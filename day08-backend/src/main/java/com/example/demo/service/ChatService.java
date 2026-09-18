package com.example.demo.service;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.*;

// 聊天+投递+人才库服务
@Service
public class ChatService {

    @Autowired
    private HBaseService hbase;

    private static final String CF = "info";
    private static final String TBL_JOB = "recruit_job";
    private static final String TBL_COMPANY = "recruit_company";
    private static final String TBL_RESUME = "recruit_resume";
    private static final String TBL_SESSION = "recruit_chat_session";
    private static final String TBL_MSG = "recruit_chat_message";
    private static final String TBL_APP = "recruit_application";
    private static final String TBL_TALENT_POOL = "recruit_talent_pool";

    // 投递简历: 校验岗位 -> 写投递记录 -> 创建/复用会话 -> 如有附件自动发消息
    public Map<String, Object> applyJob(String username, String jobId,
                                         String attachmentName, String attachmentPath) throws Exception {
        Map<String, Object> result = new HashMap<>();

        Map<String, String> job = hbase.getRow(TBL_JOB, jobId, CF);
        if (job == null || job.isEmpty()) {
            result.put("code", 1);
            result.put("msg", "岗位不存在");
            return result;
        }
        if ("recalled".equals(job.get("status"))) {
            result.put("code", 1);
            result.put("msg", "该岗位已停止招聘");
            return result;
        }

        String companyUsername = job.getOrDefault("owner", "");
        String jobTitle = job.getOrDefault("title", "");
        String companyName = job.getOrDefault("company", "");

        Map<String, String> resume = hbase.getRow(TBL_RESUME, "user_" + username, CF);
        if (resume == null || resume.isEmpty()) {
            result.put("code", 1);
            result.put("msg", "请先完善简历后再投递");
            return result;
        }

        String sessionKey = buildSessionKey(username, companyUsername, jobId);
        if (hbase.exists(TBL_SESSION, sessionKey)) {
            result.put("code", 0);
            result.put("msg", "已投递过该岗位，可直接聊天");
            result.put("sessionKey", sessionKey);
            return result;
        }

        // 写投递记录
        String appKey = "app_" + System.currentTimeMillis();
        Map<String, String> appData = new HashMap<>();
        appData.put("username", username);
        appData.put("jobId", jobId);
        appData.put("jobTitle", jobTitle);
        appData.put("companyUsername", companyUsername);
        appData.put("companyName", companyName);
        appData.put("resumeName", resume.getOrDefault("name", username));
        appData.put("status", "pending");
        appData.put("applyTime", new Date().toString());
        appData.put("sessionKey", sessionKey);
        if (attachmentName != null && !attachmentName.isEmpty()) {
            appData.put("attachmentName", attachmentName);
            appData.put("attachmentPath", attachmentPath);
        }
        hbase.putRow(TBL_APP, appKey, CF, appData);

        // 创建会话
        String greetingMessage = "您好，对公司岗位很感兴趣，这是我的简历，期待进一步沟通";
        boolean hasAttachment = attachmentName != null && !attachmentName.isEmpty();

        Map<String, String> sessData = new HashMap<>();
        sessData.put("userUsername", username);
        sessData.put("companyUsername", companyUsername);
        sessData.put("jobId", jobId);
        sessData.put("jobTitle", jobTitle);
        sessData.put("companyName", companyName);
        sessData.put("resumeName", resume.getOrDefault("name", username));
        sessData.put("lastMessage", hasAttachment ? greetingMessage : "用户投递了简历，等待企业回复");
        sessData.put("lastTime", new Date().toString());
        sessData.put("lastSender", hasAttachment ? username : "system");
        hbase.putRow(TBL_SESSION, sessionKey, CF, sessData);

        // 如果有附件，自动创建一条带附件的消息
        if (hasAttachment) {
            String msgKey = "msg_" + sessionKey + "_" + System.currentTimeMillis();
            Map<String, String> msgData = new HashMap<>();
            msgData.put("sessionKey", sessionKey);
            msgData.put("sender", username);
            msgData.put("content", greetingMessage);
            msgData.put("attachmentName", attachmentName);
            msgData.put("attachmentPath", attachmentPath);
            msgData.put("sendTime", new Date().toString());
            msgData.put("timestamp", String.valueOf(System.currentTimeMillis()));
            hbase.putRow(TBL_MSG, msgKey, CF, msgData);
        }

        result.put("code", 0);
        result.put("msg", "投递成功");
        result.put("sessionKey", sessionKey);
        return result;
    }

