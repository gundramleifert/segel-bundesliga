package de.segelbundesliga.web;

import de.segelbundesliga.config.SecurityConfig;
import de.segelbundesliga.domain.Page.Visibility;
import de.segelbundesliga.dto.PageDto;
import de.segelbundesliga.service.PageService;
import de.segelbundesliga.service.StorageService;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.context.annotation.Import;
import org.springframework.security.test.context.support.WithAnonymousUser;
import org.springframework.security.test.context.support.WithMockUser;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.servlet.MockMvc;

import java.util.List;

import static org.mockito.ArgumentMatchers.anyBoolean;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(PageController.class)
@Import(SecurityConfig.class)
@TestPropertySource(properties = {"application.zitadel.project-id=test-project-id"})
@DisplayName("PageController Tests")
class PageControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private PageService pageService;

    @MockBean
    private StorageService storageService;

    private PageDto.ListItem createListItem(Long id, String title, String slug, Visibility visibility) {
        PageDto.ListItem item = new PageDto.ListItem();
        item.setId(id);
        item.setTitle(title);
        item.setSlug(slug);
        item.setVisibility(visibility);
        item.setSortOrder(0);
        item.setShowInMenu(true);
        return item;
    }

    @Nested
    @DisplayName("GET /api/pages/menu")
    class GetMenuPagesTests {

        @Test
        @WithAnonymousUser
        @DisplayName("anonymous user gets only PUBLIC pages")
        void getMenuPages_anonymous_getsOnlyPublic() throws Exception {
            PageDto.ListItem publicPage = createListItem(1L, "Public Page", "public", Visibility.PUBLIC);
            when(pageService.getMenuPages(false)).thenReturn(List.of(publicPage));

            mockMvc.perform(get("/api/pages/menu"))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$[0].title").value("Public Page"));

            verify(pageService).getMenuPages(false);
        }

        @Test
        @WithMockUser(roles = "ADMIN")
        @DisplayName("admin gets PUBLIC and INTERNAL pages")
        void getMenuPages_admin_getsPublicAndInternal() throws Exception {
            PageDto.ListItem publicPage = createListItem(1L, "Public Page", "public", Visibility.PUBLIC);
            PageDto.ListItem internalPage = createListItem(2L, "Internal Page", "internal", Visibility.INTERNAL);
            when(pageService.getMenuPages(true)).thenReturn(List.of(publicPage, internalPage));

            mockMvc.perform(get("/api/pages/menu"))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$").isArray())
                    .andExpect(jsonPath("$.length()").value(2));

            verify(pageService).getMenuPages(true);
        }

        @Test
        @WithMockUser(roles = "INTERNAL_ACCESS")
        @DisplayName("user with INTERNAL_ACCESS gets PUBLIC and INTERNAL pages")
        void getMenuPages_internalAccess_getsPublicAndInternal() throws Exception {
            PageDto.ListItem publicPage = createListItem(1L, "Public Page", "public", Visibility.PUBLIC);
            PageDto.ListItem internalPage = createListItem(2L, "Internal Page", "internal", Visibility.INTERNAL);
            when(pageService.getMenuPages(true)).thenReturn(List.of(publicPage, internalPage));

            mockMvc.perform(get("/api/pages/menu"))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.length()").value(2));

            verify(pageService).getMenuPages(true);
        }

        @Test
        @WithMockUser(roles = "OTHER_ROLE")
        @DisplayName("user without ADMIN or INTERNAL_ACCESS gets only PUBLIC pages")
        void getMenuPages_otherRole_getsOnlyPublic() throws Exception {
            PageDto.ListItem publicPage = createListItem(1L, "Public Page", "public", Visibility.PUBLIC);
            when(pageService.getMenuPages(false)).thenReturn(List.of(publicPage));

            mockMvc.perform(get("/api/pages/menu"))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.length()").value(1));

            verify(pageService).getMenuPages(false);
        }
    }

    @Nested
    @DisplayName("GET /api/pages/public/{slug}")
    class GetPublicBySlugTests {

        @Test
        @WithAnonymousUser
        @DisplayName("anonymous user can access PUBLIC page")
        void getPublicBySlug_anonymous_publicPage_success() throws Exception {
            PageDto.Response response = new PageDto.Response();
            response.setId(1L);
            response.setTitle("Public Page");
            response.setSlug("public-page");
            response.setContent("Content");
            response.setVisibility(Visibility.PUBLIC);
            when(pageService.getBySlugWithAccessCheck("public-page", false)).thenReturn(response);

            mockMvc.perform(get("/api/pages/public/public-page"))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.title").value("Public Page"));

            verify(pageService).getBySlugWithAccessCheck("public-page", false);
        }

        @Test
        @WithMockUser(roles = "ADMIN")
        @DisplayName("admin can access INTERNAL page")
        void getPublicBySlug_admin_internalPage_success() throws Exception {
            PageDto.Response response = new PageDto.Response();
            response.setId(1L);
            response.setTitle("Internal Page");
            response.setSlug("internal-page");
            response.setContent("Internal Content");
            response.setVisibility(Visibility.INTERNAL);
            when(pageService.getBySlugWithAccessCheck("internal-page", true)).thenReturn(response);

            mockMvc.perform(get("/api/pages/public/internal-page"))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.title").value("Internal Page"));

            verify(pageService).getBySlugWithAccessCheck("internal-page", true);
        }
    }
}
