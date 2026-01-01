package de.segelbundesliga.web;

import de.segelbundesliga.dto.SponsorDto;
import de.segelbundesliga.service.SponsorService;
import de.segelbundesliga.service.StorageService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.http.HttpStatus;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;

@RestController
@RequestMapping("/api/sponsors")
@RequiredArgsConstructor
public class SponsorController {

    private final SponsorService service;
    private final StorageService storageService;

    // === Public Endpoints ===

    @GetMapping("/public")
    public List<SponsorDto.ListItem> getActiveSponsors() {
        return service.getActiveSponsors();
    }

    // === Protected Endpoints ===

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    @PreAuthorize("hasAnyRole('ADMIN', 'SPONSOR_MANAGE')")
    public SponsorDto.Response create(@Valid @RequestBody SponsorDto.Create dto) {
        return service.create(dto);
    }

    @GetMapping("/{id}")
    public SponsorDto.Response getById(@PathVariable Long id) {
        return service.getById(id);
    }

    @GetMapping
    @PreAuthorize("hasAnyRole('ADMIN', 'SPONSOR_MANAGE')")
    public Page<SponsorDto.ListItem> getAll(Pageable pageable) {
        return service.getAll(pageable);
    }

    @PutMapping("/{id}")
    @PreAuthorize("hasAnyRole('ADMIN', 'SPONSOR_MANAGE')")
    public SponsorDto.Response update(
            @PathVariable Long id,
            @Valid @RequestBody SponsorDto.Update dto) {
        return service.update(id, dto);
    }

    @DeleteMapping("/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    @PreAuthorize("hasAnyRole('ADMIN', 'SPONSOR_MANAGE')")
    public void delete(@PathVariable Long id) {
        service.delete(id);
    }

    @PostMapping("/{id}/logo")
    @PreAuthorize("hasAnyRole('ADMIN', 'SPONSOR_MANAGE')")
    public SponsorDto.Response uploadLogo(
            @PathVariable Long id,
            @RequestParam("file") MultipartFile file) throws Exception {
        String imageId = storageService.upload(file, "sponsors");
        SponsorDto.Update dto = new SponsorDto.Update();
        dto.setLogoImage(imageId);
        return service.update(id, dto);
    }
}
