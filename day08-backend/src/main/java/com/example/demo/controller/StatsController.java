package com.example.demo.controller;

import com.example.demo.service.HBaseService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

// Controller 极薄，只做"路由 + 调 Service"
@RestController
@RequestMapping("/api/stats")
public class StatsController {

    @Autowired
    private HBaseService hbase;

    // 职位分布：城市 -> 职位数  (GET /api/stats/position)
    @GetMapping("/position")
    public Map<String, String> position() throws Exception {
        return hbase.scan("recruit_position", "info", "position_count");
    }

    // 薪资分布：区间 -> 岗位数  (GET /api/stats/salary)
    @GetMapping("/salary")
    public Map<String, String> salary() throws Exception {
        return hbase.scan("recruit_salary", "info", "count");
    }

    // 最低月薪工资趋势：升序序列  (GET /api/stats/salary/trend)
    @GetMapping("/salary/trend")
    public List<String> salaryTrend() throws Exception {
        return hbase.scanList("recruit_salary_trend", "info", "low");
    }

    // 关键词分布：关键词 -> 出现次数  (GET /api/stats/keyword)
    @GetMapping("/keyword")
    public Map<String, String> keyword() throws Exception {
        return hbase.scan("recruit_keyword", "info", "count");
    }
}
