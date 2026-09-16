package com.example.demo.service;

import org.apache.hadoop.conf.Configuration;
import org.apache.hadoop.hbase.HBaseConfiguration;
import org.apache.hadoop.hbase.TableName;
import org.apache.hadoop.hbase.client.*;
import org.apache.hadoop.hbase.client.Delete;
import org.apache.hadoop.hbase.util.Bytes;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import javax.annotation.PreDestroy;
import java.util.*;

// HBase 数据访问层：连接复用 + scan/get/put
@Service
public class HBaseService {

    private final Connection connection;

    public HBaseService(@Value("${hbase.zookeeper.quorum}") String zk,
                       @Value("${hbase.zookeeper.property.clientPort:2181}") String port)
            throws Exception {
        Configuration conf = HBaseConfiguration.create();
        conf.set("hbase.zookeeper.quorum", zk);
        conf.set("hbase.zookeeper.property.clientPort", port);
        connection = ConnectionFactory.createConnection(conf);
    }

    // 扫表，返回 Map<RowKey, 某列值>（给饼图/词云用）
    public Map<String, String> scan(String table, String cf, String col) throws Exception {
        Map<String, String> result = new HashMap<>();
        try (Table t = connection.getTable(TableName.valueOf(table));
             ResultScanner rs = t.getScanner(new Scan())) {
            for (Result r : rs) {
                String v = Bytes.toString(r.getValue(Bytes.toBytes(cf), Bytes.toBytes(col)));
                if (v != null) {
                    result.put(Bytes.toString(r.getRow()), v);
                }
            }
        }
        return result;
    }

    // 扫表，按 RowKey 排序后返回值列表（给趋势图用）
    public List<String> scanList(String table, String cf, String col) throws Exception {
        Map<String, String> ordered = new TreeMap<>();
        try (Table t = connection.getTable(TableName.valueOf(table));
             ResultScanner rs = t.getScanner(new Scan())) {
            for (Result r : rs) {
                String v = Bytes.toString(r.getValue(Bytes.toBytes(cf), Bytes.toBytes(col)));
                if (v != null) {
                    ordered.put(Bytes.toString(r.getRow()), v);
                }
            }
        }
        return new ArrayList<>(ordered.values());
    }

    // 扫表，返回全部列的 List<Map>（给规则表/岗位表用）
    public List<Map<String, String>> scanAll(String table, String cf) throws Exception {
        List<Map<String, String>> list = new ArrayList<>();
        try (Table t = connection.getTable(TableName.valueOf(table));
             ResultScanner rs = t.getScanner(new Scan())) {
            for (Result r : rs) {
                Map<String, String> row = new HashMap<>();
                row.put("rowKey", Bytes.toString(r.getRow()));
                NavigableMap<byte[],NavigableMap<byte[],byte[]>> families = r.getNoVersionMap();
                if (families != null) {
                    NavigableMap<byte[],byte[]> cols = families.get(Bytes.toBytes(cf));
                    if (cols != null) {
                        for (Map.Entry<byte[],byte[]> e : cols.entrySet()) {
                            row.put(Bytes.toString(e.getKey()), Bytes.toString(e.getValue()));
                        }
                    }
                }
                list.add(row);
            }
        }
        return list;
    }

    // 获取一行所有列（给岗位详情/用户信息用）
    public Map<String, String> getRow(String table, String rowKey, String cf) throws Exception {
        try (Table t = connection.getTable(TableName.valueOf(table))) {
            Get g = new Get(Bytes.toBytes(rowKey));
            Result r = t.get(g);
            if (r == null || r.isEmpty()) return null;
            Map<String, String> row = new HashMap<>();
            row.put("rowKey", rowKey);
            NavigableMap<byte[],NavigableMap<byte[],byte[]>> families = r.getNoVersionMap();
            if (families != null) {
                NavigableMap<byte[],byte[]> cols = families.get(Bytes.toBytes(cf));
                if (cols != null) {
                    for (Map.Entry<byte[],byte[]> e : cols.entrySet()) {
                        row.put(Bytes.toString(e.getKey()), Bytes.toString(e.getValue()));
                    }
                }
            }
            return row;
        }
    }

