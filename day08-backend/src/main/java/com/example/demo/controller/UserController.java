package com.example.demo.controller;

import com.example.demo.service.UserService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

// 用户接口：注册/登录/资料
@RestController
@RequestMapping("/api/user")
public class UserController {

    @Autowired
    private UserService userService;

    // POST /api/user/register  { username, password, email }
    @PostMapping("/register")
    public Map<String, Object> register(@RequestBody Map<String, String> body) throws Exception {
        String username = body.get("username");
        String password = body.get("password");
        String email = body.get("email");
        return userService.register(username, password, email, body.get("code"));
    }

    // POST /api/user/login  { username, password }
    @PostMapping("/login")
    public Map<String, Object> login(@RequestBody Map<String, String> body) throws Exception {
        return userService.login(body.get("username"), body.get("password"));
    }

    // POST /api/user/change-password  登录用户修改密码（身份取自 JWT，不采用请求体里的用户名）
    @PostMapping("/change-password")
    public Map<String, Object> changePassword(java.security.Principal principal,
                                              @RequestBody Map<String, String> body) throws Exception {
        return userService.changePassword(principal.getName(), body.get("oldPassword"), body.get("newPassword"));
    }

    // GET /api/user/profile  (需 JWT)
    @GetMapping("/profile")
    public Map<String, String> profile(java.security.Principal principal) throws Exception {
        return userService.profile(principal.getName());
    }
}
