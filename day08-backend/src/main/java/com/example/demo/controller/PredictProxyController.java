package com.example.demo.controller;

import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.RestTemplate;
import org.springframework.http.*;

import java.util.*;

// 薪资预测代理: 转发到 Python 预测服务 (127.0.0.1:8788)
@RestController
@RequestMapping("/api")
public class PredictProxyController {

    private static final String PREDICT_URL = "http://127.0.0.1:8788";
    private final RestTemplate rest = new RestTemplate();

    // GET /api/predict?city=&edu=&exp=&tags=&tier=
    @GetMapping("/predict")
    public ResponseEntity<String> predict(
            @RequestParam(defaultValue = "北京") String city,
            @RequestParam(defaultValue = "本科") String edu,
            @RequestParam(defaultValue = "3-5年") String exp,
            @RequestParam(defaultValue = "Java") String tags,
            @RequestParam(defaultValue = "中大型企业") String tier) {
        try {
            String url = String.format("%s/api/predict?city=%s&edu=%s&exp=%s&tags=%s&tier=%s",
                    PREDICT_URL,
                    java.net.URLEncoder.encode(city, "UTF-8"),
                    java.net.URLEncoder.encode(edu, "UTF-8"),
                    java.net.URLEncoder.encode(exp, "UTF-8"),
                    java.net.URLEncoder.encode(tags, "UTF-8"),
                    java.net.URLEncoder.encode(tier, "UTF-8"));
            ResponseEntity<String> resp = rest.getForEntity(url, String.class);
            return ResponseEntity.ok().contentType(MediaType.APPLICATION_JSON).body(resp.getBody());
        } catch (Exception e) {
            String errJson = "{\"code\":1,\"msg\":\"预测服务不可用: " + e.getMessage().replace("\"", "'") + "\"}";
            return ResponseEntity.status(503).contentType(MediaType.APPLICATION_JSON).body(errJson);
        }
    }

    // GET /api/meta
    @GetMapping("/meta")
    public ResponseEntity<String> meta() {
        try {
            ResponseEntity<String> resp = rest.getForEntity(PREDICT_URL + "/api/meta", String.class);
            return ResponseEntity.ok().contentType(MediaType.APPLICATION_JSON).body(resp.getBody());
        } catch (Exception e) {
            String errJson = "{\"code\":1,\"msg\":\"预测服务不可用\"}";
            return ResponseEntity.status(503).contentType(MediaType.APPLICATION_JSON).body(errJson);
        }
    }

    // GET /api/overview
    @GetMapping("/overview")
    public ResponseEntity<String> overview() {
        try {
            ResponseEntity<String> resp = rest.getForEntity(PREDICT_URL + "/api/overview", String.class);
            return ResponseEntity.ok().contentType(MediaType.APPLICATION_JSON).body(resp.getBody());
        } catch (Exception e) {
            String errJson = "{\"code\":1,\"msg\":\"预测服务不可用\"}";
            return ResponseEntity.status(503).contentType(MediaType.APPLICATION_JSON).body(errJson);
        }
    }
}
