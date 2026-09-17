package com.example.demo;

import com.example.demo.config.AccountInitializer;
import com.example.demo.security.*;
import com.example.demo.service.*;
import com.example.demo.util.JwtUtil;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.ResultActions;
import java.time.Clock;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicLong;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import static org.mockito.ArgumentMatchers.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest(properties = "security.jwt-secret=test-only-random-secret-with-at-least-32-bytes")
@AutoConfigureMockMvc
class AccountSecurityTest {
    @MockBean HBaseService hbase;
    @MockBean ResetMailService mail;
    @MockBean Clock clock;
    @Autowired AccountSecurityService accounts;
    @Autowired PasswordResetService reset;
    @Autowired EmailAuthService emailAuth;
    @Autowired PasswordEncoder encoder;
    @Autowired AccountInitializer initializer;
    @Autowired JwtUtil jwt;
    @Autowired MockMvc mvc;
    @Autowired ObjectMapper json;
    MemoryAccounts store;
    AtomicLong now;
    volatile String lastCode;

    @BeforeEach void setup() throws Exception {
        reset(hbase, mail, clock);
        store = new MemoryAccounts(hbase);
        now = new AtomicLong(1_800_000_000_000L);
        when(clock.millis()).thenAnswer(call -> now.get());
        doAnswer(call -> { lastCode = call.getArgument(1); return null; }).when(mail).send(anyString(), anyString());
        doAnswer(call -> { lastCode = call.getArgument(1); return null; }).when(mail).send(anyString(), anyString(), any(EmailPurpose.class));
        initializer.run(null);
        create(AccountType.user, "alice"); create(AccountType.company, "acme");
    }
    void create(AccountType type, String name) throws Exception {
        accounts.register(type, name, "123456", name + "@example.com", Map.of("company_name", name, "nickname", name));
    }
    String token(AccountType type, String name) throws Exception {
        return (String) accounts.login(type, name, "123456").get("token");
    }
    AccountException wrong(AccountType type, String name) {
        return assertThrows(AccountException.class, () -> accounts.login(type, name, "wrong"));
    }
    void block(AccountType type, String name) { for (int i = 0; i < 5; i++) wrong(type, name); }
    ResultActions postJson(String path, Object body, String token) throws Exception {
        return mvc.perform(post(path).contentType("application/json").content(json.writeValueAsBytes(body))
                .header("Authorization", token == null ? "" : "Bearer " + token));
    }
    ResultActions publicPost(String path, Object body) throws Exception {
        return mvc.perform(post(path).contentType("application/json").content(json.writeValueAsBytes(body)));
    }

