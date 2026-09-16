package com.example.demo.service;

import com.example.demo.security.AccountException;
import com.example.demo.security.AccountType;
import com.example.demo.security.EmailPurpose;
import com.example.demo.util.JwtUtil;
import org.springframework.stereotype.Service;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.time.Clock;
import java.util.*;
import java.util.stream.Collectors;
import static com.example.demo.service.AccountSecurityService.*;

/** Registration challenges live separately; login consumption uses the account's own CAS revision. */
@Service
public class EmailAuthService {
    public static final String TABLE = "recruit_email_code";
    private final HBaseService hbase;
    private final AccountSecurityService accounts;
    private final ResetMailService mail;
    private final JwtUtil jwt;
    private final Clock clock;
    private final SecureRandom random = new SecureRandom();
    public EmailAuthService(HBaseService hbase, AccountSecurityService accounts, ResetMailService mail,
                            JwtUtil jwt, Clock clock) {
        this.hbase = hbase; this.accounts = accounts; this.mail = mail; this.jwt = jwt; this.clock = clock;
    }
    private void validate(AccountType type, String username, String email) {
        if (type == AccountType.admin) throw new IllegalArgumentException("管理员不支持邮箱验证");
        validateUsername(username); validateEmail(email);
    }
    private String emailKey(String email) { return jwt.codeDigest("registration-mailbox\n" + email.toLowerCase(Locale.ROOT)); }
    private String key(AccountType type, String username) { return "register:" + type + ":" + username; }
    private Map<String, String> read(String table, String key) throws Exception {
        Map<String, String> row = hbase.getRow(table, key, "info");
        return row == null ? new HashMap<>() : row;
    }
    private boolean change(String table, String key, Map<String, String> before, Map<String, String> update) throws Exception {
        update.put("security_revision", UUID.randomUUID().toString());
        return hbase.compareAndPut(table, key, "security_revision", before.get("security_revision"), update);
    }
    private AccountException invalid() { return new AccountException(400, "账号信息或验证码无效，请重新获取验证码"); }
    private AccountException busy() { return new AccountException(503, "请求繁忙，请稍后重试"); }
    private Map<String, Object> reply() {
        return Map.of("code", 0, "msg", "若账号信息符合条件，验证码将发送至该邮箱，请查收");
    }
    private Map<String, String> quota(Map<String, String> row, String prefix) {
        long now = clock.millis();
        if (row.containsKey(prefix + "sent_at") && now - number(row, prefix + "sent_at") < 60_000)
            throw new AccountException(429, "请间隔 60 秒后再发送验证码");
        List<Long> sends = new ArrayList<>();
        for (String stamp : row.getOrDefault(prefix + "sends", "").split(","))
            if (!stamp.isEmpty() && Long.parseLong(stamp) > now - 3_600_000) sends.add(Long.parseLong(stamp));
        if (sends.size() >= 5) throw new AccountException(429, "每小时最多发送 5 次验证码");
        sends.add(now);
        Map<String, String> update = new HashMap<>();
        update.put(prefix + "sent_at", Long.toString(now));
        update.put(prefix + "sends", sends.stream().map(Object::toString).collect(Collectors.joining(",")));
        return update;
    }
    private void reserveMailbox(String email) throws Exception {
        String key = "mailbox:" + emailKey(email);
        for (int retry = 0; retry < 100; retry++) {
            Map<String, String> row = read(TABLE, key);
            if (change(TABLE, key, row, quota(row, "register_"))) return;
        }
        throw busy();
    }
    private String digest(String purpose, AccountType type, String username, String email,
                          String nonce, String version, String code) {
        return jwt.codeDigest("email-code\n" + purpose + "\n" + type + "\n" + username + "\n"
                + email.toLowerCase(Locale.ROOT) + "\n" + nonce + "\n" + version + "\n" + code);
    }
    private String digest(String prefix, AccountType type, String username, Map<String, String> row, String code) {
        return digest(prefix, type, username, row.getOrDefault(prefix + "email", ""),
                row.getOrDefault(prefix + "nonce", ""), row.getOrDefault(prefix + "version", "0"), code);
    }
    public Map<String, Object> sendRegistration(AccountType type, String username, String email) throws Exception {
        validate(type, username, email); mail.requireAvailable();
        if (read(type.table, username).containsKey(type.passwordColumn)) throw new AccountException(409, "账号已存在");
        // Check account quota first; mailbox CAS prevents changing usernames/types from bypassing the limit.
        quota(read(TABLE, key(type, username)), "register_");
        reserveMailbox(email);
        return send(type, username, email, false);
    }
    public Map<String, Object> sendLogin(AccountType type, String username, String email) throws Exception {
        validate(type, username, email); mail.requireAvailable();
        return send(type, username, email, true);
    }
    private boolean matchesAccount(Map<String, String> row, AccountType type, String email) {
        return row.containsKey(type.passwordColumn) && email.equalsIgnoreCase(row.get("email"));
    }
    private Map<String, Object> send(AccountType type, String username, String email, boolean login) throws Exception {
        String table = login ? type.table : TABLE, key = login ? username : key(type, username);
        String prefix = login ? "login_" : "register_";
        for (int retry = 0; retry < 100; retry++) {
            Map<String, String> row = read(table, key);
            if (login && (!matchesAccount(row, type, email) || blocked(row))) return reply();
            Map<String, String> update = quota(row, prefix);
            String code;
            do { code = String.format(Locale.ROOT, "%06d", random.nextInt(1_000_000)); }
            while (digest(prefix, type, username, row, code).equals(row.get(prefix + "digest")));
            update.put(prefix + "email", email.toLowerCase(Locale.ROOT));
            update.put(prefix + "nonce", UUID.randomUUID().toString());
            update.put(prefix + "version", Long.toString(number(row, "credential_version")));
            update.put(prefix + "digest", digest(prefix, type, username, update, code));
            update.put(prefix + "expires", Long.toString(clock.millis() + 600_000));
            update.put(prefix + "failures", "0");
            update.put(prefix + "state", "pending");
            if (!change(table, key, row, update)) continue;
            try { mail.send(login ? row.get("email") : email, code, login ? EmailPurpose.LOGIN : EmailPurpose.REGISTER); }
            catch (RuntimeException e) {
                finish(table, key, prefix, update.get(prefix + "nonce"), "failed"); throw e;
            }
            if (!finish(table, key, prefix, update.get(prefix + "nonce"), "ready")) throw busy();
            return reply();
        }
        throw busy();
    }
    private boolean finish(String table, String key, String prefix, String nonce, String state) throws Exception {
        for (int retry = 0; retry < 100; retry++) {
            Map<String, String> row = read(table, key);
            if (!nonce.equals(row.get(prefix + "nonce"))) return false;
            Map<String, String> update = new HashMap<>();
            update.put(prefix + "state", state);
            if (!"ready".equals(state)) update.put(prefix + "digest", "");
            if (change(table, key, row, update)) return true;
        }
        throw busy();
    }
    private Map<String, String> consume(AccountType type, String username, String email, String code, boolean login) throws Exception {
        String table = login ? type.table : TABLE, key = login ? username : key(type, username);
        String prefix = login ? "login_" : "register_";
        for (int retry = 0; retry < 100; retry++) {
            Map<String, String> row = read(table, key);
            if (!"ready".equals(row.get(prefix + "state")) || number(row, prefix + "expires") <= clock.millis()
                    || number(row, prefix + "failures") >= 5 || !email.equalsIgnoreCase(row.get(prefix + "email"))) throw invalid();
            if (login && (!matchesAccount(row, type, email)
                    || number(row, "credential_version") != number(row, prefix + "version"))) throw invalid();
            if (login && blocked(row)) throw new AccountException(423, "账号已封禁，请联系管理员解封");
            boolean correct = code != null && code.matches("[0-9]{6}") && MessageDigest.isEqual(
                    digest(prefix, type, username, row, code).getBytes(StandardCharsets.UTF_8),
                    row.getOrDefault(prefix + "digest", "").getBytes(StandardCharsets.UTF_8));
            Map<String, String> update = new HashMap<>();
            if (correct) {
                update.put(prefix + "state", "consumed"); update.put(prefix + "digest", "");
                if (login) update.put("failed_attempts", "0");
            } else {
                long failures = number(row, prefix + "failures") + 1;
                update.put(prefix + "failures", Long.toString(failures));
                if (failures >= 5) { update.put(prefix + "state", "failed"); update.put(prefix + "digest", ""); }
            }
            if (!change(table, key, row, update)) continue;
            if (!correct) throw invalid();
            row.putAll(update); return row;
        }
        throw busy();
    }
    public Map<String, Object> register(AccountType type, String username, String password, String email,
                                        String code, Map<String, String> profile) throws Exception {
        validate(type, username, email); validatePassword(password);
        if (read(type.table, username).containsKey(type.passwordColumn)) throw new AccountException(409, "账号已存在");
        consume(type, username, email, code, false);
        try { return accounts.register(type, username, password, email, profile); }
        catch (AccountException e) { throw e; }
        catch (Exception e) { throw new AccountException(503, "注册暂时失败，请先尝试登录；未注册成功请重新获取验证码"); }
    }
    public Map<String, Object> login(AccountType type, String username, String email, String code) throws Exception {
        validate(type, username, email);
        return accounts.loginResult(type, username, consume(type, username, email, code, true));
    }
}
