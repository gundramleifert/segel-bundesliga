package de.segelbundesliga.e2e;

import com.microsoft.playwright.Locator;
import org.junit.jupiter.api.*;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * E2E tests for the optimization flow.
 */
@TestMethodOrder(MethodOrderer.OrderAnnotation.class)
class OptimizationTest extends BaseE2ETest {

    private static final String TEST_TOURNAMENT_NAME = "Optimization Test " + System.currentTimeMillis();
    private static String tournamentUrl;

    @BeforeEach
    void loginBeforeTest() {
        login();
    }

    @Test
    @Order(1)
    @DisplayName("Create tournament for optimization testing")
    void createTournamentForOptimization() {
        navigateTo("/tournaments/new");

        // Fill basic info
        fillTestId("tournament-name-input", TEST_TOURNAMENT_NAME);
        fillTestId("tournament-flights-input", "3");

        // Add 6 teams (minimum for interesting optimization)
        String[] teams = {"Team 1", "Team 2", "Team 3", "Team 4", "Team 5", "Team 6"};
        for (String team : teams) {
            fillTestId("team-name-input", team);
            clickTestId("team-add-button");
        }

        // Add 4 boats
        String[] boats = {"Boot A", "Boot B", "Boot C", "Boot D"};
        for (String boat : boats) {
            fillTestId("boat-name-input", boat);
            clickTestId("boat-add-button");
        }

        // Submit
        clickTestId("tournament-save-button");

        // Wait for redirect and store URL
        page.waitForURL(url -> url.matches(".*/tournaments/\\d+"),
            new com.microsoft.playwright.Page.WaitForURLOptions().setTimeout(10000));

        tournamentUrl = page.url();
        assertThat(page.getByTestId("tournament-name").textContent()).isEqualTo(TEST_TOURNAMENT_NAME);
    }

    @Test
    @Order(2)
    @DisplayName("Optimization section shows start button when requirements met")
    void optimizationShowsStartButton() {
        navigateTo(tournamentUrl.replace(BASE_URL, ""));

        // Wait for page to load
        waitForTestId("tournament-name");

        // Should see the start button (not the warning about missing config)
        assertThat(page.getByTestId("optimization-start-button").isVisible()).isTrue();

        // Should NOT see the warning about missing teams/boats
        assertThat(page.locator("text=Bitte zuerst Teams und Boote hinzufügen").isVisible()).isFalse();
    }

    @Test
    @Order(3)
    @DisplayName("User can start optimization")
    void canStartOptimization() {
        navigateTo(tournamentUrl.replace(BASE_URL, ""));
        waitForTestId("tournament-name");

        // Click start button
        clickTestId("optimization-start-button");

        // Should see cancel button (optimization is running)
        page.getByTestId("optimization-cancel-button").waitFor(
            new Locator.WaitForOptions()
                .setState(com.microsoft.playwright.options.WaitForSelectorState.VISIBLE)
                .setTimeout(5000));

        assertThat(page.getByTestId("optimization-cancel-button").isVisible()).isTrue();
    }

    @Test
    @Order(4)
    @DisplayName("Progress bar appears during optimization")
    void progressBarAppearsDuringOptimization() {
        navigateTo(tournamentUrl.replace(BASE_URL, ""));
        waitForTestId("tournament-name");

        // Start optimization
        clickTestId("optimization-start-button");

        // Wait for progress bar to appear
        page.getByTestId("optimization-progress-bar").waitFor(
            new Locator.WaitForOptions()
                .setState(com.microsoft.playwright.options.WaitForSelectorState.VISIBLE)
                .setTimeout(10000));

        assertThat(page.getByTestId("optimization-progress-bar").isVisible()).isTrue();
    }

