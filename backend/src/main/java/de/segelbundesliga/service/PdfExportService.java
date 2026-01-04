package de.segelbundesliga.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import de.segelbundesliga.domain.DisplayConfig;
import de.segelbundesliga.domain.FontFamily;
import de.segelbundesliga.domain.PageOrientation;
import de.segelbundesliga.domain.Tournament;
import de.segelbundesliga.repository.TournamentRepository;
import gundramleifert.pairing_list.PdfCreator;
import gundramleifert.pairing_list.configs.BoatConfig;
import gundramleifert.pairing_list.configs.ScheduleConfig;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;

@Service
@RequiredArgsConstructor
@Slf4j
public class PdfExportService {

    private final TournamentRepository tournamentRepository;
    private final DisplayConfigService displayConfigService;
    private final ObjectMapper objectMapper;

    /**
     * Generate PDF from tournament schedule using PdfCreator from optimizer library
     */
    @Transactional(readOnly = true)
    public byte[] generatePdf(Long tournamentId) throws IOException {
        Tournament tournament = tournamentRepository.findById(tournamentId)
                .orElseThrow(() -> new IllegalArgumentException("Tournament not found: " + tournamentId));

        if (tournament.getSchedule() == null) {
            throw new IllegalStateException("Tournament has no schedule. Run optimization first.");
        }

        // Deserialize schedule from JSON
        gundramleifert.pairing_list.types.Schedule schedule =
            objectMapper.readValue(tournament.getSchedule().getScheduleJson(),
                           gundramleifert.pairing_list.types.Schedule.class);

        // Get display config (or use default)
        DisplayConfig displayConfig = displayConfigService.getOrDefault(tournament.getDisplayConfig());

        // Convert to optimizer library's DisplayConfig
        gundramleifert.pairing_list.configs.DisplayConfig pdfConfig =
            convertToOptimizerDisplayConfig(displayConfig, tournament.getName());

        // Build ScheduleConfig for PDF generation
        ScheduleConfig scheduleConfig = buildScheduleConfig(tournament);

        // Generate PDF using PdfCreator with temporary file
        File tempFile = File.createTempFile("tournament_schedule_", ".pdf");
        try {
            try (PdfCreator pdfCreator = new PdfCreator(pdfConfig, scheduleConfig, tempFile)) {
                pdfCreator.init(tournament.getName());
                pdfCreator.createSchedule(schedule, tournament.getName(), (byte) -1, null);
            }

            // Read file into byte array
            byte[] pdfBytes = Files.readAllBytes(tempFile.toPath());
            return pdfBytes;

        } finally {
            // Clean up temporary file
            if (tempFile.exists()) {
                tempFile.delete();
            }
        }
    }

    private gundramleifert.pairing_list.configs.DisplayConfig convertToOptimizerDisplayConfig(
            DisplayConfig displayConfig, String tournamentName) {

        gundramleifert.pairing_list.configs.DisplayConfig config =
            new gundramleifert.pairing_list.configs.DisplayConfig();

        config.title = tournamentName;
        config.fontsize = displayConfig.getFontSize();
        config.landscape = displayConfig.getOrientation() == PageOrientation.LANDSCAPE;
        config.font = mapFontFamily(displayConfig.getFontFamily());

        // Use library defaults for other fields
        // (already set by default values in DisplayConfig class)

        return config;
    }

    private String mapFontFamily(FontFamily fontFamily) {
        switch (fontFamily) {
            case HELVETICA:
                return com.itextpdf.io.font.constants.StandardFonts.HELVETICA;
            case ARIAL:
                // Arial is not a standard PDF font, use Helvetica as fallback
                return com.itextpdf.io.font.constants.StandardFonts.HELVETICA;
            case TIMES_NEW_ROMAN:
                return com.itextpdf.io.font.constants.StandardFonts.TIMES_ROMAN;
            default:
                return com.itextpdf.io.font.constants.StandardFonts.HELVETICA;
        }
    }

    private ScheduleConfig buildScheduleConfig(Tournament tournament) {
        ScheduleConfig config = new ScheduleConfig();

        config.flights = tournament.getFlights();

        // Teams
        config.teams = tournament.getTeams().stream()
                .sorted((a, b) -> Integer.compare(a.getSortOrder(), b.getSortOrder()))
                .map(de.segelbundesliga.domain.Team::getName)
                .toArray(String[]::new);

        // Boats
        config.boats = tournament.getBoats().stream()
                .sorted((a, b) -> Integer.compare(a.getSortOrder(), b.getSortOrder()))
                .map(b -> {
                    BoatConfig bc = createBoatConfig();
                    bc.name = b.getName();
                    bc.color = b.getColor();
                    return bc;
                })
                .toArray(BoatConfig[]::new);

        config.init();
        return config;
    }

    private BoatConfig createBoatConfig() {
        try {
            // BoatConfig has private constructor, use reflection
            var constructor = BoatConfig.class.getDeclaredConstructor();
            constructor.setAccessible(true);
            return constructor.newInstance();
        } catch (Exception e) {
            throw new RuntimeException("Failed to create BoatConfig", e);
        }
    }
}
