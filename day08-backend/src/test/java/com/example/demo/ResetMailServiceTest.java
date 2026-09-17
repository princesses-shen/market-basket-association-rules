package com.example.demo;

import com.example.demo.security.AccountException;
import com.example.demo.security.EmailPurpose;
import com.example.demo.service.ResetMailService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.mail.MailSendException;
import org.springframework.mail.SimpleMailMessage;
import org.springframework.mail.javamail.JavaMailSender;
import org.springframework.mail.javamail.JavaMailSenderImpl;
import org.mockito.ArgumentCaptor;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class ResetMailServiceTest {
    @SuppressWarnings("unchecked")
    @Test void everyPurposeHasItsOwnChineseSubjectAndBody() {
        ObjectProvider<JavaMailSender> provider = mock(ObjectProvider.class);
        JavaMailSender sender = mock(JavaMailSender.class);
        when(provider.getIfAvailable()).thenReturn(sender); when(provider.getObject()).thenReturn(sender);
        ResetMailService service = new ResetMailService(provider, "sender@example.com");
        for (EmailPurpose purpose : EmailPurpose.values()) service.send("user@example.com", "123456", purpose);
        ArgumentCaptor<SimpleMailMessage> messages = ArgumentCaptor.forClass(SimpleMailMessage.class);
        verify(sender, times(3)).send(messages.capture());
        for (int i = 0; i < EmailPurpose.values().length; i++) {
            assertTrue(messages.getAllValues().get(i).getSubject().contains(EmailPurpose.values()[i].title));
            assertTrue(messages.getAllValues().get(i).getText().contains("10 分钟"));
        }
    }
    @SuppressWarnings("unchecked")
    @Test void missingCredentialsOrMismatchedSenderFailBeforeNetworkAccess() {
        ObjectProvider<JavaMailSender> provider = mock(ObjectProvider.class);
        JavaMailSenderImpl sender = new JavaMailSenderImpl();
        when(provider.getIfAvailable()).thenReturn(sender);
        ResetMailService service = new ResetMailService(provider, "sender@example.com");
        assertThrows(AccountException.class, service::requireAvailable);
        sender.setHost("smtp.qq.com"); sender.setUsername("sender@example.com");
        assertThrows(AccountException.class, service::requireAvailable);
        sender.setPassword("test-only"); service.requireAvailable();
        sender.setUsername("other@example.com");
        assertThrows(AccountException.class, service::requireAvailable);
    }
    @SuppressWarnings("unchecked")
    @Test void missingSmtpOrSenderIsAnExplicitServiceError() {
        ObjectProvider<JavaMailSender> provider = mock(ObjectProvider.class);
        assertEquals(503, assertThrows(AccountException.class,
                () -> new ResetMailService(provider, "").send("user@example.com", "123456")).status);
        assertEquals(503, assertThrows(AccountException.class,
                () -> new ResetMailService(provider, "sender@example.com").requireAvailable()).status);
    }
    @SuppressWarnings("unchecked")
    @Test void realMailAdapterUsesConfiguredSenderAndPropagatesDeliveryFailure() {
        ObjectProvider<JavaMailSender> provider = mock(ObjectProvider.class);
        JavaMailSender sender = mock(JavaMailSender.class);
        when(provider.getIfAvailable()).thenReturn(sender); when(provider.getObject()).thenReturn(sender);
        ResetMailService service = new ResetMailService(provider, "sender@example.com");
        service.send("user@example.com", "654321");
        ArgumentCaptor<SimpleMailMessage> message = ArgumentCaptor.forClass(SimpleMailMessage.class);
        verify(sender).send(message.capture());
        assertEquals("sender@example.com", message.getValue().getFrom());
        assertArrayEquals(new String[]{"user@example.com"}, message.getValue().getTo());
        assertTrue(message.getValue().getText().contains("654321"));
        doThrow(new MailSendException("SMTP down")).when(sender).send(any(SimpleMailMessage.class));
        assertEquals(503, assertThrows(AccountException.class, () -> service.send("user@example.com", "000000")).status);
    }
}
