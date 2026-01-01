package de.segelbundesliga.dto;

import de.segelbundesliga.domain.Sponsor.SponsorTier;
import jakarta.validation.constraints.NotBlank;
import lombok.Data;

import java.time.Instant;

public class SponsorDto {

    @Data
    public static class Create {
        @NotBlank
        private String name;
        private String description;
        private String descriptionEn;
        private String logoImage;
        private String websiteUrl;
        private SponsorTier tier = SponsorTier.BRONZE;
        private Integer sortOrder = 0;
        private Boolean active = true;
    }

    @Data
    public static class Update {
        private String name;
        private String description;
        private String descriptionEn;
        private String logoImage;
        private String websiteUrl;
        private SponsorTier tier;
        private Integer sortOrder;
        private Boolean active;
    }

    @Data
    public static class Response {
        private Long id;
        private String name;
        private String description;
        private String descriptionEn;
        private String logoImage;
        private String websiteUrl;
        private SponsorTier tier;
        private Integer sortOrder;
        private Boolean active;
        private Instant createdAt;
        private Instant updatedAt;
    }

    @Data
    public static class ListItem {
        private Long id;
        private String name;
        private String logoImage;
        private String websiteUrl;
        private SponsorTier tier;
        private Integer sortOrder;
        private Boolean active;
    }
}