    @Test void threeRolesLoginWithSignedTypeAndVersion() throws Exception {
        for (AccountType type : AccountType.values()) {
            String name = type == AccountType.user ? "alice" : type == AccountType.company ? "acme" : "lihuanshen123";
            publicPost("/api/" + type + "/login", Map.of("username", name, "password", "123456"))
                    .andExpect(status().isOk()).andExpect(jsonPath("$.role").value(type.name()))
                    .andExpect(jsonPath("$.token").isString());
            io.jsonwebtoken.Claims claims = jwt.validateToken(token(type, name));
            assertEquals(type.name(), claims.get("accountType")); assertEquals(0, ((Number) claims.get("version")).intValue());
        }
    }
    @Test void fifthFailureBlocksAndRevokesTokensThenUnlockRequiresNewLogin() throws Exception {
        for (AccountType type : Arrays.asList(AccountType.user, AccountType.company)) {
            String name = type == AccountType.user ? "alice" : "acme";
            String old = token(type, name);
            for (int i = 0; i < 4; i++) assertEquals(401, wrong(type, name).status);
            assertEquals(423, wrong(type, name).status);
            assertEquals(423, assertThrows(AccountException.class, () -> token(type, name)).status);
            String endpoint = type == AccountType.user ? "/api/user/profile" : "/api/company/jobs";
            mvc.perform(get(endpoint).header("Authorization", "Bearer " + old)).andExpect(status().isUnauthorized());
            accounts.unlock(type, name, "lihuanshen123");
            mvc.perform(get(endpoint).header("Authorization", "Bearer " + old)).andExpect(status().isUnauthorized());
            mvc.perform(get(endpoint).header("Authorization", "Bearer " + token(type, name))).andExpect(status().isOk());
            Map<String, String> row = store.get(type.table, name);
            assertEquals("0", row.get("failed_attempts"));
            assertTrue(row.entrySet().stream().anyMatch(e -> e.getKey().startsWith("unlock_audit_") && e.getValue().startsWith("lihuanshen123|")));
        }
    }
    @Test void successClearsFailuresAndSameNameAccountsAreIndependent() throws Exception {
        create(AccountType.company, "alice");
        wrong(AccountType.user, "alice"); wrong(AccountType.user, "alice");
        token(AccountType.user, "alice");
        assertEquals("0", store.get("recruit_user", "alice").get("failed_attempts"));
        block(AccountType.user, "alice");
        assertNotNull(token(AccountType.company, "alice"));
    }
    @Test void concurrentFailuresDoNotLoseCountsOrUnblock() throws Exception {
        ExecutorService pool = Executors.newFixedThreadPool(8);
        try {
            CountDownLatch start = new CountDownLatch(1);
            List<Future<Integer>> futures = new ArrayList<>();
            for (int i = 0; i < 12; i++) futures.add(pool.submit(() -> { start.await(); return wrong(AccountType.user, "alice").status; }));
            start.countDown();
            int unauthorized = 0;
            for (Future<Integer> future : futures) if (future.get(20, TimeUnit.SECONDS) == 401) unauthorized++;
            assertEquals(4, unauthorized);
            assertEquals("5", store.get("recruit_user", "alice").get("failed_attempts"));
            assertEquals("true", store.get("recruit_user", "alice").get("blocked"));
        } finally { pool.shutdownNow(); }
    }
    @Test void missingAccountsAndDatabaseFailuresNeverCountAsWrongPasswords() throws Exception {
        wrong(AccountType.user, "missing"); assertNull(store.get("recruit_user", "missing"));
        when(hbase.getRow("recruit_user", "alice", "info")).thenThrow(new java.io.IOException("database down"));
        publicPost("/api/user/login", Map.of("username", "alice", "password", "123456"))
                .andExpect(status().isServiceUnavailable()).andExpect(jsonPath("$.msg").value("服务暂时不可用，请稍后重试"));
        assertEquals("0", store.get("recruit_user", "alice").get("failed_attempts"));
    }
    @Test void adminIsNotLockedAndInitializationNeverReplacesPassword() throws Exception {
        for (int i = 0; i < 7; i++) assertEquals(401, wrong(AccountType.admin, "lihuanshen123").status);
        String password = encoder.encode("changed-password");
        store.put("recruit_admin", "lihuanshen123", Map.of("password", password));
        initializer.run(null);
        assertEquals(password, store.get("recruit_admin", "lihuanshen123").get("password"));
        assertEquals(0, accounts.login(AccountType.admin, "lihuanshen123", "changed-password").get("code"));
    }
    @Test void securityStateSurvivesNewServiceInstance() throws Exception {
        block(AccountType.user, "alice");
        AccountSecurityService restarted = new AccountSecurityService(hbase, encoder, jwt);
        assertEquals(423, assertThrows(AccountException.class, () -> restarted.login(AccountType.user, "alice", "123456")).status);
    }
    @Test void legacySha256IsAcceptedForBothAccountTypes() throws Exception {
        StringBuilder hash = new StringBuilder();
        for (byte b : java.security.MessageDigest.getInstance("SHA-256").digest("123456".getBytes(java.nio.charset.StandardCharsets.UTF_8)))
            hash.append(String.format("%02x", b));
        for (AccountType type : Arrays.asList(AccountType.user, AccountType.company)) {
            store.put(type.table, "legacy", Map.of(type.passwordColumn, hash.toString()));
            assertNotNull(token(type, "legacy"));
            assertEquals(hash.toString(), store.get(type.table, "legacy").get(type.passwordColumn));
        }
    }
    @Test void registrationValidatesEmailAndDoesNotOverwriteAccounts() throws Exception {
        for (String type : Arrays.asList("user", "company")) {
            String path = "/api/" + type + "/register";
            publicPost(path, Map.of("username", "new", "password", "123456", "companyName", "New"))
                    .andExpect(status().isBadRequest());
            publicPost(path, Map.of("username", "new", "password", "123456", "email", "bad", "companyName", "New"))
                    .andExpect(status().isBadRequest());
            emailAuth.sendRegistration(AccountType.valueOf(type), "new", "new-" + type + "@example.com");
            publicPost(path, Map.of("username", "new", "password", "123456", "email", "new-" + type + "@example.com", "companyName", "New", "code", lastCode))
                    .andExpect(status().isOk());
            AccountType t = AccountType.valueOf(type);
            String hash = store.get(t.table, "new").get(t.passwordColumn);
            assertTrue(hash.startsWith("$2"));
            publicPost(path, Map.of("username", "new", "password", "654321", "email", "new@example.com", "companyName", "New"))
                    .andExpect(status().isConflict());
            assertEquals(hash, store.get(t.table, "new").get(t.passwordColumn));
        }
    }
    @Test void adminEndpointsRejectAnonymousUserAndCompany() throws Exception {
        mvc.perform(get("/api/admin/accounts")).andExpect(status().isUnauthorized());
        mvc.perform(post("/api/admin/accounts/unlock").contentType("application/json").content("{}"))
                .andExpect(status().isUnauthorized());
        for (AccountType type : Arrays.asList(AccountType.user, AccountType.company)) {
            String token = token(type, type == AccountType.user ? "alice" : "acme");
            mvc.perform(get("/api/admin/accounts").header("Authorization", "Bearer " + token)).andExpect(status().isForbidden());
            postJson("/api/admin/accounts/unlock", Map.of("accountType", "user", "username", "alice"), token)
                    .andExpect(status().isForbidden());
        }
    }
    @Test void adminListFiltersPaginatesAndDoesNotExposeSecrets() throws Exception {
        block(AccountType.user, "alice");
        String admin = token(AccountType.admin, "lihuanshen123");
        String body = mvc.perform(get("/api/admin/accounts?accountType=user&status=blocked&keyword=ali&size=1")
                .header("Authorization", "Bearer " + admin)).andExpect(status().isOk())
                .andExpect(jsonPath("$.total").value(1)).andExpect(jsonPath("$.items[0].username").value("alice"))
                .andReturn().getResponse().getContentAsString();
        assertFalse(body.contains("password")); assertFalse(body.contains("reset_digest"));
        mvc.perform(get("/api/admin/accounts?page=2&size=1").header("Authorization", "Bearer " + admin))
                .andExpect(jsonPath("$.items.length()").value(1));
        postJson("/api/admin/accounts/unlock", Map.of("accountType", "user", "username", "alice"), admin)
                .andExpect(status().isOk()).andExpect(jsonPath("$.code").value(0));
    }
    @Test void passwordResetForBothTypesChangesPasswordAndRevokesToken() throws Exception {
        for (AccountType type : Arrays.asList(AccountType.user, AccountType.company)) {
            String name = type == AccountType.user ? "alice" : "acme";
            String old = token(type, name);
            reset.sendCode(type, name, name + "@example.com");
            assertTrue(lastCode.matches("[0-9]{6}"));
            assertFalse(store.get(type.table, name).containsValue(lastCode));
            reset.confirm(type, name, name + "@example.com", lastCode, "new-password");
            mvc.perform(get("/api/chat/sessions?username=" + name).header("Authorization", "Bearer " + old))
                    .andExpect(status().isUnauthorized());
            assertEquals(401, wrong(type, name).status);
            assertThrows(AccountException.class, () -> token(type, name));
            assertEquals(0, accounts.login(type, name, "new-password").get("code"));
            assertThrows(AccountException.class, () -> reset.confirm(type, name, name + "@example.com", lastCode, "another-password"));
        }
    }
    @Test void passwordResetNeverUnblocks() throws Exception {
        block(AccountType.user, "alice");
        reset.sendCode(AccountType.user, "alice", "alice@example.com");
        assertEquals(true, reset.confirm(AccountType.user, "alice", "alice@example.com", lastCode, "new-password").get("blocked"));
        assertEquals(423, assertThrows(AccountException.class, () -> accounts.login(AccountType.user, "alice", "new-password")).status);
    }
    @Test void resetMismatchDoesNotRevealAccountExistenceOrSendEmail() throws Exception {
        Map<String, Object> missing = reset.sendCode(AccountType.user, "missing", "alice@example.com");
        Map<String, Object> mismatch = reset.sendCode(AccountType.user, "alice", "other@example.com");
        assertEquals(missing, mismatch); verify(mail, never()).send(anyString(), anyString());
        assertEquals(missing, reset.sendCode(AccountType.user, "alice", "alice@example.com"));
    }
    @Test void mailFailureInvalidatesReservedCodeAndReportsUnavailable() throws Exception {
        doThrow(new AccountException(503, "邮件发送失败，请稍后重试")).when(mail).send(anyString(), anyString());
        publicPost("/api/auth/password-reset/code", Map.of("accountType", "user", "username", "alice", "email", "alice@example.com"))
                .andExpect(status().isServiceUnavailable());
        assertEquals("failed", store.get("recruit_user", "alice").get("reset_state"));
        assertEquals("", store.get("recruit_user", "alice").get("reset_digest"));
    }
    @Test void sendIntervalAndRollingHourLimitAreEnforced() throws Exception {
        reset.sendCode(AccountType.user, "alice", "alice@example.com");
        assertEquals(429, assertThrows(AccountException.class, () -> reset.sendCode(AccountType.user, "alice", "alice@example.com")).status);
        for (int i = 0; i < 4; i++) { now.addAndGet(60_000); reset.sendCode(AccountType.user, "alice", "alice@example.com"); }
        now.addAndGet(60_000);
        assertEquals(429, assertThrows(AccountException.class, () -> reset.sendCode(AccountType.user, "alice", "alice@example.com")).status);
        now.addAndGet(3_600_000); reset.sendCode(AccountType.user, "alice", "alice@example.com");
    }
    @Test void oldCodeExpiresOnResendAndFiveWrongVerificationsInvalidateCode() throws Exception {
        reset.sendCode(AccountType.user, "alice", "alice@example.com"); String old = lastCode;
        now.addAndGet(60_000); reset.sendCode(AccountType.user, "alice", "alice@example.com");
        // The nonce changes even if random six-digit values happen to collide; test a guaranteed wrong value.
        String bad = "000000".equals(lastCode) ? "000001" : "000000";
        if (!old.equals(lastCode)) assertThrows(AccountException.class, () -> reset.confirm(AccountType.user, "alice", "alice@example.com", old, "new-password"));
        long failed = AccountSecurityService.number(store.get("recruit_user", "alice"), "reset_failures");
        for (long i = failed; i < 5; i++) assertThrows(AccountException.class, () -> reset.confirm(AccountType.user, "alice", "alice@example.com", bad, "new-password"));
        assertThrows(AccountException.class, () -> reset.confirm(AccountType.user, "alice", "alice@example.com", lastCode, "new-password"));
        assertEquals("5", store.get("recruit_user", "alice").get("reset_failures"));
    }
    @Test void resetCodeExpiresAfterTenMinutes() throws Exception {
        reset.sendCode(AccountType.user, "alice", "alice@example.com"); now.addAndGet(600_000);
        assertThrows(AccountException.class, () -> reset.confirm(AccountType.user, "alice", "alice@example.com", lastCode, "new-password"));
    }
    @Test void concurrentConfirmConsumesCodeExactlyOnce() throws Exception {
        reset.sendCode(AccountType.user, "alice", "alice@example.com");
        ExecutorService pool = Executors.newFixedThreadPool(4);
        try {
            List<Callable<Boolean>> tasks = new ArrayList<>();
            for (int i = 0; i < 4; i++) tasks.add(() -> {
                try { reset.confirm(AccountType.user, "alice", "alice@example.com", lastCode, "new-password"); return true; }
                catch (AccountException e) { return false; }
            });
            int successes = 0;
            for (Future<Boolean> future : pool.invokeAll(tasks)) if (future.get()) successes++;
            assertEquals(1, successes); assertEquals("1", store.get("recruit_user", "alice").get("credential_version"));
        } finally { pool.shutdownNow(); }
    }
    @Test void malformedOrTamperedTokensAndInvalidAdminResetAreRejected() throws Exception {
        mvc.perform(get("/api/admin/accounts").header("Authorization", "Bearer garbage")).andExpect(status().isUnauthorized());
        String token = token(AccountType.user, "alice");
        mvc.perform(get("/api/user/profile").header("Authorization", "Bearer " + token.substring(0, token.length() - 5) + "xxxxx"))
                .andExpect(status().isUnauthorized());
        publicPost("/api/auth/password-reset/code", Map.of("accountType", "admin", "username", "lihuanshen123", "email", "995612169@qq.com"))
                .andExpect(status().isBadRequest());
    }
    @Test void publicPagesAndJobsRemainAnonymousButBusinessAndUploadsDoNot() throws Exception {
        for (String path : Arrays.asList("/login.html", "/register.html", "/forgot-password.html", "/admin/index.html", "/api/job/featured"))
            mvc.perform(get(path)).andExpect(status().isOk());
        for (String path : Arrays.asList("/api/company/jobs", "/api/resume/get?username=alice", "/api/chat/sessions?username=alice", "/uploads/file.pdf"))
            mvc.perform(get(path)).andExpect(status().isUnauthorized());
        mvc.perform(post("/api/upload")).andExpect(status().isUnauthorized());
    }
    @Test void companyOperationsUseAuthenticatedOwnerAndEnforceJobOwnership() throws Exception {
        String token = token(AccountType.company, "acme");
        postJson("/api/company/job/publish", Map.of("username", "forged", "title", "Java", "city", "北京",
                "salaryLow", "10", "salaryHigh", "20", "edu", "本科", "exp", "1年", "tags", "Java"), token)
                .andExpect(status().isOk());
        Map<String, String> job = store.scan("recruit_job").get(0); assertEquals("acme", job.get("owner"));
        store.put("recruit_job", "other", Map.of("owner", "otherCo"));
        postJson("/api/company/job/recall", Map.of("username", "otherCo", "jobId", "other"), token)
                .andExpect(jsonPath("$.code").value(1));
        postJson("/api/company/job/recall", Map.of("jobId", job.get("rowKey")), token)
                .andExpect(jsonPath("$.code").value(0));
    }
    @Test void resumeAndChatRejectForgedIdentityAndUnrelatedSession() throws Exception {
        String user = token(AccountType.user, "alice");
        store.put("recruit_resume", "user_alice", Map.of("name", "Alice"));
        store.put("recruit_resume", "user_bob", Map.of("name", "Bob"));
        mvc.perform(get("/api/resume/get?username=bob").header("Authorization", "Bearer " + user))
                .andExpect(jsonPath("$.name").value("Alice"));
        store.put("recruit_chat_session", "owned", Map.of("userUsername", "alice", "companyUsername", "acme"));
        store.put("recruit_chat_session", "other", Map.of("userUsername", "bob", "companyUsername", "other"));
        postJson("/api/chat/send", Map.of("sessionKey", "owned", "sender", "bob", "content", "hello"), user).andExpect(status().isOk());
        assertEquals("alice", store.scan("recruit_chat_message").get(0).get("sender"));
        postJson("/api/chat/send", Map.of("sessionKey", "other", "sender", "bob", "content", "hello"), user).andExpect(status().isForbidden());
        mvc.perform(get("/api/chat/messages?sessionKey=other").header("Authorization", "Bearer " + user)).andExpect(status().isForbidden());
        mvc.perform(get("/api/chat/sessions?username=bob&role=company").header("Authorization", "Bearer " + user))
                .andExpect(jsonPath("$[0].rowKey").value("owned")).andExpect(jsonPath("$.length()").value(1));
    }
    @Test void companyCannotReadUnrelatedResumesOrAttachments() throws Exception {
        String company = token(AccountType.company, "acme");
        mvc.perform(get("/api/chat/talent/resume?userUsername=bob").header("Authorization", "Bearer " + company)).andExpect(status().isForbidden());
        mvc.perform(get("/uploads/not-owned.pdf").header("Authorization", "Bearer " + company)).andExpect(status().isForbidden());
        store.put("recruit_chat_session", "related", Map.of("userUsername", "alice", "companyUsername", "acme"));
        store.put("recruit_resume", "user_alice", Map.of("name", "Alice"));
        mvc.perform(get("/api/chat/talent/resume?userUsername=alice").header("Authorization", "Bearer " + company))
                .andExpect(status().isOk()).andExpect(jsonPath("$.name").value("Alice"));
        postJson("/api/chat/talent/add", Map.of("companyUsername", "forged", "userUsername", "alice"), company).andExpect(status().isOk());
        assertEquals("acme", store.scan("recruit_talent_pool").get(0).get("companyUsername"));
        store.put("recruit_talent_pool", "unrelated", Map.of("companyUsername", "other", "userUsername", "bob"));
        store.put("recruit_resume", "user_bob", Map.of("name", "Bob"));
        mvc.perform(get("/api/company/talent").header("Authorization", "Bearer " + company)).andExpect(jsonPath("$.length()").value(1));
    }

