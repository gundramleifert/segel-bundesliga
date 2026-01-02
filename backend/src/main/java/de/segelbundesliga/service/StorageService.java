package de.segelbundesliga.service;

import io.minio.*;
import io.minio.errors.*;
import io.minio.http.Method;
import jakarta.annotation.PostConstruct;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.io.InputStream;
import java.security.InvalidKeyException;
import java.security.NoSuchAlgorithmException;
import java.util.UUID;
import java.util.concurrent.TimeUnit;

@Service
public class StorageService {

    private static final Logger log = LoggerFactory.getLogger(StorageService.class);

    private final MinioClient minioClient;

    @Value("${minio.bucket:segel-bundesliga}")
    private String defaultBucket;

    public StorageService(MinioClient minioClient) {
        this.minioClient = minioClient;
    }

    /**
     * Initialisiert den Default-Bucket falls nicht vorhanden
     */
    @PostConstruct
    public void initBucket() {
        try {
            boolean exists = minioClient.bucketExists(BucketExistsArgs.builder()
                    .bucket(defaultBucket)
                    .build());
            if (!exists) {
                minioClient.makeBucket(MakeBucketArgs.builder()
                        .bucket(defaultBucket)
                        .build());
                log.info("Bucket '{}' created", defaultBucket);
            }
        } catch (Exception e) {
            log.error("Failed to initialize bucket", e);
        }
    }

    /**
     * Lädt eine Datei hoch und gibt die Object-ID zurück
     */
    public String upload(MultipartFile file, String folder) throws Exception {
        String objectId = folder + "/" + UUID.randomUUID() + "_" + sanitizeFilename(file.getOriginalFilename());

        try (InputStream is = file.getInputStream()) {
            minioClient.putObject(PutObjectArgs.builder()
                    .bucket(defaultBucket)
                    .object(objectId)
                    .stream(is, file.getSize(), -1)
                    .contentType(file.getContentType())
                    .build());
        }

        log.info("Uploaded file: {}", objectId);
        return objectId;
    }

    /**
     * Lädt eine Datei herunter
     */
    public InputStream download(String objectId) throws Exception {
        return minioClient.getObject(GetObjectArgs.builder()
                .bucket(defaultBucket)
                .object(objectId)
                .build());
    }

    /**
     * Generiert eine temporäre URL für den Direktzugriff (z.B. für Bilder im Browser)
     */
    public String getPresignedUrl(String objectId, int expiryMinutes) throws Exception {
        return minioClient.getPresignedObjectUrl(GetPresignedObjectUrlArgs.builder()
                .method(Method.GET)
                .bucket(defaultBucket)
                .object(objectId)
                .expiry(expiryMinutes, TimeUnit.MINUTES)
                .build());
    }

    /**
     * Löscht eine Datei
     */
    public void delete(String objectId) throws Exception {
        minioClient.removeObject(RemoveObjectArgs.builder()
                .bucket(defaultBucket)
                .object(objectId)
                .build());
        log.info("Deleted file: {}", objectId);
    }

    private String sanitizeFilename(String filename) {
        if (filename == null) return "file";
        return filename.replaceAll("[^a-zA-Z0-9._-]", "_");
    }
}
