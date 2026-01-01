package de.segelbundesliga.domain;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Entity
@Table(name = "sponsors")
@Getter
@Setter
@NoArgsConstructor
public class Sponsor extends BaseEntity {

    @Column(nullable = false)
    private String name;

    @Column(columnDefinition = "text")
    private String description;

    @Column(name = "description_en", columnDefinition = "text")
    private String descriptionEn;

    @Column(name = "logo_image")
    private String logoImage;

    @Column(name = "website_url")
    private String websiteUrl;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private SponsorTier tier = SponsorTier.BRONZE;

    @Column(name = "sort_order")
    private Integer sortOrder = 0;

    @Column(nullable = false)
    private Boolean active = true;

    public enum SponsorTier {
        PLATINUM,
        GOLD,
        SILVER,
        BRONZE
    }
}
