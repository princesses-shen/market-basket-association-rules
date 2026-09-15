package com.example.demo.service;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.*;

// 简历服务: 用户简历 CRUD
@Service
public class ResumeService {

    @Autowired
    private HBaseService hbase;

    private static final String TABLE = "recruit_resume";
    private static final String CF = "info";

    // 保存/更新简历 (rowKey = user_用户名)
    public Map<String, Object> save(String username, String name, String gender, int age,
                                     String city, String edu, String exp, String phone,
                                     String email, String skills, String selfIntro) throws Exception {
        Map<String, Object> result = new HashMap<>();
        Map<String, String> data = new HashMap<>();
        String rowKey = "user_" + username;
        data.put("username", username);
        data.put("name", name);
        data.put("gender", gender);
        data.put("age", String.valueOf(age));
        data.put("city", city);
        data.put("edu", edu);
        data.put("exp", exp);
        data.put("phone", phone);
        data.put("email", email);
        data.put("skills", skills);
        data.put("self_intro", selfIntro);
        data.put("updated_time", new Date().toString());
        hbase.putRow(TABLE, rowKey, CF, data);
        result.put("code", 0);
        result.put("msg", "简历保存成功");
        return result;
    }

    // 获取本人简历
    public Map<String, String> get(String username) throws Exception {
        return hbase.getRow(TABLE, "user_" + username, CF);
    }

    // 列出所有简历 (企业端浏览人才)
    public List<Map<String, String>> list(String keyword, String city, int limit) throws Exception {
        List<Map<String, String>> all = hbase.scanAll(TABLE, CF);
        List<Map<String, String>> filtered = new ArrayList<>();
        for (Map<String, String> r : all) {
            if (city != null && !city.isEmpty() && !city.equals("全部")
                    && !city.equals(r.get("city"))) continue;
            if (keyword != null && !keyword.isEmpty()) {
                String target = r.getOrDefault("skills", "") + r.getOrDefault("name", "") + r.getOrDefault("exp", "");
                if (!target.contains(keyword)) continue;
            }
            filtered.add(r);
        }
        if (limit > 0 && filtered.size() > limit) return filtered.subList(0, limit);
        return filtered;
    }
}
