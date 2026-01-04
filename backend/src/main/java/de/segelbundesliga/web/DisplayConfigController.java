package de.segelbundesliga.web;

import de.segelbundesliga.dto.DisplayConfigDto;
import de.segelbundesliga.service.DisplayConfigService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.stream.Collectors;

@RestController
@RequestMapping("/api/display-configs")
@RequiredArgsConstructor
public class DisplayConfigController {

    private final DisplayConfigService service;

    @GetMapping
    public List<DisplayConfigDto.Response> getAllConfigs() {
        return service.getAllConfigs().stream()
                .map(DisplayConfigDto.Response::from)
                .collect(Collectors.toList());
    }

    @GetMapping("/{id}")
    public DisplayConfigDto.Response getConfig(@PathVariable Long id) {
        return DisplayConfigDto.Response.from(service.getById(id));
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    @PreAuthorize("hasRole('ADMIN')")
    public DisplayConfigDto.Response createConfig(@Valid @RequestBody DisplayConfigDto.Create dto) {
        return DisplayConfigDto.Response.from(service.create(dto));
    }

    @PutMapping("/{id}")
    @PreAuthorize("hasRole('ADMIN')")
    public DisplayConfigDto.Response updateConfig(
            @PathVariable Long id,
            @Valid @RequestBody DisplayConfigDto.Update dto) {
        return DisplayConfigDto.Response.from(service.update(id, dto));
    }

    @DeleteMapping("/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    @PreAuthorize("hasRole('ADMIN')")
    public void deleteConfig(@PathVariable Long id) {
        service.delete(id);
    }
}
