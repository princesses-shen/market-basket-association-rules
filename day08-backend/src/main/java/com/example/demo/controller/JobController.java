package com.example.demo.controller;

import com.example.demo.service.HBaseService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.*;

// 岗位接口：搜索/详情/推荐/城市列表
@RestController
@RequestMapping("/api/job")
public class JobController {

    @Autowired
    private HBaseService hbase;

    // GET /api/job/search?city=&salaryMin=&salaryMax=&keyword=&category=&page=&size=
    @GetMapping("/search")
    public Map<String, Object> search(
            @RequestParam(defaultValue = "") String city,
            @RequestParam(defaultValue = "0") int salaryMin,
            @RequestParam(defaultValue = "0") int salaryMax,
            @RequestParam(defaultValue = "") String keyword,
            @RequestParam(defaultValue = "全部") String category,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "10") int size) throws Exception {

        List<Map<String,String>> all = hbase.scanJobs(city, salaryMin, salaryMax, keyword, category, 0);
        int total = all.size();
        int start = (page - 1) * size;
        int end = Math.min(start + size, total);
        List<Map<String,String>> pageData = (start < total)
                ? new ArrayList<>(all.subList(start, end))
                : new ArrayList<>();

        Map<String, Object> result = new HashMap<>();
        result.put("list", pageData);
        result.put("total", total);
        result.put("page", page);
        result.put("size", size);
        result.put("totalPages", (total + size - 1) / size);
        return result;
    }

    // GET /api/job/detail/{id}
    @GetMapping("/detail/{id}")
    public Map<String, String> detail(@PathVariable String id) throws Exception {
        Map<String,String> job = hbase.getRow("recruit_job", id, "info");
        if (job == null) {
            Map<String,String> err = new HashMap<>();
            err.put("error", "岗位不存在");
            return err;
        }
        return job;
    }

    // GET /api/job/featured  首页推荐 6 条
    @GetMapping("/featured")
    public List<Map<String,String>> featured() throws Exception {
        return hbase.scanJobs("", 0, 0, "", "全部", 6);
    }

    // GET /api/job/cities  城市列表（直接从岗位表动态去重，避免被固定热门城市限制）
    @GetMapping("/cities")
    public List<String> cities() throws Exception {
        List<Map<String, String>> jobs = hbase.scanAll("recruit_job", "info");
        Set<String> cities = new TreeSet<>();
        for (Map<String, String> job : jobs) {
            String city = job.getOrDefault("city", "").trim();
            if (!city.isEmpty()) cities.add(city);
        }
        return new ArrayList<>(cities);
    }
}
