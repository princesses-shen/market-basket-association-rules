package com.example.demo.controller;

import com.example.demo.security.AccountException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.bind.MissingServletRequestParameterException;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;
import java.util.Map;

@RestControllerAdvice(assignableTypes = {AccountController.class, UserController.class, CompanyController.class,
        ResumeController.class, ChatController.class, FileController.class})
public class AccountErrorHandler {
    private static final Logger log = LoggerFactory.getLogger(AccountErrorHandler.class);
    @ExceptionHandler(AccountException.class)
    public ResponseEntity<?> account(AccountException e) { return error(e.status, e.getMessage()); }
    @ExceptionHandler({IllegalArgumentException.class, MissingServletRequestParameterException.class,
            HttpMessageNotReadableException.class, MethodArgumentTypeMismatchException.class})
    public ResponseEntity<?> invalid(Exception e) {
        return error(400, e instanceof IllegalArgumentException && !(e instanceof MethodArgumentTypeMismatchException)
                ? e.getMessage() : "请求参数不正确");
    }
    @ExceptionHandler(AccessDeniedException.class)
    public ResponseEntity<?> forbidden(AccessDeniedException e) { return error(403, "无权访问该资源"); }
    @ExceptionHandler(Exception.class)
    public ResponseEntity<?> unavailable(Exception e) {
        // Never return database configuration, password/code contents, or stack traces to the browser.
        log.error("Account/business request failed ({})", e.getClass().getSimpleName());
        return error(503, "服务暂时不可用，请稍后重试");
    }
    private ResponseEntity<?> error(int status, String message) {
        return ResponseEntity.status(status).body(Map.of("code", status, "msg", message));
    }
}