    // 发送消息
    public Map<String, Object> sendMessage(String sessionKey, String sender, String content) throws Exception {
        Map<String, Object> result = new HashMap<>();
        Map<String, String> session = hbase.getRow(TBL_SESSION, sessionKey, CF);
        if (session == null || session.isEmpty()) {
            result.put("code", 1);
            result.put("msg", "会话不存在");
            return result;
        }
        String now = new Date().toString();
        long ts = System.currentTimeMillis();

        String msgKey = "msg_" + sessionKey + "_" + ts;
        Map<String, String> msgData = new HashMap<>();
        msgData.put("sessionKey", sessionKey);
        msgData.put("sender", sender);
        msgData.put("content", content);
        msgData.put("sendTime", now);
        msgData.put("timestamp", String.valueOf(ts));
        hbase.putRow(TBL_MSG, msgKey, CF, msgData);

        Map<String, String> upd = new HashMap<>();
        upd.put("lastMessage", content);
        upd.put("lastTime", now);
        upd.put("lastSender", sender);
        hbase.putRow(TBL_SESSION, sessionKey, CF, upd);

        result.put("code", 0);
        result.put("msg", "发送成功");
        return result;
    }

    // 获取会话列表 (按角色)
    public List<Map<String, String>> getSessions(String username, String role) throws Exception {
        List<Map<String, String>> all = hbase.scanAll(TBL_SESSION, CF);
        List<Map<String, String>> mine = new ArrayList<>();
        for (Map<String, String> s : all) {
            if ("company".equals(role)) {
                if (username.equals(s.get("companyUsername"))) mine.add(s);
            } else {
                if (username.equals(s.get("userUsername"))) mine.add(s);
            }
        }
        mine.sort((a, b) -> {
            String ta = a.getOrDefault("lastTime", "");
            String tb = b.getOrDefault("lastTime", "");
            return tb.compareTo(ta);
        });
        return mine;
    }

    // 获取聊天记录
    public List<Map<String, String>> getMessages(String sessionKey) throws Exception {
        List<Map<String, String>> all = hbase.scanAll(TBL_MSG, CF);
        List<Map<String, String>> msgs = new ArrayList<>();
        for (Map<String, String> m : all) {
            if (sessionKey.equals(m.get("sessionKey"))) msgs.add(m);
        }
        msgs.sort(Comparator.comparing(m -> m.getOrDefault("timestamp", "0")));
        return msgs;
    }

    // 获取投递记录 (企业查看收到的投递)
    public List<Map<String, String>> getApplications(String companyUsername) throws Exception {
        List<Map<String, String>> all = hbase.scanAll(TBL_APP, CF);
        List<Map<String, String>> mine = new ArrayList<>();
        for (Map<String, String> a : all) {
            if (companyUsername.equals(a.get("companyUsername"))) mine.add(a);
        }
        mine.sort((a, b) -> {
            String ta = a.getOrDefault("applyTime", "");
            String tb = b.getOrDefault("applyTime", "");
            return tb.compareTo(ta);
        });
        return mine;
    }

    // 用户查看自己的投递
    public List<Map<String, String>> getMyApplications(String username) throws Exception {
        List<Map<String, String>> all = hbase.scanAll(TBL_APP, CF);
        List<Map<String, String>> mine = new ArrayList<>();
        for (Map<String, String> a : all) {
            if (username.equals(a.get("username"))) mine.add(a);
        }
        mine.sort((a, b) -> {
            String ta = a.getOrDefault("applyTime", "");
            String tb = b.getOrDefault("applyTime", "");
            return tb.compareTo(ta);
        });
        return mine;
    }