    @Test void resumeSaveUsesLoginIdentityAndAttachmentFlowChecksBothParticipants() throws Exception {
        String user = token(AccountType.user, "alice");
        Map<String, Object> resume = new HashMap<>();
        resume.put("username", "forged"); resume.put("name", "Alice"); resume.put("city", "北京");
        resume.put("edu", "本科"); resume.put("exp", "1年"); resume.put("phone", "123");
        resume.put("email", "alice@example.com"); resume.put("skills", "Java");
        postJson("/api/resume/save", resume, user).andExpect(status().isOk());
        assertNull(store.get("recruit_resume", "user_forged"));
        assertEquals("Alice", store.get("recruit_resume", "user_alice").get("name"));
        org.springframework.mock.web.MockMultipartFile file = new org.springframework.mock.web.MockMultipartFile(
                "file", "resume.txt", "text/plain", "resume-content".getBytes(java.nio.charset.StandardCharsets.UTF_8));
        String reply = mvc.perform(multipart("/api/upload").file(file).header("Authorization", "Bearer " + user))
                .andExpect(status().isOk()).andReturn().getResponse().getContentAsString();
        String path = json.readTree(reply).get("filePath").asText();
        String filename = path.substring("/uploads/".length());
        try {
            String company = token(AccountType.company, "acme");
            mvc.perform(get(path).header("Authorization", "Bearer " + user)).andExpect(status().isOk())
                    .andExpect(content().string("resume-content"));
            mvc.perform(get(path).header("Authorization", "Bearer " + company)).andExpect(status().isForbidden());
            store.put("recruit_job", "owned-job", Map.of("owner", "acme", "title", "Java", "company", "ACME"));
            postJson("/api/chat/apply", Map.of("username", "forged", "jobId", "owned-job",
                    "attachmentName", "resume.txt", "attachmentPath", path), user)
                    .andExpect(status().isOk()).andExpect(jsonPath("$.code").value(0));
            assertEquals("alice", store.scan("recruit_application").get(0).get("username"));
            mvc.perform(get(path).header("Authorization", "Bearer " + company)).andExpect(status().isOk());
            create(AccountType.user, "bob");
            postJson("/api/chat/apply", Map.of("jobId", "owned-job", "attachmentName", "resume.txt", "attachmentPath", path),
                    token(AccountType.user, "bob")).andExpect(status().isForbidden());
            block(AccountType.user, "alice");
            mvc.perform(get(path).header("Authorization", "Bearer " + user)).andExpect(status().isUnauthorized());
        } finally {
            java.nio.file.Files.deleteIfExists(java.nio.file.Path.of(System.getProperty("user.dir"), "uploads", filename));
        }
    }
    @Test void concurrentSendsReserveOnlyOneMailAndConcurrentWrongCodesCountToFive() throws Exception {
        ExecutorService pool = Executors.newFixedThreadPool(8);
        try {
            List<Callable<Boolean>> sends = new ArrayList<>();
            for (int i = 0; i < 8; i++) sends.add(() -> {
                try { reset.sendCode(AccountType.user, "alice", "alice@example.com"); return true; }
                catch (AccountException e) { assertEquals(429, e.status); return false; }
            });
            int sent = 0;
            for (Future<Boolean> future : pool.invokeAll(sends)) if (future.get()) sent++;
            assertEquals(1, sent); verify(mail, times(1)).send(anyString(), anyString());
            String bad = "000000".equals(lastCode) ? "000001" : "000000";
            List<Callable<Boolean>> attempts = new ArrayList<>();
            for (int i = 0; i < 8; i++) attempts.add(() -> {
                assertThrows(AccountException.class, () -> reset.confirm(AccountType.user, "alice", "alice@example.com", bad, "new-password"));
                return true;
            });
            for (Future<Boolean> future : pool.invokeAll(attempts)) assertTrue(future.get());
            assertEquals("5", store.get("recruit_user", "alice").get("reset_failures"));
        } finally { pool.shutdownNow(); }
    }
    @Test void databaseOutageDuringTokenValidationIsNotReportedAsBadCredentials() throws Exception {
        String token = token(AccountType.user, "alice");
        when(hbase.getRow("recruit_user", "alice", "info")).thenThrow(new java.io.IOException("unavailable"));
        mvc.perform(get("/api/user/profile").header("Authorization", "Bearer " + token)).andExpect(status().isServiceUnavailable());
        assertEquals("0", store.get("recruit_user", "alice").get("failed_attempts"));
    }

