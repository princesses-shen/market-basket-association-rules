package com.example.demo.controller;

import com.example.demo.service.ResumeService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.*;

// 简历接口: 保存/查询/列表
@RestController
@RequestMapping("/api/resume")
public class ResumeController {

    @Autowired
    private ResumeService resumeService;

    // POST /api/resume/save
    @PostMapping("/save")
    public Map<String, Object> save(@RequestBody Map<String, Object> body) throws Exception {
        return resumeService.save(
                (String) body.get("username"), (String) body.get("name"),
                (String) body.getOrDefault("gender", "男"),
                body.containsKey("age") ? ((Number) body.get("age")).intValue() : 0,
                (String) body.get("city"), (String) body.get("edu"),
                (String) body.get("exp"), (String) body.get("phone"),
                (String) body.get("email"), (String) body.get("skills"),
                (String) body.getOrDefault("selfIntro", ""));
    }

    // GET /api/resume/get?username=
    @GetMapping("/get")
    public Map<String, String> get(@RequestParam String username) throws Exception {
        return resumeService.get(username);
    }

    // GET /api/resume/list?keyword=&city=&limit=
    @GetMapping("/list")
    public List<Map<String, String>> list(
            @RequestParam(defaultValue = "") String keyword,
            @RequestParam(defaultValue = "全部") String city,
            @RequestParam(defaultValue = "50") int limit) throws Exception {
        return resumeService.list(keyword, city, limit);
    }
}
