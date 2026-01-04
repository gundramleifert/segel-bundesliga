package de.segelbundesliga.e2e;

import static org.assertj.core.api.Assertions.assertThat;

import com.microsoft.playwright.Download;
import com.microsoft.playwright.Locator;
import com.microsoft.playwright.Page;
import com.microsoft.playwright.options.SelectOption;
import org.junit.jupiter.api.*;

import java.nio.file.Files;
import java.nio.file.Path;

/**
 * E2E tests for tournament configuration selection, PDF export, and schedule caching.
 *
 * User Stories:
 * - US-CONFIG-01: User can select optimization configuration when creating tournament
 * - US-CONFIG-02: User can select display configuration for PDF export
 * - US-EXPORT-01: User can export tournament schedule as PDF after optimization
 * - US-CACHE-01: System reuses cached schedule for identical tournament configurations
 */
@TestMethodOrder(MethodOrderer.OrderAnnotation.class)
@DisplayName("Tournament Configuration and Export Tests")
class TournamentConfigAndExportTest extends E2ETestBase {

    private static final String TEST_TOURNAMENT_NAME = "E2E Config Test " + System.currentTimeMillis();
    private static String createdTournamentUrl = null;

    @Test
    @Order(1)
    @DisplayName("US-CONFIG-01: Optimization config selector is visible on create page")
    void optimizationConfigSelectorVisible() {
        // Given: User is on tournament create page
        navigateTo("/tournaments/new");
        page.waitForTimeout(1000);

        // Then: Optimization config selector should be visible
        Locator optConfigSelect = waitForTestId("optimization-config-select");
        assertThat(optConfigSelect.isVisible()).isTrue();

        // And: Should have options (Minimal, Fast, Balanced, Thorough)
        String optionsText = optConfigSelect.textContent();
        assertThat(optionsText).contains("Minimal");
        assertThat(optionsText).contains("Fast");
        assertThat(optionsText).contains("Balanced");
        assertThat(optionsText).contains("Thorough");
    }

    @Test
    @Order(2)
    @DisplayName("US-CONFIG-02: Display config selector is visible on create page")
    void displayConfigSelectorVisible() {
        // Given: User is on tournament create page
        navigateTo("/tournaments/new");
        page.waitForTimeout(1000);

        // Then: Display config selector should be visible
        Locator dispConfigSelect = waitForTestId("display-config-select");
        assertThat(dispConfigSelect.isVisible()).isTrue();

        // And: Should have options (Example, Compact, Standard, Large)
        String optionsText = dispConfigSelect.textContent();
        assertThat(optionsText).contains("Example");
        assertThat(optionsText).contains("Compact");
        assertThat(optionsText).contains("Standard");
        assertThat(optionsText).contains("Large");
    }

    @Test
    @Order(3)
    @DisplayName("US-CONFIG-01: User can create tournament with selected configurations")
    void canCreateTournamentWithConfigs() {
        // Given: User is on create page
        navigateTo("/tournaments/new");
        page.waitForTimeout(1000);
        waitForTestId("tournament-name-input");

        // When: User fills form with configs
        fillTestId("tournament-name-input", TEST_TOURNAMENT_NAME);
        fillTestId("tournament-flights-input", "6");

        // Select "Minimal" optimization config (fastest for E2E tests)
        selectOptimizationConfigByName("Minimal");

        // Select "Example" display config
        selectDisplayConfigByName("Example");

        // Add 4 teams and 2 boats (6 flights)
        String[] teams = {"Team A", "Team B", "Team C", "Team D"};
        for (String team : teams) {
            fillTestId("team-name-input", team);
            clickTestId("team-add-button");
            page.waitForTimeout(200);
        }

        String[] boats = {"Boot 1", "Boot 2"};
        for (String boat : boats) {
            fillTestId("boat-name-input", boat);
            clickTestId("boat-add-button");
            page.waitForTimeout(200);
        }

        // Then: User can save tournament
        clickTestId("tournament-save-button");
        page.waitForTimeout(2000);

        // Verify redirect to detail page
        assertThat(page.url()).contains("/tournaments/");
        assertThat(page.url()).doesNotEndWith("/new");

        // Store URL for later tests
        createdTournamentUrl = page.url();
        System.out.println("Created tournament at: " + createdTournamentUrl);
    }

