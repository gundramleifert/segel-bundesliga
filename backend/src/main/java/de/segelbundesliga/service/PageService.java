package de.segelbundesliga.service;

import de.segelbundesliga.domain.Page;
import de.segelbundesliga.domain.Page.Visibility;
import de.segelbundesliga.dto.PageDto;
import de.segelbundesliga.repository.PageRepository;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

@Service
@RequiredArgsConstructor
@Transactional
public class PageService {

    private static final Logger log = LoggerFactory.getLogger(PageService.class);
    private static final Pattern IMAGE_SRC_PATTERN = Pattern.compile("/api/images/([^\"'\\s>]+)");

    private final PageRepository repository;
    private final StorageService storageService;

    public PageDto.Response create(PageDto.Create dto) {
        if (repository.existsBySlug(dto.getSlug())) {
            throw new IllegalArgumentException("Slug already exists: " + dto.getSlug());
        }

        Page entity = new Page();
        entity.setTitle(dto.getTitle());
        entity.setTitleEn(dto.getTitleEn());
        entity.setSlug(dto.getSlug());
        entity.setContent(dto.getContent());
        entity.setContentEn(dto.getContentEn());
        entity.setFeaturedImage(dto.getFeaturedImage());
        entity.setVisibility(dto.getVisibility());
        entity.setSortOrder(dto.getSortOrder());
        entity.setShowInMenu(dto.getShowInMenu());
        entity.setFooterSection(dto.getFooterSection());
        if (dto.getParentId() != null) {
            Page parent = repository.findById(dto.getParentId())
                    .orElseThrow(() -> new EntityNotFoundException("Parent Page", dto.getParentId()));
            entity.setParent(parent);
        }

        return toResponse(repository.save(entity));
    }

    @Transactional(readOnly = true)
    public PageDto.Response getById(Long id) {
        return repository.findById(id)
                .map(this::toResponse)
                .orElseThrow(() -> new EntityNotFoundException("Page", id));
    }

    @Transactional(readOnly = true)
    public PageDto.Response getBySlug(String slug) {
        return repository.findBySlug(slug)
                .map(this::toResponse)
                .orElseThrow(() -> new EntityNotFoundException("Page", "slug", slug));
    }

    @Transactional(readOnly = true)
    public PageDto.Response getBySlugWithAccessCheck(String slug, boolean hasInternalAccess) {
        Page entity = repository.findBySlug(slug)
                .orElseThrow(() -> new EntityNotFoundException("Page", "slug", slug));

        // Check access: INTERNAL pages require internal access
        if (entity.getVisibility() == Page.Visibility.INTERNAL && !hasInternalAccess) {
            throw new EntityNotFoundException("Page", "slug", slug);
        }

        return toResponse(entity);
    }

    @Transactional(readOnly = true)
    public org.springframework.data.domain.Page<PageDto.ListItem> getAll(Pageable pageable) {
        return repository.findAll(pageable).map(this::toListItem);
    }

    private static final Set<Visibility> PUBLIC_ONLY = Set.of(Visibility.PUBLIC);
    private static final Set<Visibility> PUBLIC_AND_INTERNAL = Set.of(Visibility.PUBLIC, Visibility.INTERNAL);

    @Transactional(readOnly = true)
    public List<PageDto.ListItem> getPublicPages() {
        return repository.findByVisibilityOrderBySortOrderAsc(Visibility.PUBLIC).stream()
                .map(this::toListItem)
                .toList();
    }

    @Transactional(readOnly = true)
    public List<PageDto.ListItem> getVisiblePages(boolean hasInternalAccess) {
        var visibilities = hasInternalAccess ? PUBLIC_AND_INTERNAL : PUBLIC_ONLY;
        return repository.findByVisibilityInOrderBySortOrderAsc(visibilities).stream()
                .map(this::toListItem)
                .toList();
    }

    @Transactional(readOnly = true)
    public List<PageDto.ListItem> getMenuPages(boolean hasInternalAccess) {
        var visibilities = hasInternalAccess ? PUBLIC_AND_INTERNAL : PUBLIC_ONLY;
        return repository.findByShowInMenuTrueAndVisibilityInOrderBySortOrderAsc(visibilities).stream()
                .map(this::toListItem)
                .toList();
    }

