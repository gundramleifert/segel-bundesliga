package de.segelbundesliga.domain;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;

@Entity
@Table(name = "posts")
@Getter
@Setter
@NoArgsConstructor
public class Post extends BaseEntity {

    @Column(nullable = false)
    private String title;

    @Column(name = "title_en")
    private String titleEn;

    @Column(nullable = false, unique = true)
    private String slug;

    @Column(columnDefinition = "text")
    private String excerpt;

    @Column(name = "excerpt_en", columnDefinition = "text")
    private String excerptEn;

    @Column(nullable = false, columnDefinition = "text")
    private String content;

    @Column(name = "content_en", columnDefinition = "text")
    private String contentEn;

    @Column(name = "featured_image")
    private String featuredImage;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private PostStatus status = PostStatus.DRAFT;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private Visibility visibility = Visibility.PUBLIC;

    @Column(name = "published_at")
    private Instant publishedAt;

    @ElementCollection
    @CollectionTable(name = "post_images", joinColumns = @JoinColumn(name = "post_id"))
    @Column(name = "image_id")
    private List<String> images = new ArrayList<>();

    @ElementCollection
    @CollectionTable(name = "post_tags", joinColumns = @JoinColumn(name = "post_id"))
    @Column(name = "tag")
    private List<String> tags = new ArrayList<>();

    public enum PostStatus {
        DRAFT,
        PUBLISHED,
        ARCHIVED
    }

    public enum Visibility {
        PUBLIC,
        INTERNAL
    }
}
