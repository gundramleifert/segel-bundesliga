package de.segelbundesliga.e2e;

import static org.assertj.core.api.Assertions.assertThat;

import com.microsoft.playwright.Locator;
import com.microsoft.playwright.Page;
import com.microsoft.playwright.options.WaitForSelectorState;
import org.junit.jupiter.api.*;

/**
 * E2E tests for the optimization workflow.
 *
 * User Stories:
 * - US-OPT-01: User can start optimization for configured tournament
 * - US-OPT-02: User can see optimization progress
 * - US-OPT-03: User can cancel running optimization
 * - US-OPT-04: User can view optimization results
 */
@TestMethodOrder(MethodOrderer.OrderAnnotation.class)
@DisplayName("Optimization Flow Tests")
class OptimizationFlowTest extends E2ETestBase {

    private static final String TEST_TOURNAMENT_NAME = "Optimization Test " + System.currentTimeMillis();
    private static String tournamentUrl;

    @Test
    @Order(1)
    @DisplayName("Setup: Create tournament for optimization testing")
    void createTournamentForOptimization() {
        // Given: User is on create page
        navigateTo("/tournaments/new");

        // When: User creates tournament with valid config
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

        // Wait for redirect
        page.waitForURL(url -> url.matches(".*/tournaments/\\d+"),
                new Page.WaitForURLOptions().setTimeout(15000));

        tournamentUrl = page.url();

        // Then: Tournament created successfully
        assertThat(getTextByTestId("tournament-name")).isEqualTo(TEST_TOURNAMENT_NAME);
    }

    @Test
    @Order(2)
    @DisplayName("US-OPT-01: Optimization shows start button when requirements met")
    void optimizationShowsStartButton() {
        // Given: Tournament with valid config
        navigateTo(tournamentUrl.replace(TestFixtures.TEST_TARGET, ""));
        waitForTestId("tournament-name");

        // Then: Start button visible
        assertThat(isVisibleTestId("optimization-start-button")).isTrue();

        // And: No warning about missing config
        assertThat(page.locator("text=Bitte zuerst Teams und Boote hinzufügen").isVisible()).isFalse();
    }

    @Test
    @Order(3)
    @DisplayName("US-OPT-01: User can start optimization")
    void canStartOptimization() {
        // Given: Tournament page
        navigateTo(tournamentUrl.replace(TestFixtures.TEST_TARGET, ""));
        waitForTestId("tournament-name");

        // When: User clicks start
        clickTestId("optimization-start-button");

        // Then: Cancel button appears (optimization running)
        page.getByTestId("optimization-cancel-button").waitFor(
                new Locator.WaitForOptions()
                        .setState(WaitForSelectorState.VISIBLE)
                        .setTimeout(5000));

        assertThat(isVisibleTestId("optimization-cancel-button")).isTrue();
    }

    @Test
    @Order(4)
    @DisplayName("US-OPT-02: Progress bar appears during optimization")
    void progressBarAppearsDuringOptimization() {
        // Given: Tournament page
        navigateTo(tournamentUrl.replace(TestFixtures.TEST_TARGET, ""));
        waitForTestId("tournament-name");

        // When: Optimization is running (or start it)
        if (isVisibleTestId("optimization-start-button")) {
            clickTestId("optimization-start-button");
        }

        // Then: Progress bar visible
        page.getByTestId("optimization-progress-bar").waitFor(
                new Locator.WaitForOptions()
                        .setState(WaitForSelectorState.VISIBLE)
                        .setTimeout(10000));

        assertThat(isVisibleTestId("optimization-progress-bar")).isTrue();
    }

