package com.example.demo;

import com.example.demo.security.EmailPurpose;
import com.example.demo.service.ResetMailService;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.boot.autoconfigure.mail.MailSenderAutoConfiguration;
import org.springframework.context.annotation.AnnotationConfigApplicationContext;
import org.springframework.core.io.support.ResourcePropertySource;
import org.springframework.mail.javamail.JavaMailSender;
import java.security.SecureRandom;
import java.util.Locale;
import static org.junit.jupiter.api.Assertions.*;

/** Explicit opt-in only. Sends three real messages to the configured sender's own mailbox; no HBase required. */
@EnabledIfEnvironmentVariable(named = "RUN_SMTP_INTEGRATION", matches = "true")
class QqSmtpIntegrationTest {
    @Test void qqAcceptsAllThreePurposeMessages() throws Exception {
        try (AnnotationConfigApplicationContext context = new AnnotationConfigApplicationContext()) {
            context.getEnvironment().getPropertySources().addLast(new ResourcePropertySource("classpath:application.properties"));
            context.register(MailSenderAutoConfiguration.class);
            context.refresh();
            String from = context.getEnvironment().getProperty("security.mail-from");
            assertNotNull(from, "SMTP_FROM is required");
            assertEquals("995612169@qq.com", from, "This opt-in test only sends to the approved mailbox");
            ResetMailService service = new ResetMailService(context.getBeanProvider(JavaMailSender.class), from);
            SecureRandom random = new SecureRandom();
            for (EmailPurpose purpose : EmailPurpose.values()) {
                service.send(from, String.format(Locale.ROOT, "%06d", random.nextInt(1_000_000)), purpose);
                System.out.println("SMTP accepted: " + purpose.name());
            }
            System.out.println("Inbox receipt requires mailbox owner confirmation; SMTP acceptance is not inbox verification.");
        }
    }
}