    public PageDto.Response update(Long id, PageDto.Update dto) {
        Page entity = repository.findById(id)
                .orElseThrow(() -> new EntityNotFoundException("Page", id));

        if (dto.getTitle() != null) entity.setTitle(dto.getTitle());
        if (dto.getTitleEn() != null) entity.setTitleEn(dto.getTitleEn());
        if (dto.getSlug() != null && !dto.getSlug().equals(entity.getSlug())) {
            if (repository.existsBySlug(dto.getSlug())) {
                throw new IllegalArgumentException("Slug already exists: " + dto.getSlug());
            }
            entity.setSlug(dto.getSlug());
        }
        if (dto.getContent() != null) entity.setContent(dto.getContent());
        if (dto.getContentEn() != null) entity.setContentEn(dto.getContentEn());
        if (dto.getFeaturedImage() != null) entity.setFeaturedImage(dto.getFeaturedImage());
        if (dto.getVisibility() != null) entity.setVisibility(dto.getVisibility());
        if (dto.getSortOrder() != null) entity.setSortOrder(dto.getSortOrder());
        if (dto.getShowInMenu() != null) entity.setShowInMenu(dto.getShowInMenu());
        if (dto.getFooterSection() != null) entity.setFooterSection(dto.getFooterSection());
        if (dto.getParentId() != null) {
            Page parent = repository.findById(dto.getParentId())
                    .orElseThrow(() -> new EntityNotFoundException("Parent Page", dto.getParentId()));
            entity.setParent(parent);
        }

        return toResponse(repository.save(entity));
    }

    public void delete(Long id) {
        Page entity = repository.findById(id)
                .orElseThrow(() -> new EntityNotFoundException("Page", id));

        // Collect all image objectIds to delete
        Set<String> imagesToDelete = collectAllImages(entity);

        // Delete the page first
        repository.deleteById(id);

        // Then clean up images from storage
        for (String objectId : imagesToDelete) {
            try {
                storageService.delete(objectId);
                log.info("Deleted image {} for page {}", objectId, id);
            } catch (Exception e) {
                log.warn("Failed to delete image {} for page {}: {}", objectId, id, e.getMessage());
            }
        }
    }

    /**
     * Collects all image objectIds associated with a page:
     * - Featured image
     * - Images tracked in the images list
     * - Images embedded in content HTML (DE and EN)
     */
    private Set<String> collectAllImages(Page entity) {
        Set<String> images = new HashSet<>();

        // Featured image
        if (entity.getFeaturedImage() != null && !entity.getFeaturedImage().isBlank()) {
            images.add(entity.getFeaturedImage());
        }

        // Tracked images
        if (entity.getImages() != null) {
            images.addAll(entity.getImages());
        }

        // Images in content HTML
        extractImagesFromHtml(entity.getContent(), images);
        extractImagesFromHtml(entity.getContentEn(), images);

        return images;
    }

    /**
     * Extracts image objectIds from HTML content.
     * Looks for patterns like: /api/images/editor-images/uuid_filename.png
     */
    private void extractImagesFromHtml(String html, Set<String> images) {
        if (html == null || html.isBlank()) {
            return;
        }

        Matcher matcher = IMAGE_SRC_PATTERN.matcher(html);
        while (matcher.find()) {
            String objectId = matcher.group(1);
            images.add(objectId);
        }
    }

    public void addImage(Long id, String imageId) {
        Page entity = repository.findById(id)
                .orElseThrow(() -> new EntityNotFoundException("Page", id));
        entity.getImages().add(imageId);
        repository.save(entity);
    }

    private PageDto.Response toResponse(Page entity) {
        PageDto.Response dto = new PageDto.Response();
        dto.setId(entity.getId());
        dto.setTitle(entity.getTitle());
        dto.setTitleEn(entity.getTitleEn());
        dto.setSlug(entity.getSlug());
        dto.setContent(entity.getContent());
        dto.setContentEn(entity.getContentEn());
        dto.setFeaturedImage(entity.getFeaturedImage());
        dto.setVisibility(entity.getVisibility());
        dto.setSortOrder(entity.getSortOrder());
        dto.setShowInMenu(entity.getShowInMenu());
        dto.setParentId(entity.getParent() != null ? entity.getParent().getId() : null);
        dto.setFooterSection(entity.getFooterSection());
        dto.setImages(new ArrayList<>(entity.getImages()));
        dto.setCreatedAt(entity.getCreatedAt());
        dto.setUpdatedAt(entity.getUpdatedAt());
        return dto;
    }

    private PageDto.ListItem toListItem(Page entity) {
        PageDto.ListItem dto = new PageDto.ListItem();
        dto.setId(entity.getId());
        dto.setTitle(entity.getTitle());
        dto.setTitleEn(entity.getTitleEn());
        dto.setSlug(entity.getSlug());
        dto.setVisibility(entity.getVisibility());
        dto.setSortOrder(entity.getSortOrder());
        dto.setShowInMenu(entity.getShowInMenu());
        dto.setParentId(entity.getParent() != null ? entity.getParent().getId() : null);
        dto.setFooterSection(entity.getFooterSection());
        return dto;
    }
}
