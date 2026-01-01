package de.segelbundesliga.domain;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.util.ArrayList;
import java.util.List;

@Entity
@Table(name = "pages")
@Getter
@Setter
@NoArgsConstructor
public class Page extends BaseEntity {

    @Column(nullable = false)
    private String title;

    @Column(name = "title_en")
    private String titleEn;

    @Column(nullable = false, unique = true)
    private String slug;

    @Column(nullable = false, columnDefinition = "text")
    private String content;

    @Column(name = "content_en", columnDefinition = "text")
    private String contentEn;

    @Column(name = "featured_image")
    private String featuredImage;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private Visibility visibility = Visibility.PUBLIC;

    @Column(name = "sort_order")
    private Integer sortOrder = 0;

    @Column(name = "show_in_menu")
    private Boolean showInMenu = false;

    @Column(name = "parent_id")
    private Long parentId;

    @ElementCollection
    @CollectionTable(name = "page_images", joinColumns = @JoinColumn(name = "page_id"))
    @Column(name = "image_id")
    private List<String> images = new ArrayList<>();

    public enum Visibility {
        PUBLIC,
        INTERNAL
    }
}
