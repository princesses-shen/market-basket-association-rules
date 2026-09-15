package com.example.demo.controller;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.HashMap;
import java.util.Map;

// 声明：本类返回数据(JSON)，不是页面
@RestController
@RequestMapping("/api")
public class HelloController {

    // 返回纯文字：GET /api/hello
    @GetMapping("/hello")
    public String hello() {
        return "招聘分析系统后端已启动";
    }

    // 返回 JSON：GET /api/ping
    @GetMapping("/ping")
    public Map<String, Object> ping() {
        Map<String, Object> m = new HashMap<>();
        m.put("status", "ok");
        m.put("time", System.currentTimeMillis());
        return m;
    }
}
