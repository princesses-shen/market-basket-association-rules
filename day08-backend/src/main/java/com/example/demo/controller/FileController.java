package com.example.demo.controller;

import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.core.io.FileSystemResource;
import org.springframework.http.ResponseEntity;
import org.springframework.http.MediaType;

import java.io.File;
import java.io.IOException;
import java.util.*;

// 文件上传/下载接口 (简历附件)
@RestController
public class FileController {

    // 上传目录(绝对路径: 跟随 jar 运行目录, 避免 transferTo 解析到 Tomcat 临时工作目录)
    private static final String UPLOAD_DIR = System.getProperty("user.dir") + File.separator + "uploads";

    // POST /api/upload  上传文件
    @PostMapping("/api/upload")
    public Map<String, Object> upload(@RequestParam("file") MultipartFile file) throws IOException {
        Map<String, Object> result = new HashMap<>();
        if (file.isEmpty()) {
            result.put("code", 1);
            result.put("msg", "文件为空");
            return result;
        }

        // 确保上传目录存在
        File dir = new File(UPLOAD_DIR);
        if (!dir.exists()) dir.mkdirs();

        // 生成唯一文件名：时间戳_原始文件名
        String originalName = file.getOriginalFilename();
        String fileName = System.currentTimeMillis() + "_" + originalName;
        File dest = new File(dir, fileName);
        file.transferTo(dest.getAbsoluteFile());

        result.put("code", 0);
        result.put("msg", "上传成功");
        result.put("fileName", originalName);
        result.put("filePath", "/uploads/" + fileName);
        return result;
    }

    // GET /uploads/{filename:.+}  下载/预览文件
    @GetMapping("/uploads/{filename:.+}")
    public ResponseEntity<FileSystemResource> download(@PathVariable String filename) {
        File file = new File(UPLOAD_DIR, filename);
        if (!file.exists()) {
            return ResponseEntity.notFound().build();
        }
        return ResponseEntity.ok()
            .contentType(MediaType.APPLICATION_OCTET_STREAM)
            .body(new FileSystemResource(file));
    }
}
