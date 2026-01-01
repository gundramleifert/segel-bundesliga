package de.segelbundesliga.web;

import de.segelbundesliga.dto.TournamentDto;
import de.segelbundesliga.service.TournamentService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.http.HttpStatus;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/tournaments")
@RequiredArgsConstructor
public class TournamentController {

    private final TournamentService service;

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public TournamentDto.Response create(
            @Valid @RequestBody TournamentDto.Create dto,
            @AuthenticationPrincipal Jwt jwt) {
        return service.create(dto, jwt.getSubject());
    }

    @GetMapping("/{id}")
    public TournamentDto.Response getById(@PathVariable Long id) {
        return service.getById(id);
    }

    @GetMapping
    public Page<TournamentDto.ListItem> getAll(Pageable pageable) {
        return service.getAll(pageable);
    }

    @GetMapping("/my")
    public Page<TournamentDto.ListItem> getMy(
            Pageable pageable,
            @AuthenticationPrincipal Jwt jwt) {
        return service.getByOwner(jwt.getSubject(), pageable);
    }

    @PutMapping("/{id}")
    public TournamentDto.Response update(
            @PathVariable Long id,
            @Valid @RequestBody TournamentDto.Update dto,
            @AuthenticationPrincipal Jwt jwt) {
        checkOwnership(id, jwt);
        return service.update(id, dto);
    }

    @DeleteMapping("/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void delete(
            @PathVariable Long id,
            @AuthenticationPrincipal Jwt jwt) {
        checkOwnership(id, jwt);
        service.delete(id);
    }

    private void checkOwnership(Long id, Jwt jwt) {
        if (!service.isOwner(id, jwt.getSubject())) {
            throw new ForbiddenException("You are not the owner of this tournament");
        }
    }
}