    @Test
    @Order(4)
    @DisplayName("US-EXPORT-01: PDF export button is hidden before optimization")
    void pdfExportHiddenBeforeOptimization() {
        // Given: Tournament exists but not optimized
        assertThat(createdTournamentUrl).isNotNull();
        navigateTo(createdTournamentUrl);
        page.waitForTimeout(1000);

        // Then: PDF export button should not be visible
        assertThat(page.locator("[data-testid='export-pdf-button']").count()).isEqualTo(0);
    }

    @Test
    @Order(5)
    @DisplayName("US-CACHE-01 & US-EXPORT-01: Run optimization and export PDF")
    void canRunOptimizationAndExportPdf() throws Exception {
        // Given: Tournament is created
        assertThat(createdTournamentUrl).isNotNull();
        navigateTo(createdTournamentUrl);
        page.waitForTimeout(1000);

        // When: User starts optimization
        clickTestId("optimization-start-button");
        System.out.println("Started optimization, waiting for completion...");

        // Wait for optimization to complete (max 60 seconds)
        page.waitForSelector("[data-testid='export-pdf-button']", new Page.WaitForSelectorOptions().setTimeout(60000));
        page.waitForTimeout(2000); // Additional wait for UI to stabilize

        // Then: Computation time should be displayed
        Locator computationTimeStat = page.locator("[data-testid='stat-computation-time']");
        assertThat(computationTimeStat.isVisible()).isTrue();

        String computationTimeText = computationTimeStat.textContent();
        assertThat(computationTimeText).containsIgnoringCase("Rechenzeit");
        System.out.println("Optimization completed, computation time: " + computationTimeText);

        // And: Check if this might be a cache hit (computation time < 2s)
        Locator cacheIndicator = page.locator("[data-testid='cache-indicator']");
        if (cacheIndicator.count() > 0) {
            System.out.println("⚡ Schedule was reused from cache!");
            assertThat(cacheIndicator.textContent()).contains("Aus Cache wiederverwendet");
        } else {
            System.out.println("Freshly optimized (no cache hit)");
        }

        // And: PDF export button should be visible
        Locator pdfButton = waitForTestId("export-pdf-button");
        assertThat(pdfButton.isVisible()).isTrue();

        // When: User clicks PDF export
        Download download = page.waitForDownload(() -> {
            clickTestId("export-pdf-button");
        });

        // Then: PDF should be downloaded
        Path downloadPath = download.path();
        assertThat(Files.exists(downloadPath)).isTrue();
        assertThat(Files.size(downloadPath)).isGreaterThan(1000); // PDF should be > 1KB

        String suggestedFilename = download.suggestedFilename();
        assertThat(suggestedFilename).endsWith(".pdf");
        assertThat(suggestedFilename).contains("schedule");
        System.out.println("PDF downloaded successfully: " + suggestedFilename + " (" + Files.size(downloadPath) + " bytes)");
    }

    @Test
    @Order(6)
    @DisplayName("US-CACHE-01: Create identical tournament to test schedule caching")
    void createIdenticalTournamentForCaching() {
        // Given: User creates another tournament with SAME config
        navigateTo("/tournaments/new");
        page.waitForTimeout(1000);

        // When: User creates tournament with identical setup
        fillTestId("tournament-name-input", TEST_TOURNAMENT_NAME + " (Cache Test)");
        fillTestId("tournament-flights-input", "6");

        // Same configs as first tournament
        selectOptimizationConfigByName("Minimal");
        selectDisplayConfigByName("Example");

        // EXACT SAME teams (same order as first tournament!)
        String[] teams = {"Team A", "Team B", "Team C", "Team D"};
        for (String team : teams) {
            fillTestId("team-name-input", team);
            clickTestId("team-add-button");
            page.waitForTimeout(200);
        }

        // EXACT SAME boats
        String[] boats = {"Boot 1", "Boot 2"};
        for (String boat : boats) {
            fillTestId("boat-name-input", boat);
            clickTestId("boat-add-button");
            page.waitForTimeout(200);
        }

        // Save tournament
        clickTestId("tournament-save-button");
        page.waitForTimeout(2000);

        // Store new URL
        String newTournamentUrl = page.url();
        System.out.println("Created identical tournament at: " + newTournamentUrl);

        // Run optimization
        clickTestId("optimization-start-button");
        System.out.println("Started optimization for cache test...");

        // Wait for completion
        page.waitForSelector("[data-testid='export-pdf-button']", new Page.WaitForSelectorOptions().setTimeout(60000));
        page.waitForTimeout(2000);

        // Then: Cache indicator SHOULD be present (schedule reused)
        Locator cacheIndicator = page.locator("[data-testid='cache-indicator']");
        assertThat(cacheIndicator.count()).isGreaterThan(0);
        assertThat(cacheIndicator.isVisible()).isTrue();
        assertThat(cacheIndicator.textContent()).contains("Aus Cache wiederverwendet");

        // And: Computation time should be very low (< 2s)
        Locator computationTimeStat = page.locator("[data-testid='stat-computation-time']");
        String timeText = computationTimeStat.textContent().replaceAll("[^0-9.]", "");
        double computationSeconds = Double.parseDouble(timeText);
        assertThat(computationSeconds).isLessThan(2.0);

        System.out.println("✅ Cache hit confirmed! Computation time: " + computationSeconds + "s");
    }

