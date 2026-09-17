package com.example.demo.service;

import com.example.demo.util.JwtUtil;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

import java.util.Date;
import java.util.HashMap;
import java.util.Map;

// 用户注册/登录业务逻辑
@Service
public class UserService {

    @Autowired
    private HBaseService hbase;

    @Autowired
    private PasswordEncoder encoder;

    @Autowired
    private JwtUtil jwtUtil;

    // 注册：校验重名 + 写入 HBase
    public Map<String, Object> register(String username, String password, String email) {
        Map<String, Object> result = new HashMap<>();
        try {
            if (hbase.exists("recruit_user", username)) {
                result.put("code", 1);
                result.put("msg", "用户名已存在");
                return result;
            }
            // 密码 BCrypt 加密（注册用 BCrypt，兼容 gen_data 的 SHA-256 测试号需特殊处理）
            String hashed = encoder.encode(password);
            Map<String,String> data = new HashMap<>();
            data.put("password", hashed);
            data.put("email", email != null ? email : "");
            data.put("phone", "");
            data.put("role", "user");
            data.put("nickname", username);
            data.put("created", new Date().toString().substring(0,19));
            hbase.putRow("recruit_user", username, "info", data);
            // 自动登录返回 token
            result.put("code", 0);
            result.put("token", jwtUtil.generateToken(username));
            result.put("username", username);
            result.put("msg", "注册成功");
        } catch (Exception e) {
            result.put("code", 1);
            result.put("msg", "服务器错误: " + e.getMessage());
        }
        return result;
    }

    // 登录：验证密码
    public Map<String, Object> login(String username, String password) {
        Map<String, Object> result = new HashMap<>();
        try {
            Map<String,String> user = hbase.getRow("recruit_user", username, "info");
            if (user == null) {
                result.put("code", 1);
                result.put("msg", "用户不存在");
                return result;
            }
            String storedHash = user.get("password");
            // 先试 BCrypt（网页注册的）
            if (encoder.matches(password, storedHash)) {
                result.put("code", 0);
                result.put("token", jwtUtil.generateToken(username));
                result.put("username", username);
                result.put("nickname", user.getOrDefault("nickname", username));
                result.put("role", "user");
                result.put("msg", "登录成功");
                return result;
            }
            // 再试 SHA-256（gen_data 的测试账号）
            String sha256 = java.security.MessageDigest.getInstance("SHA-256")
                    .digest(password.getBytes()).toString();
            // happybase 存的 sha256 用 hex，这里用 hex 比对
            StringBuilder sb = new StringBuilder();
            for (byte b : java.security.MessageDigest.getInstance("SHA-256")
                    .digest(password.getBytes())) {
                sb.append(String.format("%02x", b));
            }
            if (sb.toString().equals(storedHash)) {
                // 升级密码为 BCrypt
                String newHash = encoder.encode(password);
                hbase.putRow("recruit_user", username, "info",
                        Map.of("password", newHash));
                result.put("code", 0);
                result.put("token", jwtUtil.generateToken(username));
                result.put("username", username);
                result.put("nickname", user.getOrDefault("nickname", username));
                result.put("role", "user");
                result.put("msg", "登录成功");
                return result;
            }
            result.put("code", 1);
            result.put("msg", "密码错误");
        } catch (Exception e) {
            result.put("code", 1);
            result.put("msg", "服务器错误: " + e.getMessage());
        }
        return result;
    }

    // 获取用户信息
    public Map<String,String> profile(String username) {
        try {
            Map<String,String> user = hbase.getRow("recruit_user", username, "info");
            if (user != null) user.remove("password");
            return user;
        } catch (Exception e) {
            return null;
        }
    }

    // 修改密码：同时兼容历史 SHA-256 密码和网页注册产生的 BCrypt 密码
    public Map<String, Object> changePassword(String username, String oldPassword, String newPassword) {
        Map<String, Object> result = new HashMap<>();
        if (newPassword == null || newPassword.length() < 6) {
            result.put("code", 1);
            result.put("msg", "新密码至少需要 6 位");
            return result;
        }
        if (newPassword.equals(oldPassword)) {
            result.put("code", 1);
            result.put("msg", "新密码不能与原密码相同");
            return result;
        }
        try {
            Map<String, String> user = hbase.getRow("recruit_user", username, "info");
            if (user == null || !passwordMatches(oldPassword, user.get("password"))) {
                result.put("code", 1);
                result.put("msg", "原密码错误");
                return result;
            }
            hbase.putRow("recruit_user", username, "info",
                    Map.of("password", encoder.encode(newPassword),
                           "password_updated", new Date().toString()));
            result.put("code", 0);
            result.put("msg", "密码修改成功，请重新登录");
        } catch (Exception e) {
            result.put("code", 1);
            result.put("msg", "服务器错误: " + e.getMessage());
        }
        return result;
    }

    private boolean passwordMatches(String password, String storedHash) throws Exception {
        if (password == null || storedHash == null || storedHash.isEmpty()) return false;
        if (storedHash.startsWith("$2")) return encoder.matches(password, storedHash);
        StringBuilder sb = new StringBuilder();
        for (byte b : java.security.MessageDigest.getInstance("SHA-256")
                .digest(password.getBytes(java.nio.charset.StandardCharsets.UTF_8))) {
            sb.append(String.format("%02x", b));
        }
        return sb.toString().equals(storedHash);
    }
}
