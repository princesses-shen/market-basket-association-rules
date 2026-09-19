package com.example.demo.controller;

import com.example.demo.service.AnnouncementService;
import org.springframework.web.bind.annotation.*;
import java.security.Principal;
import java.util.Map;

@RestController
public class AnnouncementController {
    private final AnnouncementService announcements;
    public AnnouncementController(AnnouncementService announcements) { this.announcements = announcements; }

    @GetMapping("/api/announcements")
    public Map<String, Object> list(@RequestParam(required = false) String page,
                                    @RequestParam(required = false) String size) throws Exception {
        return announcements.list(page == null ? "1" : page, size == null ? "10" : size);
    }
    @GetMapping("/api/announcements/{id}")
    public Map<String, Object> detail(@PathVariable String id) throws Exception {
        return Map.of("code", 0, "item", announcements.detail(id));
    }
    @PostMapping("/api/admin/announcements")
    public Map<String, Object> create(@RequestBody Map<String, Object> body, Principal principal) throws Exception {
        return Map.of("code", 0, "item", announcements.create(body, principal.getName()));
    }
    @PostMapping("/api/admin/announcements/{id}/update")
    public Map<String, Object> update(@PathVariable String id, @RequestBody Map<String, Object> body) throws Exception {
        return Map.of("code", 0, "item", announcements.update(id, body));
    }
    @PostMapping("/api/admin/announcements/{id}/delete")
    public Map<String, Object> delete(@PathVariable String id) throws Exception {
        announcements.delete(id);
        return Map.of("code", 0, "msg", "公告已删除");
    }
}
