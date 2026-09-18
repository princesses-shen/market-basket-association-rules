package com.example.demo.service;

import com.example.demo.security.AccountException;
import com.example.demo.security.AccountType;
import com.example.demo.util.JwtUtil;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import javax.mail.internet.InternetAddress;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;

@Service
public class AccountSecurityService {
    private final HBaseService hbase;
    private final PasswordEncoder encoder;
    private final JwtUtil jwt;
    public AccountSecurityService(HBaseService hbase, PasswordEncoder encoder, JwtUtil jwt) {
        this.hbase = hbase;
        this.encoder = encoder;
        this.jwt = jwt;
    }
    public static long number(Map<String, String> row, String key) {
        return Long.parseLong(row.getOrDefault(key, "0"));
    }
    public static boolean blocked(Map<String, String> row) {
        return "true".equals(row.get("blocked"));
    }
    public static void validatePassword(String password) {
        if (password == null || password.length() < 6 || password.getBytes(StandardCharsets.UTF_8).length > 72)
            throw new IllegalArgumentException("密码至少 6 位，且不超过 72 字节");
    }
    public static void validateEmail(String email) {
        try {
            if (email == null || email.length() > 254 || !email.equals(email.trim())
                    || !email.matches("[^\\s@]+@[^\\s@]+\\.[^\\s@]+")) throw new IllegalArgumentException();
            InternetAddress address = new InternetAddress(email, true);
            address.validate();
            if (!email.equals(address.getAddress())) throw new IllegalArgumentException();
        } catch (Exception e) { throw new IllegalArgumentException("请填写格式有效的注册邮箱"); }
    }
    public static void validateUsername(String username) {
        if (username == null || !username.matches("[\\p{L}\\p{N}_@.\\-]{1,64}"))
            throw new IllegalArgumentException("账号须为 1–64 位字母、数字、中文或 _ @ . -");
    }
    public Map<String, Object> register(AccountType type, String username, String password,
                                       String email, Map<String, String> profile) throws Exception {
        if (type == AccountType.admin) throw new IllegalArgumentException("不支持管理员注册");
        validateUsername(username);
        validatePassword(password);
        validateEmail(email);
        Map<String, String> row = new HashMap<>(profile);
        row.put(type.passwordColumn, encoder.encode(password));
        row.put("email", email);
        row.put("failed_attempts", "0");
        row.put("blocked", "false");
        row.put("credential_version", "0");
        row.put("security_revision", UUID.randomUUID().toString());
        if (!hbase.compareAndPut(type.table, username, type.passwordColumn, null, row))
            throw new AccountException(409, "账号已存在");
        return Map.of("code", 0, "msg", "注册成功，请登录");
    }
    public Map<String, Object> login(AccountType type, String username, String password) throws Exception {
        if (username == null || username.isBlank() || username.length() > 256
                || password == null || password.isEmpty() || password.length() > 1024)
            throw new IllegalArgumentException("请输入账号和密码");
        for (int retry = 0; retry < 100; retry++) {
            Map<String, String> row = hbase.getRow(type.table, username, "info");
            if (row == null) throw new AccountException(401, "账号或密码错误");
            if (type != AccountType.admin && blocked(row))
                throw new AccountException(423, "账号已封禁，请联系管理员解封");
            boolean matches = matches(password, row.get(type.passwordColumn));
            if (type == AccountType.admin) {
                if (!matches) throw new AccountException(401, "账号或密码错误");
                return loginResult(type, username, row);
            }
            Map<String, String> update = new HashMap<>();
            long failed = matches ? 0 : number(row, "failed_attempts") + 1;
            update.put("failed_attempts", Long.toString(failed));
            if (failed >= 5) {
                update.put("blocked", "true");
                update.put("blocked_at", Long.toString(System.currentTimeMillis()));
                update.put("credential_version", Long.toString(number(row, "credential_version") + 1));
            }
            if (!change(type, username, row, update)) continue;
            if (matches) return loginResult(type, username, row);
            if (failed >= 5) throw new AccountException(423, "密码连续错误 5 次，账号已封禁，请联系管理员解封");
            throw new AccountException(401, "账号或密码错误，还可尝试 " + (5 - failed) + " 次");
        }
        throw new AccountException(503, "请求繁忙，请稍后重试");
    }
    private boolean matches(String password, String hash) throws Exception {
        if (hash == null) return false;
        if (hash.startsWith("$2")) return encoder.matches(password, hash);
        StringBuilder digest = new StringBuilder();
        for (byte b : MessageDigest.getInstance("SHA-256").digest(password.getBytes(StandardCharsets.UTF_8)))
            digest.append(String.format("%02x", b));
        return MessageDigest.isEqual(digest.toString().getBytes(StandardCharsets.UTF_8), hash.getBytes(StandardCharsets.UTF_8));
    }
    public boolean change(AccountType type, String username, Map<String, String> before,
                          Map<String, String> changes) throws Exception {
        Map<String, String> update = new HashMap<>(changes);
        update.put("security_revision", UUID.randomUUID().toString());
        return hbase.compareAndPut(type.table, username, "security_revision", before.get("security_revision"), update);
    }
    Map<String, Object> loginResult(AccountType type, String username, Map<String, String> row) {
        Map<String, Object> result = new HashMap<>();
        result.put("code", 0);
        result.put("msg", "登录成功");
        result.put("username", username);
        result.put("role", type.name());
        result.put("accountType", type.name());
        result.put("nickname", row.getOrDefault("nickname", username));
        result.put("company_name", row.getOrDefault("company_name", username));
        result.put("token", jwt.generateToken(username, type, number(row, "credential_version")));
        return result;
    }
    // 登录后修改密码：校验原密码（兼容历史 SHA-256 与 BCrypt），原子写入新密码，
    // 并递增 credential_version 让此前签发的令牌全部失效。业务失败以 code/msg 返回，
    // 便于前端直接展示提示，不触发全局的 401 重新登录跳转。
    public Map<String, Object> changePassword(AccountType type, String username,
                                             String oldPassword, String newPassword) throws Exception {
        if (type == AccountType.admin) return Map.of("code", 1, "msg", "不支持修改管理员密码");
        if (username == null || username.isBlank()) return Map.of("code", 1, "msg", "请先登录");
        if (newPassword == null || newPassword.length() < 6) return Map.of("code", 1, "msg", "新密码至少需要 6 位");
        if (newPassword.getBytes(StandardCharsets.UTF_8).length > 72) return Map.of("code", 1, "msg", "新密码不能超过 72 字节");
        if (newPassword.equals(oldPassword)) return Map.of("code", 1, "msg", "新密码不能与原密码相同");
        for (int retry = 0; retry < 100; retry++) {
            Map<String, String> row = hbase.getRow(type.table, username, "info");
            if (row == null) return Map.of("code", 1, "msg", "账号不存在");
            if (!matches(oldPassword, row.get(type.passwordColumn)))
                return Map.of("code", 1, "msg", "原密码错误");
            Map<String, String> update = new HashMap<>();
            update.put(type.passwordColumn, encoder.encode(newPassword));
            update.put("password_updated", new Date().toString());
            update.put("credential_version", Long.toString(number(row, "credential_version") + 1));
            // 改密不解封账号，也不清零登录失败次数。
            if (change(type, username, row, update))
                return Map.of("code", 0, "msg", "密码修改成功，请重新登录");
        }
        return Map.of("code", 1, "msg", "请求繁忙，请稍后重试");
    }
    public Map<String, Object> accounts(String type, String keyword, String status, int page, int size) throws Exception {
        if (page < 1 || size < 1 || size > 100 || keyword.length() > 64
                || !Arrays.asList("all", "blocked", "active").contains(status))
            throw new IllegalArgumentException("查询参数不正确");
        List<AccountType> types = "all".equals(type) ? Arrays.asList(AccountType.user, AccountType.company)
                : Collections.singletonList(AccountType.publicType(type));
        List<Map<String, Object>> items = new ArrayList<>();
        for (AccountType t : types) for (Map<String, String> row : hbase.scanAll(t.table, "info")) {
            String username = row.get("rowKey");
            boolean locked = blocked(row);
            if (!username.contains(keyword) || ("blocked".equals(status) && !locked)
                    || ("active".equals(status) && locked)) continue;
            items.add(Map.of("accountType", t.name(), "username", username, "email", row.getOrDefault("email", ""),
                    "failedAttempts", number(row, "failed_attempts"), "blocked", locked,
                    "blockedAt", row.getOrDefault("blocked_at", "")));
        }
        items.sort(Comparator.comparing(row -> row.get("accountType") + ":" + row.get("username")));
        int from = (int) Math.min(items.size(), ((long) page - 1) * size);
        return Map.of("code", 0, "items", items.subList(from, Math.min(from + size, items.size())),
                "total", items.size(), "page", page, "size", size);
    }
    public Map<String, Object> unlock(AccountType type, String username, String operator) throws Exception {
        if (type == AccountType.admin) throw new IllegalArgumentException("不支持管理员解封");
        if (username == null || username.isBlank()) throw new IllegalArgumentException("请输入账号");
        for (int retry = 0; retry < 100; retry++) {
            Map<String, String> row = hbase.getRow(type.table, username, "info");
            if (row == null) throw new AccountException(404, "账号不存在");
            if (!blocked(row)) return Map.of("code", 0, "msg", "账号未封禁");
            Map<String, String> update = new HashMap<>();
            update.put("blocked", "false");
            update.put("failed_attempts", "0");
            update.put("blocked_at", "");
            update.put("credential_version", Long.toString(number(row, "credential_version") + 1));
            // Every unlock audit entry is persisted atomically with the state transition.
            update.put("unlock_audit_" + UUID.randomUUID(), operator + "|" + System.currentTimeMillis());
            if (change(type, username, row, update)) return Map.of("code", 0, "msg", "已解封，请重新登录");
        }
        throw new AccountException(503, "请求繁忙，请稍后重试");
    }
}