    @Test void verifiedRegistrationAndEmailLoginWorkForBothRolesThroughHttp() throws Exception {
        for (String type : Arrays.asList("user", "company")) {
            Map<String, String> body = new HashMap<>(Map.of("accountType", type, "username", "fresh", "email", type + "@example.com"));
            body.put("password", "123456"); body.put("companyName", "Company");
            publicPost("/api/" + type + "/register", body).andExpect(status().isBadRequest());
            publicPost("/api/auth/register/code", body).andExpect(status().isOk());
            assertNull(store.get(AccountType.valueOf(type).table, "fresh"));
            assertFalse(store.get(EmailAuthService.TABLE, "register:" + type + ":fresh").containsValue(lastCode));
            body.put("code", lastCode);
            publicPost("/api/" + type + "/register", body).andExpect(status().isOk());
            publicPost("/api/" + type + "/register", body).andExpect(status().isConflict());
            publicPost("/api/auth/email-login/code", body).andExpect(status().isOk());
            body.put("code", lastCode);
            publicPost("/api/auth/email-login/confirm", body).andExpect(status().isOk())
                    .andExpect(jsonPath("$.role").value(type)).andExpect(jsonPath("$.token").isString());
            publicPost("/api/auth/email-login/confirm", body).andExpect(status().isBadRequest());
        }
    }
    @Test void loginChallengeDoesNotBypassBlockingOrCredentialChanges() throws Exception {
        emailAuth.sendLogin(AccountType.user, "alice", "alice@example.com"); String code = lastCode;
        wrong(AccountType.user, "alice");
        String oldToken = (String) emailAuth.login(AccountType.user, "alice", "alice@example.com", code).get("token");
        assertEquals("0", store.get("recruit_user", "alice").get("failed_attempts"));
        now.addAndGet(60_000); emailAuth.sendLogin(AccountType.user, "alice", "alice@example.com"); String beforeBlock = lastCode;
        block(AccountType.user, "alice");
        assertThrows(AccountException.class, () -> emailAuth.login(AccountType.user, "alice", "alice@example.com", beforeBlock));
        accounts.unlock(AccountType.user, "alice", "lihuanshen123");
        assertThrows(AccountException.class, () -> emailAuth.login(AccountType.user, "alice", "alice@example.com", beforeBlock));
        mvc.perform(get("/api/user/profile").header("Authorization", "Bearer " + oldToken)).andExpect(status().isUnauthorized());
        now.addAndGet(60_000); emailAuth.sendLogin(AccountType.user, "alice", "alice@example.com"); String beforeReset = lastCode;
        reset.sendCode(AccountType.user, "alice", "alice@example.com");
        reset.confirm(AccountType.user, "alice", "alice@example.com", lastCode, "654321");
        assertThrows(AccountException.class, () -> emailAuth.login(AccountType.user, "alice", "alice@example.com", beforeReset));
    }
    @Test void loginMismatchAndBlockedAccountDoNotSendOrRevealExistence() throws Exception {
        Map<String, Object> missing = emailAuth.sendLogin(AccountType.user, "missing", "alice@example.com");
        assertEquals(missing, emailAuth.sendLogin(AccountType.user, "alice", "other@example.com"));
        block(AccountType.user, "alice");
        assertEquals(missing, emailAuth.sendLogin(AccountType.user, "alice", "alice@example.com"));
        verify(mail, never()).send(anyString(), anyString(), any(EmailPurpose.class));
    }
    @Test void registrationLimitsFollowMailboxAcrossUsernamesAndRoles() throws Exception {
        emailAuth.sendRegistration(AccountType.user, "first", "shared@example.com");
        assertEquals(429, assertThrows(AccountException.class, () -> emailAuth.sendRegistration(AccountType.company, "second", "SHARED@example.com")).status);
        for (int i = 1; i < 5; i++) {
            now.addAndGet(60_000); emailAuth.sendRegistration(AccountType.company, "company" + i, "shared@example.com");
        }
        now.addAndGet(60_000);
        assertEquals(429, assertThrows(AccountException.class, () -> emailAuth.sendRegistration(AccountType.user, "sixth", "shared@example.com")).status);
        now.addAndGet(3_600_000); emailAuth.sendRegistration(AccountType.user, "sixth", "shared@example.com");
    }
    @Test void registrationAccountQuotaCannotBeBypassedByChangingEmail() throws Exception {
        emailAuth.sendRegistration(AccountType.user, "new", "one@example.com");
        assertEquals(429, assertThrows(AccountException.class, () -> emailAuth.sendRegistration(AccountType.user, "new", "two@example.com")).status);
    }
    @Test void newMailFailuresNeverActivateCodesAndRemainRateLimited() throws Exception {
        doThrow(new AccountException(503, "邮件发送失败")).when(mail).send(anyString(), anyString(), any(EmailPurpose.class));
        assertEquals(503, assertThrows(AccountException.class, () -> emailAuth.sendLogin(AccountType.user, "alice", "alice@example.com")).status);
        assertEquals("failed", store.get("recruit_user", "alice").get("login_state"));
        assertEquals("", store.get("recruit_user", "alice").get("login_digest"));
        assertEquals(429, assertThrows(AccountException.class, () -> emailAuth.sendLogin(AccountType.user, "alice", "alice@example.com")).status);
        assertEquals(503, assertThrows(AccountException.class, () -> emailAuth.sendRegistration(AccountType.user, "new", "new@example.com")).status);
        assertEquals("failed", store.get(EmailAuthService.TABLE, "register:user:new").get("register_state"));
        assertNull(store.get("recruit_user", "new"));
    }
    @Test void purposesIdentitiesAndAccountTypesCannotShareCodes() throws Exception {
        emailAuth.sendRegistration(AccountType.user, "new", "new@example.com"); String registration = lastCode;
        assertThrows(AccountException.class, () -> emailAuth.login(AccountType.user, "new", "new@example.com", registration));
        assertThrows(AccountException.class, () -> emailAuth.register(AccountType.company, "new", "123456", "new@example.com", registration, Map.of()));
        assertThrows(AccountException.class, () -> emailAuth.register(AccountType.user, "other", "123456", "new@example.com", registration, Map.of()));
        assertThrows(AccountException.class, () -> emailAuth.register(AccountType.user, "new", "123456", "other@example.com", registration, Map.of()));
        emailAuth.sendLogin(AccountType.user, "alice", "alice@example.com"); String loginCode = lastCode;
        assertThrows(AccountException.class, () -> reset.confirm(AccountType.user, "alice", "alice@example.com", loginCode, "new-password"));
        emailAuth.register(AccountType.user, "new", "123456", "new@example.com", registration, Map.of());
        assertNotNull(emailAuth.login(AccountType.user, "alice", "ALICE@example.com", loginCode).get("token"));
        publicPost("/api/auth/email-login/code", Map.of("accountType", "admin", "username", "lihuanshen123", "email", "995612169@qq.com"))
                .andExpect(status().isBadRequest());
    }
    @Test void loginResendExpiryFailureLimitAndRestartAreEnforced() throws Exception {
        emailAuth.sendLogin(AccountType.user, "alice", "alice@example.com"); String first = lastCode;
        assertEquals(429, assertThrows(AccountException.class, () -> emailAuth.sendLogin(AccountType.user, "alice", "alice@example.com")).status);
        now.addAndGet(60_000); emailAuth.sendLogin(AccountType.user, "alice", "alice@example.com"); String current = lastCode;
        assertNotEquals(first, current);
        assertThrows(AccountException.class, () -> emailAuth.login(AccountType.user, "alice", "alice@example.com", first));
        String wrongCode = current.equals("000000") ? "000001" : "000000";
        for (int i = 1; i < 5; i++) assertThrows(AccountException.class, () -> emailAuth.login(AccountType.user, "alice", "alice@example.com", wrongCode));
        assertThrows(AccountException.class, () -> emailAuth.login(AccountType.user, "alice", "alice@example.com", current));
        now.addAndGet(60_000); emailAuth.sendLogin(AccountType.user, "alice", "alice@example.com");
        now.addAndGet(600_000);
        EmailAuthService restarted = new EmailAuthService(hbase, accounts, mail, jwt, clock);
        assertThrows(AccountException.class, () -> restarted.login(AccountType.user, "alice", "alice@example.com", lastCode));
    }
    @Test void loginHourlyLimitPersistsAcrossServiceInstances() throws Exception {
        for (int i = 0; i < 5; i++) { emailAuth.sendLogin(AccountType.user, "alice", "alice@example.com"); now.addAndGet(60_000); }
        EmailAuthService restarted = new EmailAuthService(hbase, accounts, mail, jwt, clock);
        assertEquals(429, assertThrows(AccountException.class, () -> restarted.sendLogin(AccountType.user, "alice", "alice@example.com")).status);
    }
    @Test void concurrentEmailLoginConsumesExactlyOnce() throws Exception {
        emailAuth.sendLogin(AccountType.user, "alice", "alice@example.com"); String code = lastCode;
        ExecutorService pool = Executors.newFixedThreadPool(6);
        try {
            List<Callable<Boolean>> tasks = new ArrayList<>();
            for (int i = 0; i < 6; i++) tasks.add(() -> {
                try { emailAuth.login(AccountType.user, "alice", "alice@example.com", code); return true; }
                catch (AccountException e) { return false; }
            });
            int successes = 0;
            for (Future<Boolean> result : pool.invokeAll(tasks)) if (result.get()) successes++;
            assertEquals(1, successes);
        } finally { pool.shutdownNow(); }
    }
    @Test void concurrentRegistrationConsumesExactlyOnce() throws Exception {
        emailAuth.sendRegistration(AccountType.user, "new", "new@example.com"); String code = lastCode;
        ExecutorService pool = Executors.newFixedThreadPool(4);
        try {
            List<Callable<Boolean>> tasks = new ArrayList<>();
            for (int i = 0; i < 4; i++) tasks.add(() -> {
                try { emailAuth.register(AccountType.user, "new", "123456", "new@example.com", code, Map.of()); return true; }
                catch (AccountException e) { return false; }
            });
            int successes = 0;
            for (Future<Boolean> result : pool.invokeAll(tasks)) if (result.get()) successes++;
            assertEquals(1, successes);
        } finally { pool.shutdownNow(); }
    }
    @Test void invalidRegistrationFieldsDoNotConsumeAndDatabaseFailureDoesNotRestoreCode() throws Exception {
        emailAuth.sendRegistration(AccountType.company, "new", "new@example.com"); String code = lastCode;
        publicPost("/api/company/register", Map.of("username", "new", "password", "123456", "email", "new@example.com", "code", code))
                .andExpect(status().isBadRequest());
        assertEquals("ready", store.get(EmailAuthService.TABLE, "register:company:new").get("register_state"));
        doThrow(new java.io.IOException("down")).when(hbase).compareAndPut(eq("recruit_company"), eq("new"), eq("password_hash"), isNull(), anyMap());
        assertEquals(503, assertThrows(AccountException.class, () -> emailAuth.register(AccountType.company, "new", "123456", "new@example.com", code, Map.of())).status);
        assertEquals("consumed", store.get(EmailAuthService.TABLE, "register:company:new").get("register_state"));
    }

