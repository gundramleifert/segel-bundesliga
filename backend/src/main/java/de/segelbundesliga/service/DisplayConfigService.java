package de.segelbundesliga.service;

import de.segelbundesliga.domain.DisplayConfig;
import de.segelbundesliga.dto.DisplayConfigDto;
import de.segelbundesliga.repository.DisplayConfigRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
public class DisplayConfigService {

    @Autowired
    private DisplayConfigRepository repository;

    public List<DisplayConfig> getAllConfigs() {
        return repository.findAll();
    }

    public DisplayConfig getById(Long id) {
        return repository.findById(id)
            .orElseThrow(() -> new IllegalArgumentException("DisplayConfig not found: " + id));
    }

    /**
     * Get display config or return default (first system default)
     */
    public DisplayConfig getOrDefault(DisplayConfig config) {
        if (config != null) {
            return config;
        }
        return repository.findBySystemDefaultTrue().stream()
            .findFirst()
            .orElseThrow(() -> new IllegalStateException("No default display config found"));
    }

    @Transactional
    public DisplayConfig create(DisplayConfigDto.Create dto) {
        DisplayConfig config = new DisplayConfig();
        config.setName(dto.getName());
        config.setDescription(dto.getDescription());
        config.setSystemDefault(false);
        config.setFontFamily(dto.getFontFamily());
        config.setFontSize(dto.getFontSize());
        config.setOrientation(dto.getOrientation());
        return repository.save(config);
    }

    @Transactional
    public DisplayConfig update(Long id, DisplayConfigDto.Update dto) {
        DisplayConfig config = getById(id);
        if (config.isSystemDefault()) {
            throw new IllegalStateException("Cannot modify system default configs");
        }

        if (dto.getName() != null) config.setName(dto.getName());
        if (dto.getDescription() != null) config.setDescription(dto.getDescription());
        if (dto.getFontFamily() != null) config.setFontFamily(dto.getFontFamily());
        if (dto.getFontSize() != null) config.setFontSize(dto.getFontSize());
        if (dto.getOrientation() != null) config.setOrientation(dto.getOrientation());

        return repository.save(config);
    }

    @Transactional
    public void delete(Long id) {
        DisplayConfig config = getById(id);
        if (config.isSystemDefault()) {
            throw new IllegalStateException("Cannot delete system default configs");
        }
        repository.delete(config);
    }
}