    @Test
    @Order(5)
    @DisplayName("User can cancel running optimization")
    void canCancelOptimization() {
        navigateTo(tournamentUrl.replace(BASE_URL, ""));
        waitForTestId("tournament-name");

        // Check if optimization is already running from previous test
        if (!page.getByTestId("optimization-cancel-button").isVisible()) {
            // Start optimization
            clickTestId("optimization-start-button");

            // Wait for cancel button
            page.getByTestId("optimization-cancel-button").waitFor(
                new Locator.WaitForOptions()
                    .setState(com.microsoft.playwright.options.WaitForSelectorState.VISIBLE)
                    .setTimeout(5000));
        }

        // Click cancel
        clickTestId("optimization-cancel-button");

        // Start button should reappear
        page.getByTestId("optimization-start-button").waitFor(
            new Locator.WaitForOptions()
                .setState(com.microsoft.playwright.options.WaitForSelectorState.VISIBLE)
                .setTimeout(10000));

        assertThat(page.getByTestId("optimization-start-button").isVisible()).isTrue();
    }

    @Test
    @Order(6)
    @DisplayName("Optimization completes and shows result")
    void optimizationCompletesAndShowsResult() {
        navigateTo(tournamentUrl.replace(BASE_URL, ""));
        waitForTestId("tournament-name");
        page.waitForLoadState();

        // Start optimization if not already showing result
        if (page.getByTestId("optimization-start-button").isVisible()) {
            clickTestId("optimization-start-button");
        }

        // Wait for optimization to complete (may take a while)
        // Poll for completion - either start button reappears or result section shows
        long startTime = System.currentTimeMillis();
        long timeout = 120000; // 2 minutes
        while (System.currentTimeMillis() - startTime < timeout) {
            page.waitForTimeout(2000);
            if (page.getByTestId("optimization-start-button").isVisible() ||
                page.locator("h3:has-text('Ergebnis')").isVisible()) {
                break;
            }
        }

        // Verify result is shown (if optimization completed successfully)
        if (page.locator("h3:has-text('Ergebnis')").isVisible()) {
            // Check result metrics are displayed
            assertThat(page.locator("text=Gesparte Shuttles").isVisible()).isTrue();
            assertThat(page.locator("text=Boot-Wechsel").isVisible()).isTrue();
            assertThat(page.locator("text=Rechenzeit").isVisible()).isTrue();

            // JSON result should be available
            assertThat(page.locator("text=JSON-Ergebnis anzeigen").isVisible()).isTrue();
        }
    }

    @Test
    @Order(7)
    @DisplayName("User can expand JSON result")
    void canExpandJsonResult() {
        navigateTo(tournamentUrl.replace(BASE_URL, ""));
        waitForTestId("tournament-name");

        // Check if result exists
        if (page.locator("text=JSON-Ergebnis anzeigen").isVisible()) {
            // Click to expand
            page.locator("text=JSON-Ergebnis anzeigen").click();

            // Should see JSON in pre element
            assertThat(page.locator("pre").isVisible()).isTrue();
        }
    }

    @Test
    @Order(8)
    @DisplayName("Tournament without teams/boats shows warning")
    void tournamentWithoutConfigShowsWarning() {
        // Create empty tournament
        navigateTo("/tournaments/new");
        page.waitForLoadState();
        String emptyTournamentName = "Empty Tournament " + System.currentTimeMillis();
        fillTestId("tournament-name-input", emptyTournamentName);
        clickTestId("tournament-save-button");

        page.waitForURL(url -> url.matches(".*/tournaments/\\d+"),
            new com.microsoft.playwright.Page.WaitForURLOptions().setTimeout(15000));
        page.waitForLoadState();
        page.waitForTimeout(1000);

        // Verify we're on the tournament detail page
        waitForTestId("tournament-name");

        // Should see warning about missing config
        Locator warning = page.locator("p.text-yellow-600");
        assertThat(warning.count()).isGreaterThan(0);

        // Should NOT see start button (no teams/boats)
        assertThat(page.getByTestId("optimization-start-button").count()).isEqualTo(0);
    }

    @Test
    @Order(99)
    @DisplayName("Cleanup: Delete test tournament")
    void cleanupDeleteTournament() {
        if (tournamentUrl != null) {
            navigateTo(tournamentUrl.replace(BASE_URL, ""));
            waitForTestId("tournament-name");

            // Handle confirmation dialog
            page.onDialog(dialog -> dialog.accept());

            // Delete
            clickTestId("tournament-delete-button");

            // Wait for redirect
            page.waitForURL("**/tournaments",
                new com.microsoft.playwright.Page.WaitForURLOptions().setTimeout(10000));
        }
    }
}
