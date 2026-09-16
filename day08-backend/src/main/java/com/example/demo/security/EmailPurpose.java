package com.example.demo.security;

public enum EmailPurpose {
    REGISTER("注册邮箱验证"), LOGIN("登录验证码"), RESET("找回密码验证码");
    public final String title;
    EmailPurpose(String title) { this.title = title; }
}
