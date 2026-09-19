package com.example.demo;

import com.example.demo.config.AccountInitializer;
import com.example.demo.security.AccountType;
import com.example.demo.service.*;
import com.example.demo.util.JwtUtil;
import com.fasterxml.jackson.databind.*;
import org.junit.jupiter.api.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.test.web.servlet.*;
import java.io.IOException;
import java.time.Clock;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import static org.mockito.ArgumentMatchers.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest(properties = "security.jwt-secret=test-only-random-secret-with-at-least-32-bytes")
@AutoConfigureMockMvc
class AnnouncementTest {
    @MockBean HBaseService hbase;
    @MockBean ResetMailService mail;
    @MockBean Clock clock;
    @Autowired MockMvc mvc;
    @Autowired ObjectMapper json;
    @Autowired JwtUtil jwt;
    @Autowired AccountInitializer initializer;
    @Autowired AnnouncementService announcements;
    MemoryAccounts store;
    String admin;
    @BeforeEach void setup() throws Exception {
        reset(hbase, clock); store = new MemoryAccounts(hbase);
        when(clock.millis()).thenReturn(1800000000000L);
        for (AccountType type : AccountType.values()) store.put(type.table, type.name(), Map.of("credential_version", "0", "role", type.name()));
        admin = jwt.generateToken("admin", AccountType.admin, 0);
    }
    ResultActions write(String path, Object body, String token) throws Exception {
        return mvc.perform(post(path).contentType("application/json").content(json.writeValueAsBytes(body))
                .header("Authorization", token == null ? "" : "Bearer " + token));
    }
    JsonNode create(String title) throws Exception {
        return json.readTree(write("/api/admin/announcements", Map.of("title", title, "body", "正文\n第二行", "author", "forged", "publishedAt", "1"), admin)
                .andExpect(status().isOk()).andReturn().getResponse().getContentAsByteArray()).get("item");
    }
    @Test void completeLifecyclePreservesPublicationAndPrivateAuthor() throws Exception {
        JsonNode item = create("  服务通知  "); String id = item.get("id").asText();
        assertEquals("服务通知", item.get("title").asText()); assertEquals("管理员", item.get("author").asText());
        assertEquals("admin", store.get(AnnouncementService.TABLE, id).get("author"));
        mvc.perform(get("/api/announcements")).andExpect(status().isOk()).andExpect(jsonPath("$.total").value(1))
                .andExpect(jsonPath("$.items[0].body").doesNotExist());
        when(clock.millis()).thenReturn(1800000001000L);
        write("/api/admin/announcements/" + id + "/update", Map.of("title", "更新通知", "body", "<script>alert(1)</script>"), admin)
                .andExpect(status().isOk()).andExpect(jsonPath("$.item.publishedAt").value("1800000000000"))
                .andExpect(jsonPath("$.item.updatedAt").value("1800000001000"));
        mvc.perform(get("/api/announcements/" + id)).andExpect(status().isOk())
                .andExpect(jsonPath("$.item.body").value("<script>alert(1)</script>"));
        write("/api/admin/announcements/" + id + "/delete", Map.of(), admin).andExpect(status().isOk());
        mvc.perform(get("/api/announcements/" + id)).andExpect(status().isNotFound());
        mvc.perform(get("/api/announcements")).andExpect(jsonPath("$.total").value(0));
    }
    @Test void allRolesReadButOnlyAdminWritesAndRevokedTokenFails() throws Exception {
        String id = create("公告").get("id").asText();
        for (AccountType type : AccountType.values()) {
            String token = jwt.generateToken(type.name(), type, 0);
            mvc.perform(get("/api/announcements").header("Authorization", "Bearer " + token)).andExpect(status().isOk());
            mvc.perform(get("/api/announcements/" + id).header("Authorization", "Bearer " + token)).andExpect(status().isOk());
            if (type == AccountType.admin) continue;
            for (String path : List.of("/api/admin/announcements", "/api/admin/announcements/" + id + "/update", "/api/admin/announcements/" + id + "/delete"))
                write(path, Map.of("title", "冒充", "body", "正文", "role", "admin"), token).andExpect(status().isForbidden());
        }
        for (String token : Arrays.asList(null, "forged"))
            write("/api/admin/announcements", Map.of("title", "x", "body", "x"), token).andExpect(status().isUnauthorized());
        store.put(AccountType.admin.table, "admin", Map.of("credential_version", "1"));
        write("/api/admin/announcements/" + id + "/delete", Map.of(), admin).andExpect(status().isUnauthorized());
    }
    @Test void paginationStableAndEditDoesNotReorder() throws Exception {
        List<String> ids = new ArrayList<>();
        for (int i = 0; i < 12; i++) ids.add(create("公告 " + i).get("id").asText());
        ids.sort(Comparator.reverseOrder());
        mvc.perform(get("/api/announcements?page=1&size=3")).andExpect(jsonPath("$.items.length()").value(3))
                .andExpect(jsonPath("$.items[0].id").value(ids.get(0))).andExpect(jsonPath("$.total").value(12));
        when(clock.millis()).thenReturn(1800000099999L);
        write("/api/admin/announcements/" + ids.get(11) + "/update", Map.of("title", "已编辑", "body", "正文"), admin).andExpect(status().isOk());
        mvc.perform(get("/api/announcements?page=2&size=10")).andExpect(jsonPath("$.items.length()").value(2))
                .andExpect(jsonPath("$.items[1].id").value(ids.get(11)));
        mvc.perform(get("/api/announcements?page=2147483647&size=50")).andExpect(status().isOk()).andExpect(jsonPath("$.items.length()").value(0));
    }
    @Test void invalidInputsAndMissingRecordsUseContractErrors() throws Exception {
        for (Object body : Arrays.asList(Map.of(), Map.of("title", "  ", "body", "x"), Map.of("title", 42, "body", "x"),
                Map.of("title", "x".repeat(101), "body", "x"), Map.of("title", "x", "body", "x".repeat(10001)), List.of(), "text"))
            write("/api/admin/announcements", body, admin).andExpect(status().isBadRequest()).andExpect(jsonPath("$.msg").isString());
        for (String query : List.of("page=0", "page=-1", "page=2147483648", "page=", "page=abc", "size=0", "size=51", "size=1.5", "size="))
            mvc.perform(get("/api/announcements?" + query)).andExpect(status().isBadRequest());
        write("/api/admin/announcements/missing/update", Map.of("title", "x", "body", "x"), admin).andExpect(status().isNotFound());
        write("/api/admin/announcements/missing/delete", Map.of(), admin).andExpect(status().isNotFound());
        create("\u00a0" + "😀".repeat(100) + "\u0085");
        mvc.perform(post("/api/admin/announcements").header("Authorization", "Bearer " + admin).contentType("application/json").content("{broken"))
                .andExpect(status().isBadRequest());
    }
    @Test void storageFailuresDoNotReportSuccessOrLoseOldData() throws Exception {
        String id = create("原始").get("id").asText();
        doThrow(new IOException("private configuration")).when(hbase).putRow(eq(AnnouncementService.TABLE), anyString(), eq("info"), anyMap());
        write("/api/admin/announcements/" + id + "/update", Map.of("title", "修改", "body", "正文"), admin)
                .andExpect(status().isServiceUnavailable()).andExpect(jsonPath("$.msg").value("服务暂时不可用，请稍后重试"));
        assertEquals("原始", announcements.detail(id).get("title"));
        doThrow(new IOException()).when(hbase).deleteRow(eq(AnnouncementService.TABLE), anyString());
        write("/api/admin/announcements/" + id + "/delete", Map.of(), admin).andExpect(status().isServiceUnavailable());
        when(hbase.scanAll(AnnouncementService.TABLE, "info")).thenThrow(new IOException());
        mvc.perform(get("/api/announcements")).andExpect(status().isServiceUnavailable());
    }
    @Test void initializerEnsuresTableAndNewServiceReadsExistingData() throws Exception {
        initializer.run(null); verify(hbase).ensureTable(AnnouncementService.TABLE);
        String id = create("持久化").get("id").asText();
        assertEquals("持久化", new AnnouncementService(hbase, clock).detail(id).get("title"));
    }
}
