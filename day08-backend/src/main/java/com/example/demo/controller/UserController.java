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

    @GetMapping("/profile")
    public Map<String, String> profile(java.security.Principal principal) throws Exception {
        return userService.profile(principal.getName());
    }
}
