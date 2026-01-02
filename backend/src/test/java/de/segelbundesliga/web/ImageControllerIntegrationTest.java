package de.segelbundesliga.web;

import de.segelbundesliga.service.StorageService;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.security.test.context.support.WithAnonymousUser;
import org.springframework.security.test.context.support.WithMockUser;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import java.io.ByteArrayInputStream;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

/**
 * Integration test for the image proxy endpoint.
 * Tests the full Spring context with mocked MinIO storage.
 *
 * User Story:
 * As a visitor viewing a page with embedded images,
 * I want images to load reliably without expiring,
 * So that pages remain fully functional over time.
 *
 * Acceptance Criteria:
 * - Images can be accessed via /api/images/{objectId} without authentication
 * - Correct content-type is returned based on file extension
 * - 404 is returned for non-existent images
 * - Admin can upload images and retrieve them via the proxy
 */
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@DisplayName("Image Proxy Integration Tests")
class ImageControllerIntegrationTest {

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private StorageService storageService;

    // Sample PNG image bytes (1x1 pixel transparent PNG)
    private static final byte[] SAMPLE_PNG = new byte[]{
            (byte) 0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
            0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,
            0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
            0x08, 0x06, 0x00, 0x00, 0x00, 0x1F, 0x15, (byte) 0xC4,
            (byte) 0x89, 0x00, 0x00, 0x00, 0x0A, 0x49, 0x44, 0x41,
            0x54, 0x78, (byte) 0x9C, 0x63, 0x00, 0x01, 0x00, 0x00,
            0x05, 0x00, 0x01, 0x0D, 0x0A, 0x2D, (byte) 0xB4, 0x00,
            0x00, 0x00, 0x00, 0x49, 0x45, 0x4E, 0x44, (byte) 0xAE,
            0x42, 0x60, (byte) 0x82
    };

    @Test
    @WithAnonymousUser
    @DisplayName("User Story: Anonymous user can view images embedded in pages")
    void anonymousUserCanAccessImageProxy() throws Exception {
        String objectId = "editor-images/test-image.png";
        when(storageService.download(objectId))
                .thenReturn(new ByteArrayInputStream(SAMPLE_PNG));

        mockMvc.perform(get("/api/images/" + objectId))
                .andExpect(status().isOk())
                .andExpect(content().contentType(MediaType.IMAGE_PNG))
                .andExpect(content().bytes(SAMPLE_PNG));
    }

    @Test
    @WithAnonymousUser
    @DisplayName("User Story: Broken image links return 404")
    void nonExistentImageReturns404() throws Exception {
        String objectId = "editor-images/deleted-image.png";
        when(storageService.download(objectId))
                .thenThrow(new RuntimeException("Object not found"));

        mockMvc.perform(get("/api/images/" + objectId))
                .andExpect(status().isNotFound());
    }

    @Test
    @WithMockUser(roles = "ADMIN")
    @DisplayName("User Story: Admin uploads image, then anyone can access it via proxy")
    void adminUploadAndPublicAccess() throws Exception {
        String objectId = "editor-images/uuid_uploaded.png";

        // Mock the upload
        when(storageService.upload(any(), eq("editor-images")))
                .thenReturn(objectId);
        when(storageService.getPresignedUrl(objectId, 60))
                .thenReturn("http://minio:9000/bucket/" + objectId + "?presigned=true");

        // Admin uploads image
        MockMultipartFile file = new MockMultipartFile(
                "file", "test.png", MediaType.IMAGE_PNG_VALUE, SAMPLE_PNG);

        mockMvc.perform(multipart("/api/storage/upload").file(file))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.objectId").value(objectId));

        // Mock download for proxy access
        when(storageService.download(objectId))
                .thenReturn(new ByteArrayInputStream(SAMPLE_PNG));

        // Anyone can access via proxy (simulated as anonymous in separate request)
        mockMvc.perform(get("/api/images/" + objectId))
                .andExpect(status().isOk())
                .andExpect(content().contentType(MediaType.IMAGE_PNG));
    }

    @Test
    @WithAnonymousUser
    @DisplayName("Different image formats are served with correct content-type")
    void differentImageFormatsReturnCorrectContentType() throws Exception {
        // JPEG
        when(storageService.download("images/photo.jpg"))
                .thenReturn(new ByteArrayInputStream(new byte[]{(byte)0xFF, (byte)0xD8, (byte)0xFF}));
        mockMvc.perform(get("/api/images/images/photo.jpg"))
                .andExpect(content().contentType(MediaType.IMAGE_JPEG));

        // GIF
        when(storageService.download("images/animation.gif"))
                .thenReturn(new ByteArrayInputStream("GIF89a".getBytes()));
        mockMvc.perform(get("/api/images/images/animation.gif"))
                .andExpect(content().contentType(MediaType.IMAGE_GIF));

        // WebP
        when(storageService.download("images/modern.webp"))
                .thenReturn(new ByteArrayInputStream("RIFF".getBytes()));
        mockMvc.perform(get("/api/images/images/modern.webp"))
                .andExpect(content().contentType("image/webp"));

        // SVG
        when(storageService.download("images/icon.svg"))
                .thenReturn(new ByteArrayInputStream("<svg></svg>".getBytes()));
        mockMvc.perform(get("/api/images/images/icon.svg"))
                .andExpect(content().contentType("image/svg+xml"));
    }

    @Test
    @WithAnonymousUser
    @DisplayName("Nested paths work correctly (e.g., pages/123/image.png)")
    void nestedPathsWorkCorrectly() throws Exception {
        String objectId = "pages/42/gallery/vacation.png";
        when(storageService.download(objectId))
                .thenReturn(new ByteArrayInputStream(SAMPLE_PNG));

        mockMvc.perform(get("/api/images/" + objectId))
                .andExpect(status().isOk())
                .andExpect(content().bytes(SAMPLE_PNG));
    }
}
