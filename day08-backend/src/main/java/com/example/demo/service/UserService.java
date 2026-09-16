package com.example.demo.service;

import com.example.demo.security.AccountType;
import org.springframework.stereotype.Service;
import java.util.*;

@Service
public class UserService {
    private final HBaseService hbase;
    private final AccountSecurityService accounts;
    private final EmailAuthService emailAuth;
    public UserService(HBaseService hbase, AccountSecurityService accounts, EmailAuthService emailAuth) { this.hbase = hbase; this.accounts = accounts; this.emailAuth = emailAuth; }
    public Map<String, Object> register(String username, String password, String email, String code) throws Exception {
        return emailAuth.register(AccountType.user, username, password, email, code,
                Map.of("phone", "", "role", "user", "nickname", username == null ? "" : username,
                        "created", new Date().toString()));
    }
    public Map<String, Object> login(String username, String password) throws Exception {
        return accounts.login(AccountType.user, username, password);
    }
    public Map<String, String> profile(String username) throws Exception {
        Map<String, String> row = hbase.getRow("recruit_user", username, "info");
        Map<String, String> result = new HashMap<>();
        if (row != null) for (String key : Arrays.asList("email", "phone", "nickname", "created"))
            result.put(key, row.getOrDefault(key, ""));
        result.put("username", username);
        result.put("role", "user");
        return result;
    }
}