    @Test void registrationResendFailureBudgetAndExpiryAreEnforced() throws Exception {
        emailAuth.sendRegistration(AccountType.user, "new", "new@example.com"); String first = lastCode;
        now.addAndGet(60_000); emailAuth.sendRegistration(AccountType.user, "new", "new@example.com"); String current = lastCode;
        assertNotEquals(first, current);
        assertThrows(AccountException.class, () -> emailAuth.register(AccountType.user, "new", "123456", "new@example.com", first, Map.of()));
        String bad = current.equals("000000") ? "000001" : "000000";
        for (int i = 1; i < 5; i++) assertThrows(AccountException.class, () -> emailAuth.register(AccountType.user, "new", "123456", "new@example.com", bad, Map.of()));
        assertThrows(AccountException.class, () -> emailAuth.register(AccountType.user, "new", "123456", "new@example.com", current, Map.of()));
        now.addAndGet(60_000); emailAuth.sendRegistration(AccountType.user, "new", "new@example.com");
        now.addAndGet(600_000);
        assertThrows(AccountException.class, () -> emailAuth.register(AccountType.user, "new", "123456", "new@example.com", lastCode, Map.of()));
        assertNull(store.get("recruit_user", "new"));
    }
    @Test void pendingMailCannotBeUsedBeforeSmtpAcceptsIt() throws Exception {
        doAnswer(call -> {
            String candidate = call.getArgument(1);
            assertEquals("pending", store.get("recruit_user", "alice").get("login_state"));
            assertThrows(AccountException.class, () -> emailAuth.login(AccountType.user, "alice", "alice@example.com", candidate));
            lastCode = candidate; return null;
        }).when(mail).send(anyString(), anyString(), eq(EmailPurpose.LOGIN));
        emailAuth.sendLogin(AccountType.user, "alice", "alice@example.com");
        assertNotNull(emailAuth.login(AccountType.user, "alice", "alice@example.com", lastCode).get("token"));
    }
    @Test void oldResetCodeCannotFollowAnEmailChange() throws Exception {
        reset.sendCode(AccountType.user, "alice", "alice@example.com"); String code = lastCode;
        store.put("recruit_user", "alice", Map.of("email", "other@example.com"));
        assertThrows(AccountException.class, () -> reset.confirm(AccountType.user, "alice", "other@example.com", code, "654321"));
    }
}
