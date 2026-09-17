package com.example.demo.controller;

import com.example.demo.security.AccountType;
import com.example.demo.service.AccountSecurityService;
import com.example.demo.service.PasswordResetService;
import com.example.demo.service.EmailAuthService;
import org.springframework.web.bind.annotation.*;
import java.security.Principal;
import java.util.Map;

@RestController
public class AccountController {
    private final AccountSecurityService accounts;
    private final PasswordResetService reset;
    private final EmailAuthService emailAuth;
    public AccountController(AccountSecurityService accounts, PasswordResetService reset, EmailAuthService emailAuth) {
        this.accounts = accounts; this.reset = reset; this.emailAuth = emailAuth;
    }
    @PostMapping("/api/admin/login")
    public Map<String, Object> login(@RequestBody Map<String, String> body) throws Exception {
        return accounts.login(AccountType.admin, body.get("username"), body.get("password"));
    }
    @GetMapping("/api/admin/accounts")
    public Map<String, Object> list(@RequestParam(defaultValue="all") String accountType,
            @RequestParam(defaultValue="") String keyword, @RequestParam(defaultValue="all") String status,
            @RequestParam(defaultValue="1") int page, @RequestParam(defaultValue="20") int size) throws Exception {
        return accounts.accounts(accountType, keyword, status, page, size);
    }
    @PostMapping("/api/admin/accounts/unlock")
    public Map<String, Object> unlock(@RequestBody Map<String, String> body, Principal principal) throws Exception {
        return accounts.unlock(AccountType.publicType(body.get("accountType")), body.get("username"), principal.getName());
    }
    @PostMapping("/api/auth/password-reset/code")
    public Map<String, Object> code(@RequestBody Map<String, String> body) throws Exception {
        return reset.sendCode(AccountType.publicType(body.get("accountType")), body.get("username"), body.get("email"));
    }
    @PostMapping("/api/auth/password-reset/confirm")
    public Map<String, Object> confirm(@RequestBody Map<String, String> body) throws Exception {
        return reset.confirm(AccountType.publicType(body.get("accountType")), body.get("username"), body.get("email"),
                body.get("code"), body.get("newPassword"));
    }
    @PostMapping("/api/auth/register/code")
    public Map<String, Object> registrationCode(@RequestBody Map<String, String> body) throws Exception {
        return emailAuth.sendRegistration(AccountType.publicType(body.get("accountType")), body.get("username"), body.get("email"));
    }
    @PostMapping("/api/auth/email-login/code")
    public Map<String, Object> loginCode(@RequestBody Map<String, String> body) throws Exception {
        return emailAuth.sendLogin(AccountType.publicType(body.get("accountType")), body.get("username"), body.get("email"));
    }
    @PostMapping("/api/auth/email-login/confirm")
    public Map<String, Object> emailLogin(@RequestBody Map<String, String> body) throws Exception {
        return emailAuth.login(AccountType.publicType(body.get("accountType")), body.get("username"), body.get("email"), body.get("code"));
    }
}
