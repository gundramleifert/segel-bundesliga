package de.segelbundesliga.web;

import de.segelbundesliga.domain.Tournament;
import de.segelbundesliga.dto.OptimizationDto;
import de.segelbundesliga.repository.TournamentRepository;
import de.segelbundesliga.service.OptimizerService;
import de.segelbundesliga.service.PdfExportService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ContentDisposition;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

@RestController
@RequestMapping("/api/optimization")
@RequiredArgsConstructor
public class OptimizationController {

    private final OptimizerService optimizerService;
    private final TournamentRepository tournamentRepository;
    private final PdfExportService pdfExportService;

    /**
     * Start optimization for a tournament.
     * Returns immediately, progress is streamed via SSE.
     */
    @PostMapping("/{tournamentId}/start")
    @ResponseStatus(HttpStatus.ACCEPTED)
    public void startOptimization(
            @PathVariable Long tournamentId,
            @AuthenticationPrincipal Jwt jwt) {

        Tournament tournament = getTournamentWithOwnerCheck(tournamentId, jwt);

        if (!optimizerService.hasRequiredConfig(tournament)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                    "Tournament must have teams and boats configured");
        }

        if (optimizerService.isRunning(tournamentId)) {
            throw new ResponseStatusException(HttpStatus.CONFLICT,
                    "Optimization already running for this tournament");
        }

        // Start async optimization
        optimizerService.runOptimization(tournamentId);
    }

    /**
     * SSE endpoint for optimization progress.
     * Connect before starting optimization to receive all events.
     */
    @GetMapping(value = "/{tournamentId}/progress", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter streamProgress(
            @PathVariable Long tournamentId,
            @AuthenticationPrincipal Jwt jwt) {

        getTournamentWithOwnerCheck(tournamentId, jwt);
        return optimizerService.createEmitter(tournamentId);
    }

    /**
     * Cancel a running optimization.
     */
    @PostMapping("/{tournamentId}/cancel")
    @ResponseStatus(HttpStatus.OK)
    public void cancelOptimization(
            @PathVariable Long tournamentId,
            @AuthenticationPrincipal Jwt jwt) {

        getTournamentWithOwnerCheck(tournamentId, jwt);

        if (!optimizerService.isRunning(tournamentId)) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND,
                    "No optimization running for this tournament");
        }

        optimizerService.cancelOptimization(tournamentId);
    }

    /**
     * Get optimization result.
     */
    @GetMapping("/{tournamentId}/result")
    public OptimizationDto.Result getResult(
            @PathVariable Long tournamentId,
            @AuthenticationPrincipal Jwt jwt) {

        Tournament tournament = getTournamentWithOwnerCheck(tournamentId, jwt);

        if (tournament.getSchedule() == null) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND,
                    "No optimization result available");
        }

        return optimizerService.getResult(tournamentId);
    }

    /**
     * Export tournament schedule as PDF.
     */
    @GetMapping("/{tournamentId}/export-pdf")
    public ResponseEntity<byte[]> exportPdf(
            @PathVariable Long tournamentId,
            @AuthenticationPrincipal Jwt jwt) {

        Tournament tournament = getTournamentWithOwnerCheck(tournamentId, jwt);

        if (tournament.getSchedule() == null) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND,
                    "No schedule available. Run optimization first.");
        }

        try {
            // Generate PDF
            byte[] pdfBytes = pdfExportService.generatePdf(tournamentId);

            // Return as downloadable file
            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_PDF);
            headers.setContentDisposition(
                ContentDisposition.attachment()
                    .filename(tournament.getName().replaceAll("[^a-zA-Z0-9.-]", "_") + "_schedule.pdf")
                    .build()
            );

            return ResponseEntity.ok()
                .headers(headers)
                .body(pdfBytes);

        } catch (Exception e) {
            throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR,
                    "Failed to generate PDF: " + e.getMessage(), e);
        }
    }

    /**
     * Check optimization status.
     */
    @GetMapping("/{tournamentId}/status")
    public OptimizationStatus getStatus(
            @PathVariable Long tournamentId,
            @AuthenticationPrincipal Jwt jwt) {

        Tournament tournament = getTournamentWithOwnerCheck(tournamentId, jwt);

        return new OptimizationStatus(
                tournamentId,
                tournament.getStatus().name(),
                optimizerService.isRunning(tournamentId),
                tournament.getSchedule() != null
        );
    }

    private Tournament getTournamentWithOwnerCheck(Long tournamentId, Jwt jwt) {
        Tournament tournament = tournamentRepository.findById(tournamentId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND,
                        "Tournament not found"));

        if (!tournament.getOwnerId().equals(jwt.getSubject())) {
            throw new ForbiddenException("You are not the owner of this tournament");
        }

        return tournament;
    }

    public record OptimizationStatus(
            Long tournamentId,
            String status,
            boolean isRunning,
            boolean hasResult
    ) {}
}
