package com.example.demo.filter;

import com.example.demo.security.AccountType;
import com.example.demo.service.AccountSecurityService;
import com.example.demo.service.HBaseService;
import com.example.demo.util.JwtUtil;
import io.jsonwebtoken.Claims;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.filter.OncePerRequestFilter;
import javax.servlet.FilterChain;
import javax.servlet.ServletException;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.*;

public class JwtAuthFilter extends OncePerRequestFilter {
    private final JwtUtil jwt;
    private final HBaseService hbase;
    public JwtAuthFilter(JwtUtil jwt, HBaseService hbase) { this.jwt = jwt; this.hbase = hbase; }
    @Override
    protected void doFilterInternal(HttpServletRequest req, HttpServletResponse resp, FilterChain chain)
            throws ServletException, IOException {
        String header = req.getHeader("Authorization");
        if (header != null) {
            Claims claims = header.startsWith("Bearer ") ? jwt.validateToken(header.substring(7)) : null;
            AccountType type;
            try {
                if (claims == null || claims.getSubject() == null || !(claims.get("version") instanceof Number))
                    throw new IllegalArgumentException();
                type = AccountType.valueOf(claims.get("accountType", String.class));
                if (!type.name().equals(claims.get("role"))) throw new IllegalArgumentException();
            } catch (RuntimeException e) { error(resp, 401, "登录已失效，请重新登录"); return; }
            Map<String, String> row;
            try { row = hbase.getRow(type.table, claims.getSubject(), "info"); }
            catch (Exception e) { error(resp, 503, "账号服务暂时不可用，请稍后重试"); return; }
            try {
                if (row == null || AccountSecurityService.blocked(row)
                        || AccountSecurityService.number(row, "credential_version") != ((Number) claims.get("version")).longValue()) {
                    error(resp, 401, row != null && AccountSecurityService.blocked(row)
                            ? "账号已封禁，请联系管理员解封" : "登录已失效，请重新登录"); return;
                }
            } catch (RuntimeException e) { error(resp, 503, "账号服务暂时不可用，请稍后重试"); return; }
            SecurityContextHolder.getContext().setAuthentication(new UsernamePasswordAuthenticationToken(
                    claims.getSubject(), null, Collections.singletonList(
                    new SimpleGrantedAuthority("ROLE_" + type.name().toUpperCase(Locale.ROOT)))));
        }
        chain.doFilter(req, resp);
    }
    public static void error(HttpServletResponse response, int status, String message) throws IOException {
        response.setStatus(status);
        response.setContentType("application/json;charset=UTF-8");
        response.getWriter().write("{\"code\":" + status + ",\"msg\":\"" + message + "\"}");
    }
}
