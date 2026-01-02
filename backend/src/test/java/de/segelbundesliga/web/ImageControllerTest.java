package de.segelbundesliga.web;

import de.segelbundesliga.config.SecurityConfig;
import de.segelbundesliga.service.StorageService;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.security.test.context.support.WithAnonymousUser;
import org.springframework.security.test.context.support.WithMockUser;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.servlet.MockMvc;

import java.io.ByteArrayInputStream;

import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@WebMvcTest(ImageController.class)
@Import(SecurityConfig.class)
@TestPropertySource(properties = {"application.zitadel.project-id=test-project-id"})
@DisplayName("ImageController Tests")
class ImageControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private StorageService storageService;

    @Nested
    @DisplayName("GET /api/images/**")
    class GetImageProxyTests {

        @Test
        @WithAnonymousUser
        @DisplayName("anonymous user can access image proxy")
        void getImage_anonymous_success() throws Exception {
            byte[] imageBytes = new byte[]{(byte) 0x89, 'P', 'N', 'G'}; // PNG magic bytes
            String objectId = "editor-images/test-image.png";

            when(storageService.download(objectId))
                    .thenReturn(new ByteArrayInputStream(imageBytes));

            mockMvc.perform(get("/api/images/" + objectId))
                    .andExpect(status().isOk())
                    .andExpect(content().contentType(MediaType.IMAGE_PNG))
                    .andExpect(content().bytes(imageBytes));
        }

        @Test
        @WithAnonymousUser
        @DisplayName("returns correct content-type for JPEG")
        void getImage_jpeg_correctContentType() throws Exception {
            byte[] imageBytes = new byte[]{(byte) 0xFF, (byte) 0xD8, (byte) 0xFF}; // JPEG magic bytes
            String objectId = "editor-images/photo.jpg";

            when(storageService.download(objectId))
                    .thenReturn(new ByteArrayInputStream(imageBytes));

            mockMvc.perform(get("/api/images/" + objectId))
                    .andExpect(status().isOk())
                    .andExpect(content().contentType(MediaType.IMAGE_JPEG));
        }

        @Test
        @WithAnonymousUser
        @DisplayName("returns correct content-type for GIF")
        void getImage_gif_correctContentType() throws Exception {
            byte[] imageBytes = new byte[]{'G', 'I', 'F', '8', '9', 'a'}; // GIF magic bytes
            String objectId = "editor-images/animation.gif";

            when(storageService.download(objectId))
                    .thenReturn(new ByteArrayInputStream(imageBytes));

            mockMvc.perform(get("/api/images/" + objectId))
                    .andExpect(status().isOk())
                    .andExpect(content().contentType(MediaType.IMAGE_GIF));
        }

        @Test
        @WithAnonymousUser
        @DisplayName("returns correct content-type for WebP")
        void getImage_webp_correctContentType() throws Exception {
            byte[] imageBytes = new byte[]{'R', 'I', 'F', 'F', 0, 0, 0, 0, 'W', 'E', 'B', 'P'};
            String objectId = "editor-images/modern.webp";

            when(storageService.download(objectId))
                    .thenReturn(new ByteArrayInputStream(imageBytes));

            mockMvc.perform(get("/api/images/" + objectId))
                    .andExpect(status().isOk())
                    .andExpect(content().contentType("image/webp"));
        }

        @Test
        @WithAnonymousUser
        @DisplayName("returns 404 for non-existent image")
        void getImage_notFound_returns404() throws Exception {
            String objectId = "editor-images/non-existent.png";

            when(storageService.download(objectId))
                    .thenThrow(new RuntimeException("Object not found"));

            mockMvc.perform(get("/api/images/" + objectId))
                    .andExpect(status().isNotFound());
        }

        @Test
        @WithMockUser
        @DisplayName("authenticated user can also access image proxy")
        void getImage_authenticated_success() throws Exception {
            byte[] imageBytes = new byte[]{(byte) 0x89, 'P', 'N', 'G'};
            String objectId = "editor-images/test.png";

            when(storageService.download(objectId))
                    .thenReturn(new ByteArrayInputStream(imageBytes));

            mockMvc.perform(get("/api/images/" + objectId))
                    .andExpect(status().isOk())
                    .andExpect(content().bytes(imageBytes));
        }

        @Test
        @WithAnonymousUser
        @DisplayName("handles nested paths correctly")
        void getImage_nestedPath_success() throws Exception {
            byte[] imageBytes = new byte[]{(byte) 0x89, 'P', 'N', 'G'};
            String objectId = "pages/123/gallery/image.png";

            when(storageService.download(objectId))
                    .thenReturn(new ByteArrayInputStream(imageBytes));

            mockMvc.perform(get("/api/images/" + objectId))
                    .andExpect(status().isOk())
                    .andExpect(content().bytes(imageBytes));
        }
    }
}
