package com.example.demo.controller;

import com.example.demo.service.ChatService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.*;

// 聊天+投递+人才库接口
@RestController
@RequestMapping("/api/chat")
public class ChatController {

    @Autowired
    private ChatService chatService;

    @Autowired
    private com.example.demo.security.ResourceAccess access;

    // POST /api/chat/apply  投递简历 (自动创建会话，可选附件)
    @PostMapping("/apply")
    public Map<String, Object> apply(@RequestBody Map<String, String> body) throws Exception {
        access.require("user");
        if (body.get("attachmentName") != null && !body.get("attachmentName").isEmpty())
            access.attachmentOwner(body.get("attachmentPath"));
        return chatService.applyJob(
            access.username(), body.get("jobId"),
            body.get("attachmentName"), body.get("attachmentPath")
        );
    }

    // POST /api/chat/send  发送消息
    @PostMapping("/send")
    public Map<String, Object> send(@RequestBody Map<String, String> body) throws Exception {
        access.session(body.get("sessionKey"));
        return chatService.sendMessage(body.get("sessionKey"), access.username(), body.get("content"));
    }

    // GET /api/chat/sessions?username=&role=
    @GetMapping("/sessions")
    public List<Map<String, String>> sessions(@RequestParam String username,
                                               @RequestParam(defaultValue = "user") String role) throws Exception {
        return chatService.getSessions(access.username(), access.type());
    }

    // GET /api/chat/messages?sessionKey=
    @GetMapping("/messages")
    public List<Map<String, String>> messages(@RequestParam String sessionKey) throws Exception {
        access.session(sessionKey);
        return chatService.getMessages(sessionKey);
    }

    // GET /api/chat/applications?companyUsername=
    @GetMapping("/applications")
    public List<Map<String, String>> applications(@RequestParam String companyUsername) throws Exception {
        return chatService.getApplications(access.require("company"));
    }

    // GET /api/chat/my-applications?username=
    @GetMapping("/my-applications")
    public List<Map<String, String>> myApplications(@RequestParam String username) throws Exception {
        return chatService.getMyApplications(access.require("user"));
    }

    // POST /api/chat/talent/add  添加到人才库
    @PostMapping("/talent/add")
    public Map<String, Object> addTalent(@RequestBody Map<String, String> body) throws Exception {
        access.talent(body.get("userUsername"));
        return chatService.addToTalentPool(access.require("company"), body.get("userUsername"));
    }

    // POST /api/chat/talent/remove  从人才库删除
    @PostMapping("/talent/remove")
    public Map<String, Object> removeTalent(@RequestBody Map<String, String> body) throws Exception {
        return chatService.removeFromTalentPool(access.require("company"), body.get("userUsername"));
    }

    // GET /api/chat/talent/list?companyUsername=  人才库列表(只含姓名)
    @GetMapping("/talent/list")
    public List<Map<String, String>> talentList(@RequestParam String companyUsername) throws Exception {
        return chatService.getTalentPool(access.require("company"));
    }

    // GET /api/chat/talent/resume?userUsername=  查看某人才完整简历
    @GetMapping("/talent/resume")
    public Map<String, String> talentResume(@RequestParam String userUsername) throws Exception {
        access.talent(userUsername);
        return chatService.getTalentResume(access.username(), userUsername);
    }
}
