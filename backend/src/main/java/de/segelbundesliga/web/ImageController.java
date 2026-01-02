package de.segelbundesliga.web;

import de.segelbundesliga.service.StorageService;
import jakarta.servlet.http.HttpServletRequest;
import lombok.RequiredArgsConstructor;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.io.InputStream;

/**
 * Public image proxy endpoint.
 * Serves images from MinIO storage without requiring authentication.
 * This allows images embedded in pages to remain accessible indefinitely,
 * unlike presigned URLs which expire after 60 minutes.
 */
@RestController
@RequestMapping("/api/images")
@RequiredArgsConstructor
public class ImageController {

    private final StorageService storageService;

    /**
     * Proxy endpoint for serving images.
     * Accepts any path after /api/images/ as the objectId.
     * Example: /api/images/editor-images/uuid_filename.png
     */
    @GetMapping("/**")
    public ResponseEntity<byte[]> getImage(HttpServletRequest request) {
        // Extract objectId from path (everything after /api/images/)
        String objectId = request.getRequestURI().substring("/api/images/".length());

        if (objectId.isEmpty()) {
            return ResponseEntity.badRequest().build();
        }

        try {
            InputStream inputStream = storageService.download(objectId);
            byte[] imageBytes = inputStream.readAllBytes();
            inputStream.close();

            MediaType contentType = determineContentType(objectId);

            return ResponseEntity.ok()
                    .contentType(contentType)
                    .body(imageBytes);
        } catch (Exception e) {
            return ResponseEntity.notFound().build();
        }
    }

    private MediaType determineContentType(String objectId) {
        String lowerCase = objectId.toLowerCase();
        if (lowerCase.endsWith(".png")) {
            return MediaType.IMAGE_PNG;
        } else if (lowerCase.endsWith(".jpg") || lowerCase.endsWith(".jpeg")) {
            return MediaType.IMAGE_JPEG;
        } else if (lowerCase.endsWith(".gif")) {
            return MediaType.IMAGE_GIF;
        } else if (lowerCase.endsWith(".webp")) {
            return MediaType.parseMediaType("image/webp");
        } else if (lowerCase.endsWith(".svg")) {
            return MediaType.parseMediaType("image/svg+xml");
        } else {
            return MediaType.APPLICATION_OCTET_STREAM;
        }
    }
}
