package de.segelbundesliga.web;

import de.segelbundesliga.dto.PageDto;
import de.segelbundesliga.service.PageService;
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
@RequestMapping("/api/pages")
@RequiredArgsConstructor
public class PageController {

    private final PageService service;
    private final StorageService storageService;

    // === Public Endpoints ===

    @GetMapping("/public")
    public List<PageDto.ListItem> getPublicPages() {
        return service.getPublicPages();
    }

    @GetMapping("/public/{slug}")
    public PageDto.Response getPublicBySlug(@PathVariable String slug) {
        return service.getBySlug(slug);
    }

    @GetMapping("/menu")
    public List<PageDto.ListItem> getMenuPages(
            @RequestParam(defaultValue = "true") boolean publicOnly) {
        return service.getMenuPages(publicOnly);
    }

    // === Protected Endpoints ===

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    @PreAuthorize("hasRole('ADMIN')")
    public PageDto.Response create(@Valid @RequestBody PageDto.Create dto) {
        return service.create(dto);
    }

    @GetMapping("/{id}")
    public PageDto.Response getById(@PathVariable Long id) {
        return service.getById(id);
    }

    @GetMapping
    public Page<PageDto.ListItem> getAll(Pageable pageable) {
        return service.getAll(pageable);
    }

    @PutMapping("/{id}")
    @PreAuthorize("hasRole('ADMIN')")
    public PageDto.Response update(
            @PathVariable Long id,
            @Valid @RequestBody PageDto.Update dto) {
        return service.update(id, dto);
    }

    @DeleteMapping("/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    @PreAuthorize("hasRole('ADMIN')")
    public void delete(@PathVariable Long id) {
        service.delete(id);
    }

    @PostMapping("/{id}/images")
    @PreAuthorize("hasRole('ADMIN')")
    public String uploadImage(
            @PathVariable Long id,
            @RequestParam("file") MultipartFile file) throws Exception {
        String imageId = storageService.upload(file, "pages/" + id);
        service.addImage(id, imageId);
        return imageId;
    }
}
