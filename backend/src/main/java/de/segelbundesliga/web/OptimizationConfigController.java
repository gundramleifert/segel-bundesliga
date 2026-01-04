package de.segelbundesliga.web;

import de.segelbundesliga.dto.OptimizationConfigDto;
import de.segelbundesliga.service.OptimizationConfigService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.stream.Collectors;

@RestController
@RequestMapping("/api/optimization-configs")
@RequiredArgsConstructor
public class OptimizationConfigController {

    private final OptimizationConfigService service;

    @GetMapping
    public List<OptimizationConfigDto.Response> getAllConfigs() {
        return service.getAllConfigs().stream()
                .map(OptimizationConfigDto.Response::from)
                .collect(Collectors.toList());
    }

    @GetMapping("/{id}")
    public OptimizationConfigDto.Response getConfig(@PathVariable Long id) {
        return OptimizationConfigDto.Response.from(service.getById(id));
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    @PreAuthorize("hasRole('ADMIN')")
    public OptimizationConfigDto.Response createConfig(@Valid @RequestBody OptimizationConfigDto.Create dto) {
        return OptimizationConfigDto.Response.from(service.create(dto));
    }

    @PutMapping("/{id}")
    @PreAuthorize("hasRole('ADMIN')")
    public OptimizationConfigDto.Response updateConfig(
            @PathVariable Long id,
            @Valid @RequestBody OptimizationConfigDto.Update dto) {
        return OptimizationConfigDto.Response.from(service.update(id, dto));
    }

    @DeleteMapping("/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    @PreAuthorize("hasRole('ADMIN')")
    public void deleteConfig(@PathVariable Long id) {
        service.delete(id);
    }
}
