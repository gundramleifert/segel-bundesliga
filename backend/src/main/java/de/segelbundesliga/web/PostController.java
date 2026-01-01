package de.segelbundesliga.web;

import de.segelbundesliga.dto.PostDto;
import de.segelbundesliga.service.PostService;
import de.segelbundesliga.service.StorageService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.http.HttpStatus;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

@RestController
@RequestMapping("/api/posts")
@RequiredArgsConstructor
public class PostController {

    private final PostService service;
    private final StorageService storageService;

    // === Public Endpoints ===

    @GetMapping("/public")
    public Page<PostDto.ListItem> getPublicPosts(Pageable pageable) {
        return service.getPublicPosts(pageable);
    }

    @GetMapping("/public/{slug}")
    public PostDto.Response getPublicBySlug(@PathVariable String slug) {
        return service.getBySlug(slug);
    }

    // === Protected Endpoints ===

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    @PreAuthorize("hasAnyRole('ADMIN', 'BLOG_WRITE')")
    public PostDto.Response create(@Valid @RequestBody PostDto.Create dto) {
        return service.create(dto);
    }

    @GetMapping("/{id}")
    public PostDto.Response getById(@PathVariable Long id) {
        return service.getById(id);
    }

    @GetMapping
    public Page<PostDto.ListItem> getAll(Pageable pageable) {
        return service.getAll(pageable);
    }

    @GetMapping("/published")
    public Page<PostDto.ListItem> getAllPublished(Pageable pageable) {
        return service.getAllPublished(pageable);
    }

    @PutMapping("/{id}")
    @PreAuthorize("hasAnyRole('ADMIN', 'BLOG_WRITE')")
    public PostDto.Response update(
            @PathVariable Long id,
            @Valid @RequestBody PostDto.Update dto) {
        return service.update(id, dto);
    }

    @PutMapping("/{id}/publish")
    @PreAuthorize("hasAnyRole('ADMIN', 'BLOG_PUBLISH')")
    public PostDto.Response publish(@PathVariable Long id) {
        return service.publish(id);
    }

    @DeleteMapping("/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    @PreAuthorize("hasAnyRole('ADMIN', 'BLOG_WRITE')")
    public void delete(@PathVariable Long id) {
        service.delete(id);
    }

    @PostMapping("/{id}/images")
    @PreAuthorize("hasAnyRole('ADMIN', 'BLOG_WRITE')")
    public String uploadImage(
            @PathVariable Long id,
            @RequestParam("file") MultipartFile file) throws Exception {
        String imageId = storageService.upload(file, "posts/" + id);
        service.addImage(id, imageId);
        return imageId;
    }
}
