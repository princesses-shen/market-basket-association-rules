package com.example.mr;

import java.io.IOException;
import org.apache.hadoop.io.IntWritable;
import org.apache.hadoop.io.Text;
import org.apache.hadoop.mapreduce.Mapper;

// Mapper: 读 TSV 每行, 输出 <city, 1>
public class CityCountMapper extends Mapper<Object, Text, Text, IntWritable> {
    private final static IntWritable ONE = new IntWritable(1);
    private Text cityKey = new Text();

    @Override
    protected void map(Object key, Text value, Context context) throws IOException, InterruptedException {
        // TSV 格式: city	job_id	title	company	...
        String line = value.toString();
        if (line.startsWith("city")) return; // skip header
        String[] parts = line.split("\t");
        if (parts.length >= 1 && !parts[0].isEmpty()) {
            cityKey.set(parts[0]);
            context.write(cityKey, ONE);
        }
    }
}
