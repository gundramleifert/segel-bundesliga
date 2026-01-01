package de.segelbundesliga.service;

import de.segelbundesliga.domain.Sponsor;
import de.segelbundesliga.dto.SponsorDto;
import de.segelbundesliga.repository.SponsorRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
@RequiredArgsConstructor
@Transactional
public class SponsorService {

    private final SponsorRepository repository;

    public SponsorDto.Response create(SponsorDto.Create dto) {
        Sponsor entity = new Sponsor();
        entity.setName(dto.getName());
        entity.setDescription(dto.getDescription());
        entity.setDescriptionEn(dto.getDescriptionEn());
        entity.setLogoImage(dto.getLogoImage());
        entity.setWebsiteUrl(dto.getWebsiteUrl());
        entity.setTier(dto.getTier());
        entity.setSortOrder(dto.getSortOrder());
        entity.setActive(dto.getActive());

        return toResponse(repository.save(entity));
    }

    @Transactional(readOnly = true)
    public SponsorDto.Response getById(Long id) {
        return repository.findById(id)
                .map(this::toResponse)
                .orElseThrow(() -> new EntityNotFoundException("Sponsor", id));
    }

    @Transactional(readOnly = true)
    public Page<SponsorDto.ListItem> getAll(Pageable pageable) {
        return repository.findAll(pageable).map(this::toListItem);
    }

    @Transactional(readOnly = true)
    public List<SponsorDto.ListItem> getActiveSponsors() {
        return repository.findAllActiveOrderedByTier().stream()
                .map(this::toListItem)
                .toList();
    }

    public SponsorDto.Response update(Long id, SponsorDto.Update dto) {
        Sponsor entity = repository.findById(id)
                .orElseThrow(() -> new EntityNotFoundException("Sponsor", id));

        if (dto.getName() != null) entity.setName(dto.getName());
        if (dto.getDescription() != null) entity.setDescription(dto.getDescription());
        if (dto.getDescriptionEn() != null) entity.setDescriptionEn(dto.getDescriptionEn());
        if (dto.getLogoImage() != null) entity.setLogoImage(dto.getLogoImage());
        if (dto.getWebsiteUrl() != null) entity.setWebsiteUrl(dto.getWebsiteUrl());
        if (dto.getTier() != null) entity.setTier(dto.getTier());
        if (dto.getSortOrder() != null) entity.setSortOrder(dto.getSortOrder());
        if (dto.getActive() != null) entity.setActive(dto.getActive());

        return toResponse(repository.save(entity));
    }

    public void delete(Long id) {
        if (!repository.existsById(id)) {
            throw new EntityNotFoundException("Sponsor", id);
        }
        repository.deleteById(id);
    }

    private SponsorDto.Response toResponse(Sponsor entity) {
        SponsorDto.Response dto = new SponsorDto.Response();
        dto.setId(entity.getId());
        dto.setName(entity.getName());
        dto.setDescription(entity.getDescription());
        dto.setDescriptionEn(entity.getDescriptionEn());
        dto.setLogoImage(entity.getLogoImage());
        dto.setWebsiteUrl(entity.getWebsiteUrl());
        dto.setTier(entity.getTier());
        dto.setSortOrder(entity.getSortOrder());
        dto.setActive(entity.getActive());
        dto.setCreatedAt(entity.getCreatedAt());
        dto.setUpdatedAt(entity.getUpdatedAt());
        return dto;
    }

    private SponsorDto.ListItem toListItem(Sponsor entity) {
        SponsorDto.ListItem dto = new SponsorDto.ListItem();
        dto.setId(entity.getId());
        dto.setName(entity.getName());
        dto.setLogoImage(entity.getLogoImage());
        dto.setWebsiteUrl(entity.getWebsiteUrl());
        dto.setTier(entity.getTier());
        dto.setSortOrder(entity.getSortOrder());
        dto.setActive(entity.getActive());
        return dto;
    }
}
