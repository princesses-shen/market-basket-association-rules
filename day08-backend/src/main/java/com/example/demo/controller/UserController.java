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
    public Map<String, Object> register(@RequestBody Map<String, String> body) {
        String username = body.get("username");
        String password = body.get("password");
        String email = body.get("email");
        return userService.register(username, password, email);
    }

    // POST /api/user/login  { username, password }
    @PostMapping("/login")
    public Map<String, Object> login(@RequestBody Map<String, String> body) {
        return userService.login(body.get("username"), body.get("password"));
    }

    @Autowired
    private com.example.demo.util.JwtUtil jwtUtil;

    // GET /api/user/profile  (需 JWT)
    @GetMapping("/profile")
    public Map<String, String> profile(@RequestHeader(value="Authorization", required=false) String auth) {
        if (auth == null || !auth.startsWith("Bearer ")) {
            return Map.of("error", "未登录");
        }
        String token = auth.substring(7);
        io.jsonwebtoken.Claims c = jwtUtil.validateToken(token);
        if (c == null) return Map.of("error", "token无效");
        return userService.profile(c.getSubject());
    }
}
