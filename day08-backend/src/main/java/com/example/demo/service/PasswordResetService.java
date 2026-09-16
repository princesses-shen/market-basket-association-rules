package com.example.demo.service;

import com.example.demo.security.AccountException;
import com.example.demo.security.AccountType;
import com.example.demo.util.JwtUtil;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.time.Clock;
import java.util.*;
import java.util.stream.Collectors;
import static com.example.demo.service.AccountSecurityService.*;

@Service
public class PasswordResetService {
    private final HBaseService hbase;
    private final AccountSecurityService accounts;
    private final ResetMailService mail;
    private final PasswordEncoder encoder;
    private final JwtUtil jwt;
    private final Clock clock;
    private final SecureRandom random = new SecureRandom();
    public PasswordResetService(HBaseService hbase, AccountSecurityService accounts, ResetMailService mail,
                                PasswordEncoder encoder, JwtUtil jwt, Clock clock) {
        this.hbase = hbase; this.accounts = accounts; this.mail = mail;
        this.encoder = encoder; this.jwt = jwt; this.clock = clock;
    }
    private Map<String, String> matching(AccountType type, String username, String email) throws Exception {
        if (type == AccountType.admin) throw new IllegalArgumentException("管理员不支持邮箱找回");
        if (username == null || username.isBlank() || username.length() > 256)
            throw new IllegalArgumentException("请输入账号");
        validateEmail(email);
        Map<String, String> row = hbase.getRow(type.table, username, "info");
        return row != null && email.equalsIgnoreCase(row.getOrDefault("email", "")) ? row : null;
    }
    private String digest(AccountType type, String username, String email, String nonce, String code) {
        return jwt.codeDigest("reset\n" + type + "\n" + username + "\n" + email.toLowerCase(Locale.ROOT) + "\n" + nonce + "\n" + code);
    }
    public Map<String, Object> sendCode(AccountType type, String username, String email) throws Exception {
        mail.requireAvailable();
        Map<String, Object> reply = Map.of("code", 0, "msg", "若账号与注册邮箱匹配，验证码将发送至该邮箱，请查收");
        for (int retry = 0; retry < 100; retry++) {
            Map<String, String> row = matching(type, username, email);
            if (row == null) return reply;
            long now = clock.millis();
            if (now - number(row, "reset_sent_at") < 60_000)
                throw new AccountException(429, "请间隔 60 秒后再发送验证码");
            List<Long> sends = new ArrayList<>();
            for (String stamp : row.getOrDefault("reset_sends", "").split(","))
                if (!stamp.isEmpty() && Long.parseLong(stamp) > now - 3_600_000) sends.add(Long.parseLong(stamp));
            if (sends.size() >= 5) throw new AccountException(429, "同一账号每小时最多发送 5 次验证码");
            sends.add(now);
            String code = String.format(Locale.ROOT, "%06d", random.nextInt(1_000_000));
            // Never reuse the preceding code, even if the random generator draws the same value.
            while (digest(type, username, row.getOrDefault("reset_email", ""), row.getOrDefault("reset_nonce", ""), code)
                    .equals(row.get("reset_digest")))
                code = String.format(Locale.ROOT, "%06d", random.nextInt(1_000_000));
            String nonce = UUID.randomUUID().toString();
            Map<String, String> update = new HashMap<>();
            update.put("reset_nonce", nonce);
            update.put("reset_email", email.toLowerCase(Locale.ROOT));
            update.put("reset_digest", digest(type, username, email, nonce, code));
            update.put("reset_expires", Long.toString(now + 600_000));
            update.put("reset_sent_at", Long.toString(now));
            update.put("reset_sends", sends.stream().map(Object::toString).collect(Collectors.joining(",")));
            update.put("reset_failures", "0");
            update.put("reset_state", "pending");
            if (!accounts.change(type, username, row, update)) continue;
            try { mail.send(row.get("email"), code); }
            catch (RuntimeException e) {
                finishSend(type, username, nonce, "failed");
                throw e;
            }
            if (!finishSend(type, username, nonce, "ready"))
                throw new AccountException(503, "验证码状态已变化，请稍后重新获取");
            return reply;
        }
        throw new AccountException(503, "请求繁忙，请稍后重试");
    }
    private boolean finishSend(AccountType type, String username, String nonce, String state) throws Exception {
        for (int retry = 0; retry < 100; retry++) {
            Map<String, String> row = hbase.getRow(type.table, username, "info");
            if (row == null || !nonce.equals(row.get("reset_nonce"))) return false;
            Map<String, String> update = new HashMap<>();
            update.put("reset_state", state);
            if (!"ready".equals(state)) update.put("reset_digest", "");
            if (accounts.change(type, username, row, update)) return true;
        }
        throw new AccountException(503, "请求繁忙，请稍后重试");
    }
    public Map<String, Object> confirm(AccountType type, String username, String email,
                                       String code, String password) throws Exception {
        validatePassword(password);
        String hashedPassword = encoder.encode(password);
        for (int retry = 0; retry < 100; retry++) {
            Map<String, String> row = matching(type, username, email);
            if (row == null || !email.equalsIgnoreCase(row.get("reset_email")) || !"ready".equals(row.get("reset_state"))
                    || number(row, "reset_expires") <= clock.millis() || number(row, "reset_failures") >= 5)
                throw new AccountException(400, "账号信息或验证码无效，请重新获取验证码");
            boolean correct = code != null && code.matches("[0-9]{6}") && MessageDigest.isEqual(
                    digest(type, username, email, row.get("reset_nonce"), code).getBytes(StandardCharsets.UTF_8),
                    row.getOrDefault("reset_digest", "").getBytes(StandardCharsets.UTF_8));
            Map<String, String> update = new HashMap<>();
            if (!correct) {
                long failures = number(row, "reset_failures") + 1;
                update.put("reset_failures", Long.toString(failures));
                if (failures >= 5) { update.put("reset_state", "failed"); update.put("reset_digest", ""); }
            } else {
                update.put(type.passwordColumn, hashedPassword);
                update.put("credential_version", Long.toString(number(row, "credential_version") + 1));
                update.put("reset_state", "consumed");
                update.put("reset_digest", "");
                // A password reset never unblocks the account or resets its login failure count.
            }
            if (!accounts.change(type, username, row, update)) continue;
            if (!correct) throw new AccountException(400, "账号信息或验证码无效，请重新获取验证码");
            return Map.of("code", 0, "blocked", blocked(row), "msg", blocked(row)
                    ? "密码已重置，账号仍处于封禁状态，请联系管理员解封" : "密码已重置，请重新登录");
        }
        throw new AccountException(503, "请求繁忙，请稍后重试");
    }
}
