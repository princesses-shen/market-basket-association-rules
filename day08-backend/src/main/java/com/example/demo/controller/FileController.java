package com.example.demo.controller;

import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.core.io.FileSystemResource;
import org.springframework.http.ContentDisposition;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;

import java.io.File;
import java.nio.charset.StandardCharsets;
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
    private static final String TABLE_UPLOAD = "recruit_upload";
    private static final String CF = "info";
    private static final long MAX_FILE_SIZE = 10L * 1024 * 1024;

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

        if (file.getSize() > MAX_FILE_SIZE) {
            result.put("code", 1);
            result.put("msg", "文件不能超过 10MB");
            return result;
        }

        // 原文件名只保留最后一段并去掉换行，避免路径穿越与响应头注入。
        String originalName = file.getOriginalFilename();
        if (originalName == null || originalName.isBlank()) originalName = "attachment";
        originalName = originalName.replace('\\', '/');
        originalName = originalName.substring(originalName.lastIndexOf('/') + 1).replaceAll("[\\r\\n]", "");

        // 确保上传目录存在
        File dir = new File(UPLOAD_DIR);
        if (!dir.exists()) dir.mkdirs();

        // 用随机标识保存附件，原文件名仅保存在元数据中。
        String fileName = UUID.randomUUID().toString();
        File dest = new File(dir, fileName);
        hbase.putRow(TABLE_UPLOAD, fileName, CF, Map.of("owner", access.username(),
                "accountType", access.type(), "originalName", originalName));
        file.transferTo(dest.getAbsoluteFile());

        result.put("code", 0);
        result.put("msg", "上传成功");
        result.put("fileName", originalName);
        result.put("filePath", "/uploads/" + fileName);
        return result;
    }

    // GET /uploads/{filename:.+}  在线预览文件 (PDF / Word)
    @GetMapping("/uploads/{filename:.+}")
    public ResponseEntity<FileSystemResource> download(@PathVariable String filename) throws Exception {
        access.download(filename);
        File file = existingAttachment(filename);
        if (file == null) return ResponseEntity.notFound().build();
        String downloadName = storedOriginalName(filename);
        return ResponseEntity.ok()
            .header("Content-Disposition", ContentDisposition.inline()
                    .filename(downloadName, StandardCharsets.UTF_8).build().toString())
            .header("X-Content-Type-Options", "nosniff")
            .contentType(mediaTypeOf(downloadName))
            .body(new FileSystemResource(file));
    }

    // GET /api/files/{filename}/download  企业端把附件简历保存到本机
    @GetMapping("/api/files/{filename:.+}/download")
    public ResponseEntity<FileSystemResource> saveToComputer(@PathVariable String filename) throws Exception {
        access.download(filename);
        File file = existingAttachment(filename);
        if (file == null) return ResponseEntity.notFound().build();
        String downloadName = storedOriginalName(filename);
        return ResponseEntity.ok()
            .header("Content-Disposition", ContentDisposition.attachment()
                    .filename(downloadName, StandardCharsets.UTF_8).build().toString())
            .header("X-Content-Type-Options", "nosniff")
            .contentType(mediaTypeOf(downloadName))
            .body(new FileSystemResource(file));
    }

    // 仅允许 uploads 目录下的单个文件, 防路径穿越
    private File existingAttachment(String filename) throws Exception {
        File base = new File(UPLOAD_DIR).getCanonicalFile();
        File file = new File(base, filename).getCanonicalFile();
        if (!base.equals(file.getParentFile()) || !file.isFile()) return null;
        return file;
    }

    // 上传时把原文件名写入元数据，这里读回来做下载名与 MIME 判断
    private String storedOriginalName(String filename) throws Exception {
        Map<String, String> metadata = hbase.getRow(TABLE_UPLOAD, filename, CF);
        String name = metadata == null ? null : metadata.get("originalName");
        return name == null || name.isBlank() ? filename : name;
    }

    private String extensionOf(String name) {
        int dot = name.lastIndexOf('.');
        return dot < 0 ? "" : name.substring(dot + 1).toLowerCase(Locale.ROOT);
    }

    private MediaType mediaTypeOf(String name) {
        String ext = extensionOf(name);
        if ("pdf".equals(ext)) return MediaType.APPLICATION_PDF;
        if ("doc".equals(ext)) return MediaType.parseMediaType("application/msword");
        if ("docx".equals(ext)) {
            return MediaType.parseMediaType("application/vnd.openxmlformats-officedocument.wordprocessingml.document");
        }
        return MediaType.APPLICATION_OCTET_STREAM;
    }
}
