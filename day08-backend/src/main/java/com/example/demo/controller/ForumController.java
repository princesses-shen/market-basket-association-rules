package com.example.demo.controller;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.core.io.ClassPathResource;
import org.springframework.web.bind.annotation.*;

import java.io.InputStream;
import java.security.Principal;
import java.security.SecureRandom;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;

/**
 * 求职咨询论坛接口（origin/main 分支的板块，合并后由 Spring Boot 承接）。
 *
 * 数据来源：classpath:forum-data.json，由 scripts/export_forum_json.py 从
 * src/serving/forum_data.py 导出。原来的 Python 版由 serve_website.py 提供同名接口，
 * 两个分支合并后网站主服务是 Spring Boot，因此这里做等价实现。
 *
 * 接口契约与原 Python 版保持一致：
 *   GET  /api/forum/categories           -> ["全部", "求职攻略", ...]
 *   GET  /api/forum/list                 -> {list, total, page, size, totalPages, categories}
 *   GET  /api/forum/detail/{id}          -> 文章对象（views 自增）
 *   GET  /api/forum/comments/{id}        -> 评论数组
 *   POST /api/forum/like/{id}            -> {success}
 *   POST /api/forum/comment/{id}         -> {success, msg, comment}
 *
 * 说明：点赞数与新增评论保存在内存里，进程重启后回到 JSON 初始值；
 * 这与原 Python 版行为一致，演示足够。若后续要落库，可改为写 HBase
 * recruit_forum_comments 表。
 */
@RestController
@RequestMapping("/api/forum")
public class ForumController {

    private static final DateTimeFormatter TIME_FORMAT =
            DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm");

    private final List<String> categories;
    private final List<Map<String, Object>> articles;
    private final Map<String, List<Map<String, Object>>> comments = new ConcurrentHashMap<>();
    private final AtomicLong commentSeq = new AtomicLong(100);
    private final SecureRandom random = new SecureRandom();

    @SuppressWarnings("unchecked")
    public ForumController() throws Exception {
        ObjectMapper mapper = new ObjectMapper();
        ClassPathResource resource = new ClassPathResource("forum-data.json");
        if (!resource.exists()) {
            // 明确报错，不要让论坛静默变成空列表
            throw new IllegalStateException(
                    "论坛数据文件 forum-data.json 缺失，请先在项目根目录执行："
                            + "python scripts/export_forum_json.py");
        }
        Map<String, Object> root;
        try (InputStream in = resource.getInputStream()) {
            root = mapper.readValue(in, new TypeReference<Map<String, Object>>() {});
        }
        this.categories = (List<String>) root.getOrDefault("categories", Collections.emptyList());
        this.articles = (List<Map<String, Object>>) root.getOrDefault("articles", new ArrayList<>());
        Map<String, List<Map<String, Object>>> seed =
                (Map<String, List<Map<String, Object>>>) root.getOrDefault("comments", new HashMap<>());
        seed.forEach((key, value) ->
                this.comments.put(key, Collections.synchronizedList(new ArrayList<>(value))));
    }

    @GetMapping("/categories")
    public List<String> categories() {
        return categories;
    }

