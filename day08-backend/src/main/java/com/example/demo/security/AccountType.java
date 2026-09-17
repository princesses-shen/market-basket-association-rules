package com.example.demo.security;

public enum AccountType {
    user("recruit_user", "password"), company("recruit_company", "password_hash"),
    admin("recruit_admin", "password");
    public final String table;
    public final String passwordColumn;
    AccountType(String table, String passwordColumn) {
        this.table = table;
        this.passwordColumn = passwordColumn;
    }
    public static AccountType publicType(String value) {
        if ("user".equals(value)) return user;
        if ("company".equals(value)) return company;
        throw new IllegalArgumentException("请选择用户或企业账号");
    }
}
