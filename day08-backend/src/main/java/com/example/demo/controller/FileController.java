package com.example.demo.controller;

import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.core.io.FileSystemResource;
import org.springframework.http.ResponseEntity;
import org.springframework.http.MediaType;
import org.springframework.http.HttpHeaders;
import org.springframework.http.ContentDisposition;

import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.*;

// 文件上传/下载接口 (简历附件)
@RestController
public class FileController {

    // 上传目录(绝对路径: 跟随 jar 运行目录, 避免 transferTo 解析到 Tomcat 临时工作目录)
    private static final String UPLOAD_DIR = System.getProperty("user.dir") + File.separator + "uploads";
    private static final long MAX_FILE_SIZE = 10L * 1024 * 1024;
    private static final Set<String> ALLOWED_EXTENSIONS =
            new HashSet<>(Arrays.asList("pdf", "doc", "docx"));

    // POST /api/upload  上传文件
    @PostMapping("/api/upload")
    public Map<String, Object> upload(@RequestParam("file") MultipartFile file) throws IOException {
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

        String originalName = file.getOriginalFilename();
        if (originalName == null) originalName = "resume";
        originalName = Paths.get(originalName).getFileName().toString();
        String extension = getExtension(originalName);
        if (!ALLOWED_EXTENSIONS.contains(extension)) {
            result.put("code", 1);
            result.put("msg", "仅支持 PDF、DOC、DOCX 简历");
            return result;
        }

        // 确保上传目录存在
        File dir = new File(UPLOAD_DIR);
        if (!dir.exists()) dir.mkdirs();

        // 生成唯一文件名：时间戳_原始文件名
        String safeName = originalName.replaceAll("[^a-zA-Z0-9._\\-\\u4e00-\\u9fa5]", "_");
        String fileName = UUID.randomUUID().toString().replace("-", "") + "_" + safeName;
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
        File file = resolveStoredFile(filename);
        if (!file.exists()) {
            return ResponseEntity.notFound().build();
        }
        MediaType mediaType = detectMediaType(file.toPath());
        return ResponseEntity.ok()
            .contentType(mediaType)
            .header(HttpHeaders.CONTENT_DISPOSITION,
                    ContentDisposition.inline().filename(originalName(filename), StandardCharsets.UTF_8).build().toString())
            .body(new FileSystemResource(file));
    }

    // GET /api/files/{filename}/download  企业端保存附件简历
    @GetMapping("/api/files/{filename:.+}/download")
    public ResponseEntity<FileSystemResource> saveToComputer(@PathVariable String filename) {
        File file = resolveStoredFile(filename);
        if (!file.exists()) return ResponseEntity.notFound().build();
        return ResponseEntity.ok()
            .contentType(detectMediaType(file.toPath()))
            .header(HttpHeaders.CONTENT_DISPOSITION,
                    ContentDisposition.attachment().filename(originalName(filename), StandardCharsets.UTF_8).build().toString())
            .body(new FileSystemResource(file));
    }

    private File resolveStoredFile(String filename) {
        // 只接受纯文件名，阻止 ../ 等路径穿越
        String clean = Paths.get(filename).getFileName().toString();
        if (!clean.equals(filename)) return new File(UPLOAD_DIR, "__invalid__");
        return new File(UPLOAD_DIR, clean);
    }

    private String originalName(String storedName) {
        int underscore = storedName.indexOf('_');
        return underscore >= 0 && underscore + 1 < storedName.length()
                ? storedName.substring(underscore + 1) : storedName;
    }

    private String getExtension(String name) {
        int dot = name.lastIndexOf('.');
        return dot < 0 ? "" : name.substring(dot + 1).toLowerCase(Locale.ROOT);
    }

    private MediaType detectMediaType(Path path) {
        String ext = getExtension(path.getFileName().toString());
        if ("pdf".equals(ext)) return MediaType.APPLICATION_PDF;
        if ("doc".equals(ext)) return MediaType.parseMediaType("application/msword");
        if ("docx".equals(ext)) {
            return MediaType.parseMediaType("application/vnd.openxmlformats-officedocument.wordprocessingml.document");
        }
        try {
            String detected = Files.probeContentType(path);
            if (detected != null) return MediaType.parseMediaType(detected);
        } catch (Exception ignored) {}
        return MediaType.APPLICATION_OCTET_STREAM;
    }
}