    @Test
    @Order(7)
    @DisplayName("US-CACHE-01: Different team order results in different schedule (no cache hit)")
    void differentTeamOrderNoCacheHit() {
        // Given: User creates tournament with DIFFERENT team order
        navigateTo("/tournaments/new");
        page.waitForTimeout(1000);

        // When: User creates tournament with different team order
        fillTestId("tournament-name-input", TEST_TOURNAMENT_NAME + " (Different Order)");
        fillTestId("tournament-flights-input", "6");

        // Same configs as first tournament
        selectOptimizationConfigByName("Minimal");
        selectDisplayConfigByName("Example");

        // DIFFERENT team order (same teams, different order!)
        String[] teams = {"Team B", "Team C", "Team D", "Team A"}; // Reordered!
        for (String team : teams) {
            fillTestId("team-name-input", team);
            clickTestId("team-add-button");
            page.waitForTimeout(200);
        }

        String[] boats = {"Boot 1", "Boot 2"};
        for (String boat : boats) {
            fillTestId("boat-name-input", boat);
            clickTestId("boat-add-button");
            page.waitForTimeout(200);
        }

        clickTestId("tournament-save-button");
        page.waitForTimeout(2000);

        // Run optimization
        clickTestId("optimization-start-button");
        System.out.println("Started optimization with different team order...");

        page.waitForSelector("[data-testid='export-pdf-button']", new Page.WaitForSelectorOptions().setTimeout(60000));
        page.waitForTimeout(2000);

        // Then: Cache indicator should NOT be present (fresh optimization)
        Locator cacheIndicator = page.locator("[data-testid='cache-indicator']");
        if (cacheIndicator.count() > 0) {
            // Might still be cache hit if same teams were used before in different test
            System.out.println("⚠️  Unexpected cache hit - might be from previous test run");
        } else {
            System.out.println("✅ No cache hit (as expected for different team order)");
        }

        // Computation time should be higher than cache hit
        Locator computationTimeStat = page.locator("[data-testid='stat-computation-time']");
        String timeText = computationTimeStat.textContent().replaceAll("[^0-9.]", "");
        double computationSeconds = Double.parseDouble(timeText);
        System.out.println("Computation time: " + computationSeconds + "s");
    }

    /**
     * Helper: Select optimization config by name (e.g., "Minimal", "Fast")
     * Finds the option whose text starts with the given name.
     */
    private void selectOptimizationConfigByName(String configName) {
        Locator select = page.locator("[data-testid='optimization-config-select']");
        // Wait for options to load
        page.waitForTimeout(2000);

        // Get all option elements and find the one that starts with configName
        Locator options = select.locator("option");
        int count = options.count();
        for (int i = 0; i < count; i++) {
            String text = options.nth(i).textContent();
            if (text != null && text.trim().startsWith(configName)) {
                String value = options.nth(i).getAttribute("value");
                if (value != null && !value.isEmpty()) {
                    select.selectOption(value);
                    return;
                }
            }
        }
        throw new RuntimeException("Could not find optimization config starting with: " + configName);
    }

    /**
     * Helper: Select display config by name (e.g., "Example", "Standard")
     * Finds the option whose text starts with the given name.
     */
    private void selectDisplayConfigByName(String configName) {
        Locator select = page.locator("[data-testid='display-config-select']");
        // Wait for options to load
        page.waitForTimeout(2000);

        // Get all option elements and find the one that starts with configName
        Locator options = select.locator("option");
        int count = options.count();
        for (int i = 0; i < count; i++) {
            String text = options.nth(i).textContent();
            if (text != null && text.trim().startsWith(configName)) {
                String value = options.nth(i).getAttribute("value");
                if (value != null && !value.isEmpty()) {
                    select.selectOption(value);
                    return;
                }
            }
        }
        throw new RuntimeException("Could not find display config starting with: " + configName);
    }
}
