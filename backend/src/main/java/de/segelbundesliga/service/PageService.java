package de.segelbundesliga.service;

import de.segelbundesliga.domain.Page;
import de.segelbundesliga.dto.PageDto;
import de.segelbundesliga.repository.PageRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.List;

@Service
@RequiredArgsConstructor
@Transactional
public class PageService {

    private final PageRepository repository;

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
    public org.springframework.data.domain.Page<PageDto.ListItem> getAll(Pageable pageable) {
        return repository.findAll(pageable).map(this::toListItem);
    }

    @Transactional(readOnly = true)
    public List<PageDto.ListItem> getPublicPages() {
        return repository.findPublicPages().stream()
                .map(this::toListItem)
                .toList();
    }

    @Transactional(readOnly = true)
    public List<PageDto.ListItem> getMenuPages(boolean publicOnly) {
        List<Page> pages = publicOnly
                ? repository.findPublicMenuPages()
                : repository.findMenuPages();
        return pages.stream().map(this::toListItem).toList();
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
        if (dto.getParentId() != null) {
            Page parent = repository.findById(dto.getParentId())
                    .orElseThrow(() -> new EntityNotFoundException("Parent Page", dto.getParentId()));
            entity.setParent(parent);
        }

        return toResponse(repository.save(entity));
    }

    public void delete(Long id) {
        if (!repository.existsById(id)) {
            throw new EntityNotFoundException("Page", id);
        }
        repository.deleteById(id);
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
        return dto;
    }
}
