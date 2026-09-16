package com.example.demo.util;

import com.example.demo.security.AccountType;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.SignatureAlgorithm;
import io.jsonwebtoken.security.Keys;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import javax.crypto.Mac;
import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.util.Base64;
import java.util.Date;

@Component
public class JwtUtil {
    private final SecretKey key;
    private static final long EXPIRE_MS = 24 * 60 * 60 * 1000L;
    public JwtUtil(@Value("${security.jwt-secret}") String secret) {
        if (secret == null || secret.getBytes(StandardCharsets.UTF_8).length < 32)
            throw new IllegalArgumentException("JWT_SECRET 必须配置为至少 32 字节的随机私有密钥");
        key = Keys.hmacShaKeyFor(secret.getBytes(StandardCharsets.UTF_8));
    }
    public String generateToken(String username, AccountType type, long version) {
        return Jwts.builder().setSubject(username).claim("accountType", type.name())
                .claim("role", type.name()).claim("version", version)
                .setIssuedAt(new Date()).setExpiration(new Date(System.currentTimeMillis() + EXPIRE_MS))
                .signWith(key, SignatureAlgorithm.HS256).compact();
    }
    public Claims validateToken(String token) {
        try {
            return Jwts.parserBuilder().setSigningKey(key).build().parseClaimsJws(token).getBody();
        } catch (RuntimeException e) { return null; }
    }
    // Keyed digest prevents offline enumeration of a six-digit code from database contents.
    public String codeDigest(String value) {
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(key);
            return Base64.getEncoder().encodeToString(mac.doFinal(value.getBytes(StandardCharsets.UTF_8)));
        } catch (Exception e) { throw new IllegalStateException("验证码摘要服务不可用", e); }
    }
}
