package com.example.demo.security;

import com.example.demo.service.HBaseService;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import java.util.Map;

@Component
public class ResourceAccess {
    private final HBaseService hbase;
    public ResourceAccess(HBaseService hbase) { this.hbase = hbase; }
    public String username() { return authentication().getName(); }
    private Authentication authentication() {
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth == null || !auth.isAuthenticated() || "anonymousUser".equals(auth.getPrincipal()))
            throw new AccessDeniedException("未登录");
        return auth;
    }
    public String type() {
        return authentication().getAuthorities().stream().map(a -> a.getAuthority())
                .filter(a -> a.startsWith("ROLE_")).findFirst().orElseThrow(() -> new AccessDeniedException("无角色"))
                .substring(5).toLowerCase(java.util.Locale.ROOT);
    }
    public String require(String type) {
        if (!type.equals(type())) throw new AccessDeniedException("角色不匹配");
        return username();
    }
    public void session(String sessionKey) throws Exception {
        if (sessionKey == null || sessionKey.isBlank()) throw new IllegalArgumentException("请选择会话");
        Map<String, String> row = hbase.getRow("recruit_chat_session", sessionKey, "info");
        String field = "company".equals(type()) ? "companyUsername" : "userUsername";
        if (row == null || !username().equals(row.get(field))) throw new AccessDeniedException("非会话成员");
    }
    public void talent(String target) throws Exception {
        String company = require("company");
        if (target == null || target.isBlank()) throw new IllegalArgumentException("请选择人才");
        // Check stored ownership, not only a concatenated row key (legacy names may contain underscores).
        for (Map<String, String> row : hbase.scanAll("recruit_talent_pool", "info"))
            if (company.equals(row.get("companyUsername")) && target.equals(row.get("userUsername"))) return;
        for (Map<String, String> row : hbase.scanAll("recruit_chat_session", "info"))
            if (company.equals(row.get("companyUsername")) && target.equals(row.get("userUsername"))) return;
        throw new AccessDeniedException("非本企业人才或投递人");
    }
    public void attachmentOwner(String path) throws Exception {
        if (path == null || !path.startsWith("/uploads/")) throw new AccessDeniedException("附件无效");
        Map<String, String> row = hbase.getRow("recruit_upload", path.substring(9), "info");
        if (row == null || !username().equals(row.get("owner")) || !type().equals(row.get("accountType")))
            throw new AccessDeniedException("非本人附件");
    }
    public void download(String filename) throws Exception {
        Map<String, String> row = hbase.getRow("recruit_upload", filename, "info");
        if (row != null && username().equals(row.get("owner")) && type().equals(row.get("accountType"))) return;
        // Also supports existing attachments once they have a recorded application relationship.
        for (Map<String, String> application : hbase.scanAll("recruit_application", "info")) {
            if (!("/uploads/" + filename).equals(application.get("attachmentPath"))) continue;
            if ("user".equals(type()) && username().equals(application.get("username"))) return;
            if ("company".equals(type()) && username().equals(application.get("companyUsername"))) return;
        }
        throw new AccessDeniedException("无附件访问权限");
    }
}
