package de.segelbundesliga.dto;

import de.segelbundesliga.domain.DisplayConfig;
import de.segelbundesliga.domain.FontFamily;
import de.segelbundesliga.domain.PageOrientation;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Data;

import java.time.Instant;

public class DisplayConfigDto {

    @Data
    public static class Create {
        @NotBlank
        private String name;
        private String description;

        @NotNull
        private FontFamily fontFamily = FontFamily.HELVETICA;

        @NotNull
        @Min(8)
        @Max(16)
        private Integer fontSize = 10;

        @NotNull
        private PageOrientation orientation = PageOrientation.LANDSCAPE;
    }

    @Data
    public static class Update {
        private String name;
        private String description;
        private FontFamily fontFamily;

        @Min(8)
        @Max(16)
        private Integer fontSize;

        private PageOrientation orientation;
    }

    @Data
    public static class Response {
        private Long id;
        private String name;
        private String description;
        private boolean systemDefault;
        private FontFamily fontFamily;
        private Integer fontSize;
        private PageOrientation orientation;
        private Instant createdAt;
        private Instant updatedAt;

        public static Response from(DisplayConfig entity) {
            Response dto = new Response();
            dto.setId(entity.getId());
            dto.setName(entity.getName());
            dto.setDescription(entity.getDescription());
            dto.setSystemDefault(entity.isSystemDefault());
            dto.setFontFamily(entity.getFontFamily());
            dto.setFontSize(entity.getFontSize());
            dto.setOrientation(entity.getOrientation());
            dto.setCreatedAt(entity.getCreatedAt());
            dto.setUpdatedAt(entity.getUpdatedAt());
            return dto;
        }
    }
}
