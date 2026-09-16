package com.example.demo.security;

public class AccountException extends RuntimeException {
    public final int status;
    public AccountException(int status, String message) {
        super(message);
        this.status = status;
    }
}
