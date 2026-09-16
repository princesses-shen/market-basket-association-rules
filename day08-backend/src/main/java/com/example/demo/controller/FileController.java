package com.example.demo.controller;

import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.core.io.FileSystemResource;
import org.springframework.http.ResponseEntity;
import org.springframework.http.MediaType;

import java.io.File;
import java.util.*;

// 文件上传/下载接口 (简历附件)
@RestController
public class FileController {
    private final com.example.demo.security.ResourceAccess access;
    private final com.example.demo.service.HBaseService hbase;
    public FileController(com.example.demo.security.ResourceAccess access, com.example.demo.service.HBaseService hbase) {
        this.access = access; this.hbase = hbase;
    }

    // 上传目录(绝对路径: 跟随 jar 运行目录, 避免 transferTo 解析到 Tomcat 临时工作目录)
    private static final String UPLOAD_DIR = System.getProperty("user.dir") + File.separator + "uploads";

    // POST /api/upload  上传文件
    @PostMapping("/api/upload")
    public Map<String, Object> upload(@RequestParam("file") MultipartFile file) throws Exception {
        access.require("user");
        Map<String, Object> result = new HashMap<>();
        if (file.isEmpty()) {
            result.put("code", 1);
            result.put("msg", "文件为空");
            return result;
        }

        // 确保上传目录存在
        File dir = new File(UPLOAD_DIR);
        if (!dir.exists()) dir.mkdirs();

        // 用随机标识保存附件，原文件名仅保存在元数据中。
        String originalName = file.getOriginalFilename();
        if (originalName == null || originalName.isBlank()) originalName = "attachment";
        originalName = originalName.replace('\\', '/');
        originalName = originalName.substring(originalName.lastIndexOf('/') + 1).replaceAll("[\\r\\n]", "");
        String fileName = UUID.randomUUID().toString();
        File dest = new File(dir, fileName);
        hbase.putRow("recruit_upload", fileName, "info", Map.of("owner", access.username(),
                "accountType", access.type(), "originalName", originalName));
        file.transferTo(dest.getAbsoluteFile());

        result.put("code", 0);
        result.put("msg", "上传成功");
        result.put("fileName", originalName);
        result.put("filePath", "/uploads/" + fileName);
        return result;
    }

    // GET /uploads/{filename:.+}  下载/预览文件
    @GetMapping("/uploads/{filename:.+}")
    public ResponseEntity<FileSystemResource> download(@PathVariable String filename) throws Exception {
        access.download(filename);
        File file = new File(UPLOAD_DIR, filename);
        if (!file.getCanonicalFile().getParentFile().equals(new File(UPLOAD_DIR).getCanonicalFile()) || !file.isFile()) {
            return ResponseEntity.notFound().build();
        }
        Map<String, String> metadata = hbase.getRow("recruit_upload", filename, "info");
        String downloadName = metadata == null ? filename : metadata.getOrDefault("originalName", filename);
        return ResponseEntity.ok()
            .header("Content-Disposition", org.springframework.http.ContentDisposition.attachment()
                    .filename(downloadName, java.nio.charset.StandardCharsets.UTF_8).build().toString())
            .header("X-Content-Type-Options", "nosniff")
            .contentType(MediaType.APPLICATION_OCTET_STREAM)
            .body(new FileSystemResource(file));
    }
}
