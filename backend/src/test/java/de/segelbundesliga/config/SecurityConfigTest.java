package de.segelbundesliga.config;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.security.test.context.support.WithAnonymousUser;
import org.springframework.security.test.context.support.WithMockUser;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

/**
 * Security tests using @WithMockUser with full Spring context.
 */
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@DisplayName("Security Tests")
class SecurityConfigTest {

    @Autowired
    private MockMvc mockMvc;

    @Nested
    @DisplayName("Public GET Endpoints")
    class PublicEndpoints {

        @Test
        @WithAnonymousUser
        @DisplayName("GET /api/posts/public - accessible without auth")
        void postsPublic_noAuth_returns200() throws Exception {
            mockMvc.perform(get("/api/posts/public"))
                .andExpect(status().isOk());
        }

        @Test
        @WithAnonymousUser
        @DisplayName("GET /api/pages/public - accessible without auth")
        void pagesPublic_noAuth_returns200() throws Exception {
            mockMvc.perform(get("/api/pages/public"))
                .andExpect(status().isOk());
        }

        @Test
        @WithAnonymousUser
        @DisplayName("GET /api/sponsors/public - accessible without auth")
        void sponsorsPublic_noAuth_returns200() throws Exception {
            mockMvc.perform(get("/api/sponsors/public"))
                .andExpect(status().isOk());
        }
    }

    @Nested
    @DisplayName("Protected Endpoints - No Auth")
    class ProtectedNoAuth {

        @Test
        @WithAnonymousUser
        @DisplayName("POST /api/posts - returns 401")
        void createPost_noAuth_returns401() throws Exception {
            mockMvc.perform(post("/api/posts")
                    .contentType(MediaType.APPLICATION_JSON)
                    .content("""
                        {"title":"Test","slug":"test","content":"c","status":"DRAFT","visibility":"PUBLIC"}
                        """))
                .andExpect(status().isUnauthorized());
        }

        @Test
        @WithAnonymousUser
        @DisplayName("GET /api/tournaments - returns 401")
        void tournaments_noAuth_returns401() throws Exception {
            mockMvc.perform(get("/api/tournaments"))
                .andExpect(status().isUnauthorized());
        }
    }

    @Nested
    @DisplayName("Protected Endpoints - With Auth")
    class ProtectedWithAuth {

        @Test
        @WithMockUser
        @DisplayName("GET /api/tournaments - returns 200 with auth")
        void tournaments_withAuth_returns200() throws Exception {
            mockMvc.perform(get("/api/tournaments"))
                .andExpect(status().isOk());
        }

        @Test
        @WithMockUser(roles = "BLOG_WRITE")
        @DisplayName("POST /api/posts - works with BLOG_WRITE role")
        void createPost_withBlogWriteRole_returns201() throws Exception {
            mockMvc.perform(post("/api/posts")
                    .contentType(MediaType.APPLICATION_JSON)
                    .content("""
                        {"title":"Test","slug":"test-blogwrite","content":"c","status":"DRAFT","visibility":"PUBLIC"}
                        """))
                .andExpect(status().isCreated());
        }

        @Test
        @WithMockUser(roles = "ADMIN")
        @DisplayName("POST /api/posts - works with ADMIN role")
        void createPost_withAdminRole_returns201() throws Exception {
            mockMvc.perform(post("/api/posts")
                    .contentType(MediaType.APPLICATION_JSON)
                    .content("""
                        {"title":"Test","slug":"test-admin","content":"c","status":"DRAFT","visibility":"PUBLIC"}
                        """))
                .andExpect(status().isCreated());
        }

        @Test
        @WithMockUser(roles = "PAIRING_VIEW")
        @DisplayName("POST /api/posts - returns 403 without BLOG_WRITE")
        void createPost_withoutBlogWriteRole_returns403() throws Exception {
            mockMvc.perform(post("/api/posts")
                    .contentType(MediaType.APPLICATION_JSON)
                    .content("""
                        {"title":"Test","slug":"test","content":"c","status":"DRAFT","visibility":"PUBLIC"}
                        """))
                .andExpect(status().isForbidden());
        }
    }

    @Nested
    @DisplayName("Admin Endpoints")
    class AdminEndpoints {

        @Test
        @WithMockUser(roles = "BLOG_WRITE")
        @DisplayName("GET /api/admin/* - returns 403 without ADMIN")
        void adminEndpoint_withoutAdmin_returns403() throws Exception {
            mockMvc.perform(get("/api/admin/users"))
                .andExpect(status().isForbidden());
        }

        @Test
        @WithMockUser(roles = "ADMIN")
        @DisplayName("GET /api/admin/* - returns 404 with ADMIN (passes security)")
        void adminEndpoint_withAdmin_passesSecurityReturns404() throws Exception {
            mockMvc.perform(get("/api/admin/users"))
                .andExpect(status().isNotFound());
        }
    }
}