    // 添加到人才库
    public Map<String, Object> addToTalentPool(String companyUsername, String userUsername) throws Exception {
        Map<String, Object> result = new HashMap<>();
        String key = "talent_" + companyUsername + "_" + userUsername;
        if (hbase.exists(TBL_TALENT_POOL, key)) {
            result.put("code", 1);
            result.put("msg", "该用户已在人才库中");
            return result;
        }
        Map<String, String> resume = hbase.getRow(TBL_RESUME, "user_" + userUsername, CF);
        Map<String, String> data = new HashMap<>();
        data.put("companyUsername", companyUsername);
        data.put("userUsername", userUsername);
        data.put("resumeName", resume != null ? resume.getOrDefault("name", userUsername) : userUsername);
        data.put("addTime", new Date().toString());
        hbase.putRow(TBL_TALENT_POOL, key, CF, data);
        result.put("code", 0);
        result.put("msg", "已加入人才库");
        return result;
    }

    // 从人才库删除
    public Map<String, Object> removeFromTalentPool(String companyUsername, String userUsername) throws Exception {
        Map<String, Object> result = new HashMap<>();
        String key = "talent_" + companyUsername + "_" + userUsername;
        Map<String, String> talent = hbase.getRow(TBL_TALENT_POOL, key, CF);
        if (talent == null) {
            result.put("code", 1);
            result.put("msg", "该用户不在人才库中");
            return result;
        }
        if (!companyUsername.equals(talent.get("companyUsername")) || !userUsername.equals(talent.get("userUsername")))
            throw new org.springframework.security.access.AccessDeniedException("无权操作其他企业的人才库");
        hbase.deleteRow(TBL_TALENT_POOL, key);
        result.put("code", 0);
        result.put("msg", "已从人才库移除");
        return result;
    }

    // 获取人才库列表 (只返回姓名和用户名，不返回简历详情)
    public List<Map<String, String>> getTalentPool(String companyUsername) throws Exception {
        List<Map<String, String>> all = hbase.scanAll(TBL_TALENT_POOL, CF);
        List<Map<String, String>> mine = new ArrayList<>();
        for (Map<String, String> t : all) {
            if (companyUsername.equals(t.get("companyUsername"))) {
                Map<String, String> item = new HashMap<>();
                item.put("userUsername", t.getOrDefault("userUsername", ""));
                item.put("resumeName", t.getOrDefault("resumeName", ""));
                item.put("addTime", t.getOrDefault("addTime", ""));
                mine.add(item);
            }
        }
        mine.sort((a, b) -> {
            String ta = a.getOrDefault("addTime", "");
            String tb = b.getOrDefault("addTime", "");
            return tb.compareTo(ta);
        });
        return mine;
    }

    // 获取某个用户的完整简历 (人才库点击查看用)
    public Map<String, String> getTalentResume(String companyUsername, String userUsername) throws Exception {
        Map<String, String> resume = hbase.getRow(TBL_RESUME, "user_" + userUsername, CF);
        if (resume == null) resume = new HashMap<>();

        // 找出该候选人投递给当前企业的最新附件简历，附加到网页简历结果中
        List<Map<String, String>> applications = hbase.scanAll(TBL_APP, CF);
        Map<String, String> latest = null;
        for (Map<String, String> app : applications) {
            if (!userUsername.equals(app.get("username"))) continue;
            if (companyUsername != null && !companyUsername.isEmpty()
                    && !companyUsername.equals(app.get("companyUsername"))) continue;
            if (app.getOrDefault("attachmentPath", "").isEmpty()) continue;
            if (latest == null || app.getOrDefault("applyTime", "")
                    .compareTo(latest.getOrDefault("applyTime", "")) > 0) {
                latest = app;
            }
        }
        if (latest != null) {
            resume.put("attachmentName", latest.getOrDefault("attachmentName", ""));
            resume.put("attachmentPath", latest.getOrDefault("attachmentPath", ""));
            resume.put("attachmentJobTitle", latest.getOrDefault("jobTitle", ""));
            resume.put("attachmentApplyTime", latest.getOrDefault("applyTime", ""));
        }
        return resume;
    }

    private String buildSessionKey(String user, String company, String jobId) {
        return "sess_" + user + "_" + company + "_" + jobId;
    }
}
