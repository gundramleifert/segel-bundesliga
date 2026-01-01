package de.segelbundesliga.dto;

import de.segelbundesliga.domain.Page.FooterSection;
import de.segelbundesliga.domain.Page.Visibility;
import jakarta.validation.constraints.NotBlank;
import lombok.Data;

import java.time.Instant;
import java.util.List;

public class PageDto {

    @Data
    public static class Create {
        @NotBlank
        private String title;
        private String titleEn;
        @NotBlank
        private String slug;
        @NotBlank
        private String content;
        private String contentEn;
        private String featuredImage;
        private Visibility visibility = Visibility.PUBLIC;
        private Integer sortOrder = 0;
        private Boolean showInMenu = false;
        private Long parentId;
        private FooterSection footerSection;
    }

    @Data
    public static class Update {
        private String title;
        private String titleEn;
        private String slug;
        private String content;
        private String contentEn;
        private String featuredImage;
        private Visibility visibility;
        private Integer sortOrder;
        private Boolean showInMenu;
        private Long parentId;
        private FooterSection footerSection;
    }

    @Data
    public static class Response {
        private Long id;
        private String title;
        private String titleEn;
        private String slug;
        private String content;
        private String contentEn;
        private String featuredImage;
        private Visibility visibility;
        private Integer sortOrder;
        private Boolean showInMenu;
        private Long parentId;
        private FooterSection footerSection;
        private List<String> images;
        private Instant createdAt;
        private Instant updatedAt;
    }

    @Data
    public static class ListItem {
        private Long id;
        private String title;
        private String titleEn;
        private String slug;
        private Visibility visibility;
        private Integer sortOrder;
        private Boolean showInMenu;
        private Long parentId;
        private FooterSection footerSection;
    }
}
