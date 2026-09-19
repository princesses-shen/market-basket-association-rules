package com.example.demo.service;

import com.example.demo.security.AccountException;
import org.springframework.stereotype.Service;
import java.time.Clock;
import java.util.*;
import java.util.stream.Collectors;

@Service
public class AnnouncementService {
    public static final String TABLE = "recruit_announcement";
    private final HBaseService hbase;
    private final Clock clock;
    public AnnouncementService(HBaseService hbase, Clock clock) { this.hbase = hbase; this.clock = clock; }

    public Map<String, Object> list(String pageValue, String sizeValue) throws Exception {
        int page = positive(pageValue, Integer.MAX_VALUE), size = positive(sizeValue, 50);
        List<Map<String, String>> rows = hbase.scanAll(TABLE, "info");
        rows.sort(Comparator.<Map<String, String>>comparingLong(row -> Long.parseLong(row.get("publishedAt")))
                .thenComparing(row -> row.get("rowKey")).reversed());
        long start = (long) (page - 1) * size;
        List<Map<String, String>> items = rows.stream().skip(start).limit(size)
                .map(row -> publicItem(row, false)).collect(Collectors.toList());
        return Map.of("code", 0, "items", items, "total", rows.size(), "page", page, "size", size);
    }

    public Map<String, String> detail(String id) throws Exception { return publicItem(require(id), true); }

    public synchronized Map<String, String> create(Map<String, Object> body, String author) throws Exception {
        Map<String, String> row = content(body);
        String id = UUID.randomUUID().toString(), now = Long.toString(clock.millis());
        row.put("author", author); row.put("publishedAt", now); row.put("updatedAt", now);
        hbase.putRow(TABLE, id, "info", row);
        row.put("rowKey", id);
        return publicItem(row, true);
    }

    public synchronized Map<String, String> update(String id, Map<String, Object> body) throws Exception {
        Map<String, String> values = content(body), row = require(id);
        row.putAll(values); row.put("updatedAt", Long.toString(clock.millis()));
        Map<String, String> stored = new HashMap<>(row); stored.remove("rowKey");
        hbase.putRow(TABLE, id, "info", stored);
        return publicItem(row, true);
    }

    public synchronized void delete(String id) throws Exception { require(id); hbase.deleteRow(TABLE, id); }

    private Map<String, String> require(String id) throws Exception {
        Map<String, String> row = hbase.getRow(TABLE, id, "info");
        if (row == null) throw new AccountException(404, "公告不存在或已删除");
        return row;
    }
    private static Map<String, String> publicItem(Map<String, String> row, boolean withBody) {
        Map<String, String> item = new LinkedHashMap<>();
        item.put("id", row.get("rowKey")); item.put("title", row.get("title"));
        if (withBody) item.put("body", row.get("body"));
        item.put("author", "管理员"); item.put("publishedAt", row.get("publishedAt")); item.put("updatedAt", row.get("updatedAt"));
        return item;
    }
    private static Map<String, String> content(Map<String, Object> body) {
        if (body == null) throw new IllegalArgumentException("标题和正文不能为空");
        Map<String, String> values = new HashMap<>();
        values.put("title", text(body.get("title"), 100, "标题"));
        values.put("body", text(body.get("body"), 10000, "正文"));
        return values;
    }
    // Use Unicode code points and the same whitespace set as Python str.strip().
    private static boolean whitespace(int cp) { return Character.isWhitespace(cp) || Character.isSpaceChar(cp) || cp == 0x85; }
    private static String text(Object value, int max, String name) {
        if (!(value instanceof String)) throw new IllegalArgumentException(name + "必须为文本");
        String s = (String) value;
        int start = 0, end = s.length();
        while (start < end && whitespace(s.codePointAt(start))) start += Character.charCount(s.codePointAt(start));
        while (end > start && whitespace(s.codePointBefore(end))) end -= Character.charCount(s.codePointBefore(end));
        s = s.substring(start, end);
        if (s.codePoints().anyMatch(cp -> cp >= 0xD800 && cp <= 0xDFFF)) throw new IllegalArgumentException("文本编码不正确");
        if (s.isEmpty() || s.codePointCount(0, s.length()) > max) throw new IllegalArgumentException(name + "须为 1–" + max + " 字");
        return s;
    }
    private static int positive(String value, int max) {
        try {
            if (value == null || !value.matches("[0-9]{1,10}")) throw new NumberFormatException();
            int n = Integer.parseInt(value);
            if (n < 1 || n > max) throw new NumberFormatException();
            return n;
        } catch (NumberFormatException e) { throw new IllegalArgumentException("分页参数不正确"); }
    }
}
