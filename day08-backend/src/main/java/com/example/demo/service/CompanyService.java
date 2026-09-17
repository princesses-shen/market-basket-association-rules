package com.example.demo.service;

import org.apache.hadoop.hbase.TableName;
import org.apache.hadoop.hbase.client.*;
import org.apache.hadoop.hbase.util.Bytes;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.*;

// 企业端服务: 企业注册登录 + 岗位发布/回收
@Service
public class CompanyService {

    @Autowired
    private HBaseService hbase;

    private static final String TABLE_COMPANY = "recruit_company";
    private static final String TABLE_JOB = "recruit_job";
    private static final String CF = "info";

    // 企业注册
    public Map<String, Object> register(String username, String password, String companyName, String industry, String city, String scale) throws Exception {
        Map<String, Object> result = new HashMap<>();
        if (hbase.exists(TABLE_COMPANY, username)) {
            result.put("code", 1);
            result.put("msg", "企业账号已存在");
            return result;
        }
        // 简单 hash (与 UserService 一致, SHA-256)
        String hash = sha256(password);
        Map<String, String> data = new HashMap<>();
        data.put("password_hash", hash);
        data.put("company_name", companyName);
        data.put("industry", industry);
        data.put("city", city);
        data.put("scale", scale);
        data.put("created_time", new Date().toString());
        hbase.putRow(TABLE_COMPANY, username, CF, data);
        result.put("code", 0);
        result.put("msg", "企业注册成功");
        return result;
    }

    // 企业登录
    public Map<String, Object> login(String username, String password) throws Exception {
        Map<String, Object> result = new HashMap<>();
        Map<String, String> company = hbase.getRow(TABLE_COMPANY, username, CF);
        if (company == null || company.isEmpty()) {
            result.put("code", 1);
            result.put("msg", "企业账号不存在");
            return result;
        }
        String storedHash = company.get("password_hash");
        String inputHash = sha256(password);
        if (!storedHash.equals(inputHash)) {
            result.put("code", 1);
            result.put("msg", "密码错误");
            return result;
        }
        result.put("code", 0);
        result.put("msg", "登录成功");
        result.put("username", username);
        result.put("company_name", company.get("company_name"));
        result.put("role", "company");
        return result;
    }

    // 企业账号修改密码
    public Map<String, Object> changePassword(String username, String oldPassword, String newPassword) throws Exception {
        Map<String, Object> result = new HashMap<>();
        if (newPassword == null || newPassword.length() < 6) {
            result.put("code", 1);
            result.put("msg", "新密码至少需要 6 位");
            return result;
        }
        if (newPassword.equals(oldPassword)) {
            result.put("code", 1);
            result.put("msg", "新密码不能与原密码相同");
            return result;
        }
        Map<String, String> company = hbase.getRow(TABLE_COMPANY, username, CF);
        if (company == null || company.isEmpty()) {
            result.put("code", 1);
            result.put("msg", "企业账号不存在");
            return result;
        }
        if (!sha256(oldPassword).equals(company.get("password_hash"))) {
            result.put("code", 1);
            result.put("msg", "原密码错误");
            return result;
        }
        hbase.putRow(TABLE_COMPANY, username, CF,
                Map.of("password_hash", sha256(newPassword),
                       "password_updated", new Date().toString()));
        result.put("code", 0);
        result.put("msg", "密码修改成功，请重新登录");
        return result;
    }

    // 企业发布岗位
    public Map<String, Object> publishJob(String companyUsername, String title, String city, int salLow, int salHigh,
                                            String edu, String exp, String tags, String category, String desc) throws Exception {
        Map<String, Object> result = new HashMap<>();
        Map<String, String> company = hbase.getRow(TABLE_COMPANY, companyUsername, CF);
        if (company == null || company.isEmpty()) {
            result.put("code", 1);
            result.put("msg", "企业不存在");
            return result;
        }
        // 生成 job_id
        String jobId = "job_" + System.currentTimeMillis();
        Map<String, String> data = new HashMap<>();
        data.put("title", title);
        data.put("city", city);
        data.put("company", company.getOrDefault("company_name", companyUsername));
        data.put("salary_low", String.valueOf(salLow));
        data.put("salary_high", String.valueOf(salHigh));
        data.put("edu", edu);
        data.put("exp", exp);
        data.put("tags", tags);
        data.put("category", category);
        data.put("desc", desc);
        data.put("publish_time", new Date().toString());
        data.put("status", "active"); // active / recalled
        data.put("owner", companyUsername);
        hbase.putRow(TABLE_JOB, jobId, CF, data);
        result.put("code", 0);
        result.put("msg", "发布成功");
        result.put("job_id", jobId);
        return result;
    }

    // 回收岗位
    public Map<String, Object> recallJob(String companyUsername, String jobId) throws Exception {
        Map<String, Object> result = new HashMap<>();
        Map<String, String> job = hbase.getRow(TABLE_JOB, jobId, CF);
        if (job == null || job.isEmpty()) {
            result.put("code", 1);
            result.put("msg", "岗位不存在");
            return result;
        }
        if (!companyUsername.equals(job.get("owner"))) {
            result.put("code", 1);
            result.put("msg", "无权操作他人岗位");
            return result;
        }
        Map<String, String> data = new HashMap<>();
        data.put("status", "recalled");
        hbase.putRow(TABLE_JOB, jobId, CF, data);
        result.put("code", 0);
        result.put("msg", "回收成功");
        return result;
    }

    // 列出本企业所有岗位
    public List<Map<String, String>> myJobs(String companyUsername) throws Exception {
        List<Map<String, String>> all = hbase.scanAll(TABLE_JOB, CF);
        List<Map<String, String>> mine = new ArrayList<>();
        for (Map<String, String> job : all) {
            if (companyUsername.equals(job.get("owner"))) {
                mine.add(job);
            }
        }
        return mine;
    }

    // 浏览人才 (读 recruit_talent_pool 表，只显示企业已加入的人才库)
    public List<Map<String, String>> browseTalent(String keyword, String city, int limit) throws Exception {
        List<Map<String, String>> pool = hbase.scanAll("recruit_talent_pool", CF);
        List<Map<String, String>> filtered = new ArrayList<>();
        for (Map<String, String> t : pool) {
            String userUsername = t.getOrDefault("userUsername", "");
            Map<String, String> resume = hbase.getRow("recruit_resume", "user_" + userUsername, CF);
            if (resume == null) continue;
            if (city != null && !city.isEmpty() && !city.equals("全部")
                    && !city.equals(resume.get("city"))) continue;
            if (keyword != null && !keyword.isEmpty()) {
                String target = resume.getOrDefault("skills", "") + resume.getOrDefault("name", "") + resume.getOrDefault("exp", "");
                if (!target.contains(keyword)) continue;
            }
            resume.put("userUsername", userUsername);
            resume.put("addTime", t.getOrDefault("addTime", ""));
            filtered.add(resume);
        }
        if (filtered.size() > limit) return filtered.subList(0, limit);
        return filtered;
    }

    private String sha256(String input) {
        try {
            java.security.MessageDigest md = java.security.MessageDigest.getInstance("SHA-256");
            byte[] hash = md.digest(input.getBytes("UTF-8"));
            StringBuilder sb = new StringBuilder();
            for (byte b : hash) sb.append(String.format("%02x", b));
            return sb.toString();
        } catch (Exception e) {
            return input;
        }
    }
}
