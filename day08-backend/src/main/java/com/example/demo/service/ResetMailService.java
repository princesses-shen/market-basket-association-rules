package com.example.demo.service;

import com.example.demo.security.AccountException;
import com.example.demo.security.EmailPurpose;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.mail.SimpleMailMessage;
import org.springframework.mail.javamail.JavaMailSender;
import org.springframework.mail.javamail.JavaMailSenderImpl;
import org.springframework.stereotype.Service;

@Service
public class ResetMailService {
    private final ObjectProvider<JavaMailSender> provider;
    private final String from;
    public ResetMailService(ObjectProvider<JavaMailSender> provider, @Value("${security.mail-from:}") String from) {
        this.provider = provider;
        this.from = from;
    }
    public void requireAvailable() {
        JavaMailSender sender = provider.getIfAvailable();
        if (from.isBlank() || sender == null)
            throw new AccountException(503, "邮件服务未配置，请联系管理员");
        if (sender instanceof JavaMailSenderImpl) {
            JavaMailSenderImpl configured = (JavaMailSenderImpl) sender;
            if (configured.getHost() == null || configured.getHost().isBlank()
                    || configured.getUsername() == null || configured.getUsername().isBlank()
                    || configured.getPassword() == null || configured.getPassword().isBlank()
                    || !from.equalsIgnoreCase(configured.getUsername()))
                throw new AccountException(503, "邮件服务配置不完整，请联系管理员");
        }
    }
    public void send(String email, String code) {
        send(email, code, EmailPurpose.RESET);
    }
    public void send(String email, String code, EmailPurpose purpose) {
        requireAvailable();
        SimpleMailMessage message = new SimpleMailMessage();
        message.setFrom(from);
        message.setTo(email);
        message.setSubject("智聘 · " + purpose.title);
        message.setText("您的" + purpose.title + "为：" + code + "，10 分钟内有效，仅限本次用途使用。"
                + "请勿向他人泄露验证码。如非本人操作，请忽略此邮件。");
        try { provider.getObject().send(message); }
        catch (RuntimeException e) { throw new AccountException(503, "邮件发送失败，请稍后重试"); }
    }
}
