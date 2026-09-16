package com.example.demo;

import com.example.demo.service.HBaseService;
import java.util.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

/** Test-only row store: every compare-and-put is atomic, including across concurrent requests. */
final class MemoryAccounts {
    private final Map<String, Map<String, String>> rows = new HashMap<>();
    MemoryAccounts(HBaseService hbase) throws Exception {
        when(hbase.getRow(anyString(), anyString(), eq("info"))).thenAnswer(call -> get(call.getArgument(0), call.getArgument(1)));
        when(hbase.compareAndPut(anyString(), anyString(), anyString(), nullable(String.class), anyMap()))
                .thenAnswer(call -> compare(call.getArgument(0), call.getArgument(1), call.getArgument(2), call.getArgument(3), call.getArgument(4)));
        doAnswer(call -> { put(call.getArgument(0), call.getArgument(1), call.getArgument(3)); return null; })
                .when(hbase).putRow(anyString(), anyString(), eq("info"), anyMap());
        when(hbase.scanAll(anyString(), eq("info"))).thenAnswer(call -> scan(call.getArgument(0)));
        when(hbase.exists(anyString(), anyString())).thenAnswer(call -> get(call.getArgument(0), call.getArgument(1)) != null);
        doAnswer(call -> { remove(call.getArgument(0), call.getArgument(1)); return null; })
                .when(hbase).deleteRow(anyString(), anyString());
    }
    synchronized Map<String, String> get(String table, String key) {
        Map<String, String> row = rows.get(table + "\n" + key);
        return row == null ? null : new HashMap<>(row);
    }
    synchronized void put(String table, String key, Map<String, String> update) {
        Map<String, String> row = rows.computeIfAbsent(table + "\n" + key, unused -> new HashMap<>());
        row.putAll(update); row.put("rowKey", key);
    }
    synchronized boolean compare(String table, String key, String column, String expected, Map<String, String> update) {
        Map<String, String> row = get(table, key);
        if (!Objects.equals(row == null ? null : row.get(column), expected)) return false;
        put(table, key, update); return true;
    }
    synchronized List<Map<String, String>> scan(String table) {
        List<Map<String, String>> result = new ArrayList<>();
        rows.forEach((key, row) -> { if (key.startsWith(table + "\n")) result.add(new HashMap<>(row)); });
        return result;
    }
    synchronized void remove(String table, String key) { rows.remove(table + "\n" + key); }
}
