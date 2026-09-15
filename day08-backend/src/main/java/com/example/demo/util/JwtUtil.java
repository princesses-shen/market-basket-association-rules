package com.example.demo.util;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.SignatureAlgorithm;
import io.jsonwebtoken.security.Keys;
import org.springframework.stereotype.Component;

import javax.crypto.SecretKey;
import java.util.Date;

// JWT 工具：生成/验证/解析 token
@Component
public class JwtUtil {

    // 硬编码密钥（课程项目，够用）
    private static final SecretKey KEY = Keys.hmacShaKeyFor(
            "RecruitWebSecretKey2026ForJwtAuthMustBe32Bytes!!".getBytes());
    private static final long EXPIRE_MS = 24 * 60 * 60 * 1000L; // 24小时

    // 生成 token
    public String generateToken(String username) {
        return Jwts.builder()
                .setSubject(username)
                .setIssuedAt(new Date())
                .setExpiration(new Date(System.currentTimeMillis() + EXPIRE_MS))
                .signWith(KEY, SignatureAlgorithm.HS256)
                .compact();
    }

    // 验证并解析
    public Claims validateToken(String token) {
        try {
            return Jwts.parserBuilder()
                    .setSigningKey(KEY)
                    .build()
                    .parseClaimsJws(token)
                    .getBody();
        } catch (Exception e) {
            return null;
        }
    }

    // 提取用户名
    public String extractUsername(String token) {
        Claims c = validateToken(token);
        return c != null ? c.getSubject() : null;
    }
}
