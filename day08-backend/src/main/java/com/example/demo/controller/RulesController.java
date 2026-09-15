package com.example.demo.controller;

import com.example.demo.service.HBaseService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.*;

// 关联规则接口：读 recruit_assoc_rules 表
@RestController
@RequestMapping("/api/rules")
public class RulesController {

    @Autowired
    private HBaseService hbase;

    // GET /api/rules/strong  返回全部强规则
    @GetMapping("/strong")
    public List<Map<String, String>> strong() throws Exception {
        List<Map<String, String>> rules = hbase.scanAll("recruit_assoc_rules", "info");
        // 按 lift 降序
        rules.sort((a, b) -> {
            try {
                return Double.compare(
                        Double.parseDouble(b.getOrDefault("lift", "0")),
                        Double.parseDouble(a.getOrDefault("lift", "0")));
            } catch (NumberFormatException e) { return 0; }
        });
        return rules;
    }

    // GET /api/rules/frequent  返回频繁项集（从规则里去重 antecedents+consequents）
    @GetMapping("/frequent")
    public List<Map<String, Object>> frequent() throws Exception {
        List<Map<String, String>> rules = hbase.scanAll("recruit_assoc_rules", "info");
        Map<String, Double> seen = new HashMap<>();
        for (Map<String, String> r : rules) {
            String items = r.getOrDefault("antecedents", "") + "," + r.getOrDefault("consequents", "");
            double support = Double.parseDouble(r.getOrDefault("support", "0"));
            // 保留每个 itemset 的最高 support
            if (!seen.containsKey(items) || seen.get(items) < support) {
                seen.put(items, support);
            }
        }
        List<Map<String, Object>> list = new ArrayList<>();
        for (Map.Entry<String, Double> e : seen.entrySet()) {
            Map<String, Object> m = new HashMap<>();
            m.put("items", e.getKey());
            m.put("support", e.getValue());
            list.add(m);
        }
        // 按 support 降序
        list.sort((a, b) -> Double.compare((Double) b.get("support"), (Double) a.get("support")));
        return list;
    }
}