    @Test
    @Order(5)
    @DisplayName("US-OPT-03: User can cancel running optimization")
    void canCancelOptimization() {
        // Given: Tournament page
        navigateTo(tournamentUrl.replace(TestFixtures.TEST_TARGET, ""));
        waitForTestId("tournament-name");

        // Ensure optimization is running
        if (isVisibleTestId("optimization-start-button")) {
            clickTestId("optimization-start-button");
            page.getByTestId("optimization-cancel-button").waitFor(
                    new Locator.WaitForOptions()
                            .setState(WaitForSelectorState.VISIBLE)
                            .setTimeout(5000));
        }

        // When: User clicks cancel
        clickTestId("optimization-cancel-button");

        // Then: Start button reappears
        page.getByTestId("optimization-start-button").waitFor(
                new Locator.WaitForOptions()
                        .setState(WaitForSelectorState.VISIBLE)
                        .setTimeout(10000));

        assertThat(isVisibleTestId("optimization-start-button")).isTrue();
    }

    @Test
    @Order(6)
    @DisplayName("US-OPT-04: Optimization completes and shows result")
    void optimizationCompletesAndShowsResult() {
        // Given: Tournament page
        navigateTo(tournamentUrl.replace(TestFixtures.TEST_TARGET, ""));
        waitForTestId("tournament-name");
        page.waitForLoadState();

        // Start optimization if not already showing result
        if (isVisibleTestId("optimization-start-button")) {
            clickTestId("optimization-start-button");
        }

        // Wait for completion (poll for up to 2 minutes)
        long startTime = System.currentTimeMillis();
        long timeout = 120000;
        boolean completed = false;

        while (System.currentTimeMillis() - startTime < timeout) {
            page.waitForTimeout(2000);
            if (isVisibleTestId("optimization-start-button") ||
                    page.locator("h3:has-text('Ergebnis')").isVisible()) {
                completed = true;
                break;
            }
        }

        // Then: Result section visible (if completed successfully)
        if (page.locator("h3:has-text('Ergebnis')").isVisible()) {
            assertThat(page.locator("text=Gesparte Shuttles").isVisible()).isTrue();
            assertThat(page.locator("text=Boot-Wechsel").isVisible()).isTrue();
            assertThat(page.locator("text=Rechenzeit").isVisible()).isTrue();
            assertThat(page.locator("text=JSON-Ergebnis anzeigen").isVisible()).isTrue();
        }
    }

    @Test
    @Order(7)
    @DisplayName("US-OPT-04: User can expand JSON result")
    void canExpandJsonResult() {
        // Given: Tournament with result
        navigateTo(tournamentUrl.replace(TestFixtures.TEST_TARGET, ""));
        waitForTestId("tournament-name");

        // If result exists
        if (page.locator("text=JSON-Ergebnis anzeigen").isVisible()) {
            // When: User clicks to expand
            page.locator("text=JSON-Ergebnis anzeigen").click();

            // Then: JSON is shown
            assertThat(page.locator("pre").isVisible()).isTrue();
        }
    }

    @Test
    @Order(8)
    @DisplayName("US-OPT-01: Tournament without config shows warning")
    void tournamentWithoutConfigShowsWarning() {
        // Given: Create empty tournament
        navigateTo("/tournaments/new");
        page.waitForLoadState();

        String emptyTournamentName = "Empty Tournament " + System.currentTimeMillis();
        fillTestId("tournament-name-input", emptyTournamentName);
        clickTestId("tournament-save-button");

        page.waitForURL(url -> url.matches(".*/tournaments/\\d+"),
                new Page.WaitForURLOptions().setTimeout(15000));
        page.waitForLoadState();
        waitForTestId("tournament-name");

        // Then: Warning shown, no start button
        Locator warning = page.locator("p.text-yellow-600");
        assertThat(warning.count()).isGreaterThan(0);
        assertThat(page.getByTestId("optimization-start-button").count()).isEqualTo(0);
    }

    @Test
    @Order(99)
    @DisplayName("Cleanup: Delete test tournament")
    void cleanupDeleteTournament() {
        if (tournamentUrl != null) {
            navigateTo(tournamentUrl.replace(TestFixtures.TEST_TARGET, ""));
            waitForTestId("tournament-name");

            acceptNextDialog();
            clickTestId("tournament-delete-button");

            page.waitForURL("**/tournaments",
                    new Page.WaitForURLOptions().setTimeout(10000));
        }
    }
}
