package de.segelbundesliga.service;

import de.segelbundesliga.domain.Post;
import de.segelbundesliga.domain.Post.PostStatus;
import de.segelbundesliga.dto.PostDto;
import de.segelbundesliga.repository.PostRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.ArrayList;

@Service
@RequiredArgsConstructor
@Transactional
public class PostService {

    private final PostRepository repository;

    public PostDto.Response create(PostDto.Create dto) {
        if (repository.existsBySlug(dto.getSlug())) {
            throw new IllegalArgumentException("Slug already exists: " + dto.getSlug());
        }

        Post entity = new Post();
        entity.setTitle(dto.getTitle());
        entity.setTitleEn(dto.getTitleEn());
        entity.setSlug(dto.getSlug());
        entity.setExcerpt(dto.getExcerpt());
        entity.setExcerptEn(dto.getExcerptEn());
        entity.setContent(dto.getContent());
        entity.setContentEn(dto.getContentEn());
        entity.setFeaturedImage(dto.getFeaturedImage());
        entity.setVisibility(dto.getVisibility());
        entity.setStatus(PostStatus.DRAFT);
        if (dto.getTags() != null) {
            entity.setTags(new ArrayList<>(dto.getTags()));
        }

        return toResponse(repository.save(entity));
    }

    @Transactional(readOnly = true)
    public PostDto.Response getById(Long id) {
        return repository.findById(id)
                .map(this::toResponse)
                .orElseThrow(() -> new EntityNotFoundException("Post", id));
    }

    @Transactional(readOnly = true)
    public PostDto.Response getBySlug(String slug) {
        return repository.findBySlug(slug)
                .map(this::toResponse)
                .orElseThrow(() -> new EntityNotFoundException("Post", "slug", slug));
    }

    @Transactional(readOnly = true)
    public Page<PostDto.ListItem> getAll(Pageable pageable) {
        return repository.findAll(pageable).map(this::toListItem);
    }

    @Transactional(readOnly = true)
    public Page<PostDto.ListItem> getPublicPosts(Pageable pageable) {
        return repository.findPublicPosts(pageable).map(this::toListItem);
    }

    @Transactional(readOnly = true)
    public Page<PostDto.ListItem> getAllPublished(Pageable pageable) {
        return repository.findAllPublishedPosts(pageable).map(this::toListItem);
    }

    public PostDto.Response update(Long id, PostDto.Update dto) {
        Post entity = repository.findById(id)
                .orElseThrow(() -> new EntityNotFoundException("Post", id));

        if (dto.getTitle() != null) entity.setTitle(dto.getTitle());
        if (dto.getTitleEn() != null) entity.setTitleEn(dto.getTitleEn());
        if (dto.getSlug() != null && !dto.getSlug().equals(entity.getSlug())) {
            if (repository.existsBySlug(dto.getSlug())) {
                throw new IllegalArgumentException("Slug already exists: " + dto.getSlug());
            }
            entity.setSlug(dto.getSlug());
        }
        if (dto.getExcerpt() != null) entity.setExcerpt(dto.getExcerpt());
        if (dto.getExcerptEn() != null) entity.setExcerptEn(dto.getExcerptEn());
        if (dto.getContent() != null) entity.setContent(dto.getContent());
        if (dto.getContentEn() != null) entity.setContentEn(dto.getContentEn());
        if (dto.getFeaturedImage() != null) entity.setFeaturedImage(dto.getFeaturedImage());
        if (dto.getStatus() != null) {
            if (dto.getStatus() == PostStatus.PUBLISHED && entity.getPublishedAt() == null) {
                entity.setPublishedAt(Instant.now());
            }
            entity.setStatus(dto.getStatus());
        }
        if (dto.getVisibility() != null) entity.setVisibility(dto.getVisibility());
        if (dto.getTags() != null) entity.setTags(new ArrayList<>(dto.getTags()));

        return toResponse(repository.save(entity));
    }

    public PostDto.Response publish(Long id) {
        Post entity = repository.findById(id)
                .orElseThrow(() -> new EntityNotFoundException("Post", id));

        entity.setStatus(PostStatus.PUBLISHED);
        if (entity.getPublishedAt() == null) {
            entity.setPublishedAt(Instant.now());
        }

        return toResponse(repository.save(entity));
    }

    public void delete(Long id) {
        if (!repository.existsById(id)) {
            throw new EntityNotFoundException("Post", id);
        }
        repository.deleteById(id);
    }

    public void addImage(Long id, String imageId) {
        Post entity = repository.findById(id)
                .orElseThrow(() -> new EntityNotFoundException("Post", id));
        entity.getImages().add(imageId);
        repository.save(entity);
    }

    private PostDto.Response toResponse(Post entity) {
        PostDto.Response dto = new PostDto.Response();
        dto.setId(entity.getId());
        dto.setTitle(entity.getTitle());
        dto.setTitleEn(entity.getTitleEn());
        dto.setSlug(entity.getSlug());
        dto.setExcerpt(entity.getExcerpt());
        dto.setExcerptEn(entity.getExcerptEn());
        dto.setContent(entity.getContent());
        dto.setContentEn(entity.getContentEn());
        dto.setFeaturedImage(entity.getFeaturedImage());
        dto.setStatus(entity.getStatus());
        dto.setVisibility(entity.getVisibility());
        dto.setPublishedAt(entity.getPublishedAt());
        dto.setImages(new ArrayList<>(entity.getImages()));
        dto.setTags(new ArrayList<>(entity.getTags()));
        dto.setCreatedAt(entity.getCreatedAt());
        dto.setUpdatedAt(entity.getUpdatedAt());
        return dto;
    }

    private PostDto.ListItem toListItem(Post entity) {
        PostDto.ListItem dto = new PostDto.ListItem();
        dto.setId(entity.getId());
        dto.setTitle(entity.getTitle());
        dto.setTitleEn(entity.getTitleEn());
        dto.setSlug(entity.getSlug());
        dto.setExcerpt(entity.getExcerpt());
        dto.setExcerptEn(entity.getExcerptEn());
        dto.setFeaturedImage(entity.getFeaturedImage());
        dto.setStatus(entity.getStatus());
        dto.setVisibility(entity.getVisibility());
        dto.setPublishedAt(entity.getPublishedAt());
        dto.setTags(new ArrayList<>(entity.getTags()));
        return dto;
    }
}
