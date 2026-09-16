package com.example.demo.config;

import com.example.demo.service.AccountSecurityService;
import com.example.demo.service.HBaseService;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;
import java.util.Map;
import java.util.UUID;

@Component
public class AccountInitializer implements ApplicationRunner {
    private final HBaseService hbase;
    private final PasswordEncoder encoder;
    private final String initialPassword;
    public AccountInitializer(HBaseService hbase, PasswordEncoder encoder,
                              @Value("${security.admin-initial-password:123456}") String initialPassword) {
        this.hbase = hbase; this.encoder = encoder; this.initialPassword = initialPassword;
    }
    @Override
    public void run(ApplicationArguments args) throws Exception {
        for (String table : new String[]{"recruit_user", "recruit_company", "recruit_admin", "recruit_upload", "recruit_email_code"})
            hbase.ensureTable(table);
        Map<String, String> existing = hbase.getRow("recruit_admin", "lihuanshen123", "info");
        if (existing != null && existing.containsKey("password")) return;
        AccountSecurityService.validatePassword(initialPassword);
        hbase.compareAndPut("recruit_admin", "lihuanshen123", "password", null,
                Map.of("password", encoder.encode(initialPassword), "email", "995612169@qq.com",
                        "role", "admin", "credential_version", "0", "security_revision", UUID.randomUUID().toString()));
    }
}
