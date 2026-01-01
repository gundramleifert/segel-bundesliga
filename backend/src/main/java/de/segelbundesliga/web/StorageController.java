package de.segelbundesliga.web;

import de.segelbundesliga.service.StorageService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.util.Map;

@RestController
@RequestMapping("/api/storage")
@RequiredArgsConstructor
public class StorageController {

    private final StorageService storageService;

    /**
     * Upload a file and return objectId + presigned URL for immediate display.
     * Used by rich text editor for inline image uploads.
     */
    @PostMapping("/upload")
    @ResponseStatus(HttpStatus.CREATED)
    @PreAuthorize("hasRole('ADMIN')")
    public Map<String, String> upload(@RequestParam("file") MultipartFile file) throws Exception {
        String objectId = storageService.upload(file, "editor-images");
        String url = storageService.getPresignedUrl(objectId, 60);
        return Map.of(
                "objectId", objectId,
                "url", url
        );
    }

    /**
     * Get a fresh presigned URL for an existing object.
     */
    @GetMapping("/url")
    public Map<String, String> getPresignedUrl(@RequestParam String objectId) throws Exception {
        String url = storageService.getPresignedUrl(objectId, 60);
        return Map.of("url", url);
    }
}
