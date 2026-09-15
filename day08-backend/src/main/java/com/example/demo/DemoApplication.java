package com.example.demo;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

// @SpringBootApplication = 自动配置 + 组件扫描 + 配置类，一个注解让应用自举
@SpringBootApplication
public class DemoApplication {
    public static void main(String[] args) {
        // 这一行就启动了整个内嵌 Tomcat + 所有 Bean + 路由
        SpringApplication.run(DemoApplication.class, args);
    }
}
