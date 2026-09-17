package com.example.demo.controller;

import com.example.demo.service.CompanyService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.*;

// 企业端接口: 注册/登录/发布岗位/回收岗位/人才浏览
@RestController
@RequestMapping("/api/company")
public class CompanyController {

    @Autowired
    private CompanyService companyService;

    // POST /api/company/register
    @PostMapping("/register")
    public Map<String, Object> register(@RequestBody Map<String, String> body) throws Exception {
        return companyService.register(
                body.get("username"), body.get("password"), body.get("companyName"),
                body.getOrDefault("industry", ""), body.getOrDefault("city", ""),
                body.getOrDefault("scale", ""));
    }

    // POST /api/company/login
    @PostMapping("/login")
    public Map<String, Object> login(@RequestBody Map<String, String> body) throws Exception {
        return companyService.login(body.get("username"), body.get("password"));
    }

    // POST /api/company/change-password  企业账号修改密码
    @PostMapping("/change-password")
    public Map<String, Object> changePassword(@RequestBody Map<String, String> body) throws Exception {
        return companyService.changePassword(
                body.get("username"), body.get("oldPassword"), body.get("newPassword"));
    }

    // POST /api/company/job/publish
    @PostMapping("/job/publish")
    public Map<String, Object> publishJob(@RequestBody Map<String, String> body) throws Exception {
        return companyService.publishJob(
                body.get("username"), body.get("title"), body.get("city"),
                Integer.parseInt(body.get("salaryLow")), Integer.parseInt(body.get("salaryHigh")),
                body.get("edu"), body.get("exp"), body.get("tags"),
                body.getOrDefault("category", ""), body.getOrDefault("desc", ""));
    }

    // POST /api/company/job/recall
    @PostMapping("/job/recall")
    public Map<String, Object> recallJob(@RequestBody Map<String, String> body) throws Exception {
        return companyService.recallJob(body.get("username"), body.get("jobId"));
    }

    // GET /api/company/jobs?username=
    @GetMapping("/jobs")
    public List<Map<String, String>> myJobs(@RequestParam String username) throws Exception {
        return companyService.myJobs(username);
    }

    // GET /api/company/talent?keyword=&city=&limit=
    @GetMapping("/talent")
    public List<Map<String, String>> talent(
            @RequestParam(defaultValue = "") String keyword,
            @RequestParam(defaultValue = "全部") String city,
            @RequestParam(defaultValue = "50") int limit) throws Exception {
        return companyService.browseTalent(keyword, city, limit);
    }
}
