package de.segelbundesliga.web;

import de.segelbundesliga.config.ImageUploadConfig;
import de.segelbundesliga.service.StorageService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.server.ResponseStatusException;

import javax.imageio.ImageIO;
import java.awt.image.BufferedImage;
import java.io.IOException;
import java.util.Map;

@RestController
@RequestMapping("/api/storage")
@RequiredArgsConstructor
public class StorageController {

    private final StorageService storageService;
    private final ImageUploadConfig imageConfig;

    /**
     * Upload a file and return objectId + presigned URL for immediate display.
     * Used by rich text editor for inline image uploads.
     *
     * Restrictions:
     * - Only JPG and PNG formats allowed
     * - Max file size: 2 MB
     * - Max dimensions: 1920x1080
     */
    @PostMapping("/upload")
    @ResponseStatus(HttpStatus.CREATED)
    @PreAuthorize("hasRole('ADMIN')")
    public Map<String, String> upload(@RequestParam("file") MultipartFile file) throws Exception {
        validateImage(file);

        String objectId = storageService.upload(file, "editor-images");
        String url = storageService.getPresignedUrl(objectId, 60);
        return Map.of(
                "objectId", objectId,
                "url", url
        );
    }

    private void validateImage(MultipartFile file) {
        // Check if file is empty
        if (file.isEmpty()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "File is empty");
        }

        // Check file size
        if (file.getSize() > imageConfig.getMaxFileSize()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                    String.format("File size exceeds maximum of %d MB", imageConfig.getMaxFileSize() / (1024 * 1024)));
        }

        // Check content type
        String contentType = file.getContentType();
        if (contentType == null || !imageConfig.getAllowedContentTypes().contains(contentType.toLowerCase())) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                    "Only " + String.join(", ", imageConfig.getAllowedContentTypes()) + " images are allowed");
        }

        // Check file extension
        String filename = file.getOriginalFilename();
        if (filename != null) {
            String lowerFilename = filename.toLowerCase();
            boolean validExtension = imageConfig.getAllowedExtensions().stream().anyMatch(lowerFilename::endsWith);
            if (!validExtension) {
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                        "Only " + String.join(", ", imageConfig.getAllowedExtensions()) + " files are allowed");
            }
        }

        // Check image dimensions
        try {
            BufferedImage image = ImageIO.read(file.getInputStream());
            if (image == null) {
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                        "Could not read image file");
            }
            if (image.getWidth() > imageConfig.getMaxWidth() || image.getHeight() > imageConfig.getMaxHeight()) {
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                        String.format("Image dimensions exceed maximum of %dx%d pixels (uploaded: %dx%d)",
                                imageConfig.getMaxWidth(), imageConfig.getMaxHeight(), image.getWidth(), image.getHeight()));
            }
        } catch (IOException e) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                    "Could not process image file");
        }
    }

    /**
     * Get a fresh presigned URL for an existing object.
     */
    @GetMapping("/url")
    public Map<String, String> getPresignedUrl(@RequestParam String objectId) throws Exception {
        String url = storageService.getPresignedUrl(objectId, 60);
        return Map.of("url", url);
    }

    /**
     * Get image upload configuration for client-side validation.
     */
    @GetMapping("/config")
    public Map<String, Object> getUploadConfig() {
        return Map.of(
                "maxFileSize", imageConfig.getMaxFileSize(),
                "maxWidth", imageConfig.getMaxWidth(),
                "maxHeight", imageConfig.getMaxHeight(),
                "allowedContentTypes", imageConfig.getAllowedContentTypes(),
                "allowedExtensions", imageConfig.getAllowedExtensions()
        );
    }
}
