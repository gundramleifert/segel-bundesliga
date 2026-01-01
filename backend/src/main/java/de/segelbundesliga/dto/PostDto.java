package de.segelbundesliga.dto;

import de.segelbundesliga.domain.Post.PostStatus;
import de.segelbundesliga.domain.Post.Visibility;
import jakarta.validation.constraints.NotBlank;
import lombok.Data;

import java.time.Instant;
import java.util.List;

public class PostDto {

    @Data
    public static class Create {
        @NotBlank
        private String title;
        private String titleEn;
        @NotBlank
        private String slug;
        private String excerpt;
        private String excerptEn;
        @NotBlank
        private String content;
        private String contentEn;
        private String featuredImage;
        private Visibility visibility = Visibility.PUBLIC;
        private List<String> tags;
    }

    @Data
    public static class Update {
        private String title;
        private String titleEn;
        private String slug;
        private String excerpt;
        private String excerptEn;
        private String content;
        private String contentEn;
        private String featuredImage;
        private PostStatus status;
        private Visibility visibility;
        private List<String> tags;
    }

    @Data
    public static class Response {
        private Long id;
        private String title;
        private String titleEn;
        private String slug;
        private String excerpt;
        private String excerptEn;
        private String content;
        private String contentEn;
        private String featuredImage;
        private PostStatus status;
        private Visibility visibility;
        private Instant publishedAt;
        private List<String> images;
        private List<String> tags;
        private Instant createdAt;
        private Instant updatedAt;
    }

    @Data
    public static class ListItem {
        private Long id;
        private String title;
        private String titleEn;
        private String slug;
        private String excerpt;
        private String excerptEn;
        private String featuredImage;
        private PostStatus status;
        private Visibility visibility;
        private Instant publishedAt;
        private List<String> tags;
    }
}
