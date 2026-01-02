package de.segelbundesliga.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Configuration;

import java.util.Set;

@Data
@Configuration
@ConfigurationProperties(prefix = "application.image-upload")
public class ImageUploadConfig {

    /**
     * Maximum file size in bytes (default: 2 MB)
     */
    private long maxFileSize = 2 * 1024 * 1024;

    /**
     * Maximum image width in pixels (default: 1920)
     */
    private int maxWidth = 1920;

    /**
     * Maximum image height in pixels (default: 1080)
     */
    private int maxHeight = 1080;

    /**
     * Allowed content types (default: image/jpeg, image/png)
     */
    private Set<String> allowedContentTypes = Set.of("image/jpeg", "image/png");

    /**
     * Allowed file extensions (default: .jpg, .jpeg, .png)
     */
    private Set<String> allowedExtensions = Set.of(".jpg", ".jpeg", ".png");
}