    // 写入一行多列（给注册用）
    public void putRow(String table, String rowKey, String cf, Map<String,String> data) throws Exception {
        try (Table t = connection.getTable(TableName.valueOf(table))) {
            Put p = new Put(Bytes.toBytes(rowKey));
            for (Map.Entry<String,String> e : data.entrySet()) {
                p.addColumn(Bytes.toBytes(cf), Bytes.toBytes(e.getKey()), Bytes.toBytes(e.getValue()));
            }
            t.put(p);
        }
    }

    public boolean compareAndPut(String table, String rowKey, String column, String expected,
                                 Map<String, String> data) throws Exception {
        byte[] row = Bytes.toBytes(rowKey);
        byte[] cf = Bytes.toBytes("info");
        try (Table t = connection.getTable(TableName.valueOf(table))) {
            Put put = new Put(row);
            data.forEach((key, value) -> put.addColumn(cf, Bytes.toBytes(key), Bytes.toBytes(value)));
            Table.CheckAndMutateBuilder check = t.checkAndMutate(row, cf).qualifier(Bytes.toBytes(column));
            return (expected == null ? check.ifNotExists() : check.ifEquals(Bytes.toBytes(expected))).thenPut(put);
        }
    }

    public void ensureTable(String table) throws Exception {
        try (Admin admin = connection.getAdmin()) {
            TableName name = TableName.valueOf(table);
            if (!admin.tableExists(name)) {
                try {
                    admin.createTable(TableDescriptorBuilder.newBuilder(name)
                            .setColumnFamily(ColumnFamilyDescriptorBuilder.of("info")).build());
                } catch (org.apache.hadoop.hbase.TableExistsException ignored) {
                    // Another instance may have initialized the table concurrently.
                }
            }
        }
    }

    // 检查行是否存在（给注册验重用）
    public boolean exists(String table, String rowKey) throws Exception {
        try (Table t = connection.getTable(TableName.valueOf(table))) {
            Get g = new Get(Bytes.toBytes(rowKey));
            return t.exists(g);
        }
    }

    // 删除一行（给人才库删除用）
    public void deleteRow(String table, String rowKey) throws Exception {
        try (Table t = connection.getTable(TableName.valueOf(table))) {
            Delete d = new Delete(Bytes.toBytes(rowKey));
            t.delete(d);
        }
    }

    // 岗位搜索：全表 scan 后 Java 端过滤（1200 行足够快）
    public List<Map<String,String>> scanJobs(String city, int salMin, int salMax,
                                             String keyword, String category, String edu, int limit) throws Exception {
        List<Map<String,String>> all = scanAll("recruit_job", "info");
        List<Map<String,String>> filtered = new ArrayList<>();
        for (Map<String,String> job : all) {
            if (city != null && !city.isEmpty() && !city.equals("全部")
                    && !city.equals(job.get("city"))) continue;
            if (category != null && !category.isEmpty() && !category.equals("全部")
                    && !category.equals(job.get("category"))) continue;
            if (edu != null && !edu.isEmpty() && !edu.equals("全部")
                    && !edu.equals(job.get("edu"))) continue;
            if (keyword != null && !keyword.isEmpty()) {
                String title = job.getOrDefault("title", "");
                String company = job.getOrDefault("company", "");
                String tags = job.getOrDefault("tags", "");
                String match = title + company + tags;
                if (!match.contains(keyword)) continue;
            }
            try {
                int low = Integer.parseInt(job.getOrDefault("salary_low","0"));
                int high = Integer.parseInt(job.getOrDefault("salary_high","0"));
                if (salMin > 0 && high < salMin) continue;
                if (salMax > 0 && low > salMax) continue;
            } catch (NumberFormatException ignored) {}
            filtered.add(job);
        }
        // 按发布时间倒序
        filtered.sort((a,b) -> {
            String ta = a.getOrDefault("publish_time","");
            String tb = b.getOrDefault("publish_time","");
            return tb.compareTo(ta);
        });
        if (limit > 0 && filtered.size() > limit) {
            return new ArrayList<>(filtered.subList(0, limit));
        }
        return filtered;
    }

    @PreDestroy
    public void close() {
        try {
            if (connection != null) connection.close();
        } catch (Exception ignored) {
        }
    }
}