    @GetMapping("/list")
    public Map<String, Object> list(@RequestParam(defaultValue = "全部") String category,
                                    @RequestParam(defaultValue = "") String keyword,
                                    @RequestParam(defaultValue = "1") int page,
                                    @RequestParam(defaultValue = "10") int size) {
        String kw = keyword == null ? "" : keyword.trim().toLowerCase(Locale.ROOT);
        List<Map<String, Object>> filtered = new ArrayList<>();
        for (Map<String, Object> article : articles) {
            String articleCategory = text(article.get("category"));
            if (category != null && !category.isEmpty() && !"全部".equals(category)
                    && !category.equals(articleCategory)) {
                continue;
            }
            if (!kw.isEmpty()) {
                boolean hit = text(article.get("title")).toLowerCase(Locale.ROOT).contains(kw)
                        || text(article.get("summary")).toLowerCase(Locale.ROOT).contains(kw);
                if (!hit) {
                    continue;
                }
            }
            filtered.add(article);
        }
        // 与原 Python 版一致：按发布时间倒序
        filtered.sort((left, right) ->
                text(right.get("publish_time")).compareTo(text(left.get("publish_time"))));

        int total = filtered.size();
        int safeSize = size <= 0 ? 10 : size;
        int totalPages = (total + safeSize - 1) / safeSize;
        int safePage = page <= 0 ? 1 : page;
        int from = Math.min(total, (safePage - 1) * safeSize);
        int to = Math.min(total, from + safeSize);

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("list", new ArrayList<>(filtered.subList(from, to)));
        result.put("total", total);
        result.put("page", safePage);
        result.put("size", safeSize);
        result.put("totalPages", totalPages);
        result.put("categories", categories);
        return result;
    }

    @GetMapping("/detail/{id}")
    public Map<String, Object> detail(@PathVariable String id) {
        Map<String, Object> article = find(id);
        if (article == null) {
            Map<String, Object> missing = new LinkedHashMap<>();
            missing.put("error", "文章不存在");
            return missing;
        }
        synchronized (article) {
            article.put("views", number(article.get("views")) + 1);
        }
        return article;
    }

    @GetMapping("/comments/{id}")
    public List<Map<String, Object>> comments(@PathVariable String id) {
        List<Map<String, Object>> list = comments.get(id);
        if (list == null) {
            return Collections.emptyList();
        }
        synchronized (list) {
            return new ArrayList<>(list);
        }
    }

    @PostMapping("/like/{id}")
    public Map<String, Object> like(@PathVariable String id) {
        Map<String, Object> article = find(id);
        if (article == null) {
            return single("success", false);
        }
        synchronized (article) {
            article.put("likes", number(article.get("likes")) + 1);
        }
        return single("success", true);
    }

    @PostMapping("/comment/{id}")
    public Map<String, Object> comment(@PathVariable String id,
                                       @RequestBody Map<String, String> body,
                                       Principal principal) {
        Map<String, Object> article = find(id);
        if (article == null) {
            return reply(false, "文章不存在", null);
        }
        String content = body == null || body.get("content") == null
                ? "" : body.get("content").trim();
        if (content.length() < 2) {
            return reply(false, "评论内容太短", null);
        }
        String author = principal != null && principal.getName() != null
                ? principal.getName() : "匿名用户";

        Map<String, Object> comment = new LinkedHashMap<>();
        comment.put("id", "c" + commentSeq.incrementAndGet() + random.nextInt(10));
        comment.put("author", author);
        comment.put("avatar", "😊");
        comment.put("content", content);
        comment.put("time", LocalDateTime.now().format(TIME_FORMAT));
        comment.put("likes", 0);

        List<Map<String, Object>> list =
                comments.computeIfAbsent(id, key -> Collections.synchronizedList(new ArrayList<>()));
        synchronized (list) {
            list.add(comment);
        }
        synchronized (article) {
            article.put("comments_count", number(article.get("comments_count")) + 1);
        }
        return reply(true, "评论成功", comment);
    }

    private Map<String, Object> find(String id) {
        if (id == null) {
            return null;
        }
        for (Map<String, Object> article : articles) {
            if (id.equals(article.get("id"))) {
                return article;
            }
        }
        return null;
    }

    private static String text(Object value) {
        return value == null ? "" : String.valueOf(value);
    }

    private static int number(Object value) {
        if (value instanceof Number) {
            return ((Number) value).intValue();
        }
        try {
            return Integer.parseInt(String.valueOf(value));
        } catch (RuntimeException e) {
            return 0;
        }
    }

    private static Map<String, Object> single(String key, Object value) {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put(key, value);
        return result;
    }

    private static Map<String, Object> reply(boolean success, String message, Object comment) {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("success", success);
        result.put("msg", message);
        if (comment != null) {
            result.put("comment", comment);
        }
        return result;
    }
}
