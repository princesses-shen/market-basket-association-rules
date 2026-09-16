package com.example.demo.config;

import com.example.demo.filter.JwtAuthFilter;
import com.example.demo.service.HBaseService;
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
import java.time.Clock;

@Configuration
@EnableWebSecurity
public class SecurityConfig {
    @Bean public PasswordEncoder passwordEncoder() { return new BCryptPasswordEncoder(); }
    @Bean public Clock clock() { return Clock.systemUTC(); }
    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http, JwtUtil jwt, HBaseService hbase) throws Exception {
        http.csrf().disable().cors().and()
            .sessionManagement().sessionCreationPolicy(SessionCreationPolicy.STATELESS).and()
            .exceptionHandling()
                .authenticationEntryPoint((req, resp, e) -> JwtAuthFilter.error(resp, 401, "请先登录"))
                .accessDeniedHandler((req, resp, e) -> JwtAuthFilter.error(resp, 403, "无权访问该资源")).and()
            .authorizeRequests()
                .antMatchers("/api/user/register", "/api/user/login", "/api/company/register", "/api/company/login",
                        "/api/admin/login", "/api/auth/password-reset/code", "/api/auth/password-reset/confirm",
                        "/api/auth/register/code", "/api/auth/email-login/code", "/api/auth/email-login/confirm").permitAll()
                .antMatchers("/api/admin/**").hasRole("ADMIN")
                .antMatchers("/api/company/**").hasRole("COMPANY")
                .antMatchers("/api/user/**", "/api/resume/save", "/api/chat/apply", "/api/chat/my-applications",
                        "/api/upload").hasRole("USER")
                .antMatchers("/api/resume/list", "/api/chat/applications", "/api/chat/talent/**").hasRole("COMPANY")
                .antMatchers("/api/resume/**", "/api/chat/**", "/uploads/**").hasAnyRole("USER", "COMPANY")
                .antMatchers("/api/stats/**", "/api/rules/**", "/api/job/**", "/api/hello", "/api/predict",
                        "/api/meta", "/api/overview").permitAll()
                // Protect APIs before allowing static file extensions.
                .antMatchers("/api/**").authenticated()
                .antMatchers("/", "/error", "/**/*.html", "/**/*.js", "/**/*.css", "/**/*.png", "/**/*.jpg",
                        "/**/*.ico", "/js/**", "/css/**").permitAll()
                .anyRequest().authenticated().and()
            .addFilterBefore(new JwtAuthFilter(jwt, hbase), UsernamePasswordAuthenticationFilter.class);
        return http.build();
    }
}
