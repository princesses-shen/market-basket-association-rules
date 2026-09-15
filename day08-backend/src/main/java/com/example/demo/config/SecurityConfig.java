package com.example.demo.config;

import com.example.demo.filter.JwtAuthFilter;
import com.example.demo.util.JwtUtil;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;

// Spring Security 配置：JWT 无状态鉴权
@Configuration
@EnableWebSecurity
public class SecurityConfig {

    private final JwtUtil jwtUtil;

    public SecurityConfig(JwtUtil jwtUtil) {
        this.jwtUtil = jwtUtil;
    }

    @Bean
    public PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder();
    }

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http
            .csrf().disable()
            .cors().and()
            .sessionManagement().sessionCreationPolicy(SessionCreationPolicy.STATELESS).and()
            .authorizeRequests()
                // 静态资源放行
                .antMatchers("/", "/**/*.html", "/**/*.js", "/**/*.css",
                             "/**/*.png", "/**/*.jpg", "/**/*.ico", "/js/**", "/css/**",
                             "/uploads/**").permitAll()
                // 公开接口放行
                .antMatchers("/api/user/register", "/api/user/login",
                             "/api/company/register", "/api/company/login").permitAll()
                .antMatchers("/api/company/**", "/api/resume/**", "/api/chat/**",
                             "/api/upload").permitAll()
                .antMatchers("/api/stats/**", "/api/rules/**", "/api/job/**",
                             "/api/hello", "/api/predict", "/api/meta", "/api/overview").permitAll()
                // 其余需要登录
                .anyRequest().authenticated()
            .and()
            .addFilterBefore(new JwtAuthFilter(jwtUtil), UsernamePasswordAuthenticationFilter.class);
        return http.build();
    }
}
