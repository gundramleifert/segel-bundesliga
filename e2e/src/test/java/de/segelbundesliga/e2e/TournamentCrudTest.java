package de.segelbundesliga.e2e;

import static org.assertj.core.api.Assertions.assertThat;

import com.microsoft.playwright.Locator;
import com.microsoft.playwright.Page;
import org.junit.jupiter.api.*;

/**
 * E2E tests for tournament CRUD operations.
 *
 * User Stories:
 * - US-TOUR-01: User can create tournament with teams and boats
 * - US-TOUR-02: User can view tournament details
 * - US-TOUR-03: User can edit tournament configuration
 * - US-TOUR-04: User can delete tournament
 */
@TestMethodOrder(MethodOrderer.OrderAnnotation.class)
@DisplayName("Tournament CRUD Tests")
class TournamentCrudTest extends E2ETestBase {

    private static final String TEST_TOURNAMENT_NAME = "E2E Test Turnier " + System.currentTimeMillis();
    private static String createdTournamentUrl = null;

    @Test
    @Order(1)
    @DisplayName("US-TOUR-01: User can navigate to create tournament page")
    void canNavigateToCreateTournament() {
        // Given: User is logged in
        navigateTo("/tournaments");

        // When: User clicks create button
        clickTestId("tournament-create-button");

        // Then: User is on create page
        assertThat(page.url()).endsWith("/tournaments/new");
        assertThat(page.locator("h2").textContent()).contains("Turnier");
    }

    @Test
    @Order(2)
    @DisplayName("US-TOUR-01: Form validation requires tournament name")
    void formValidationRequiresName() {
        // Given: User is on create page
        navigateTo("/tournaments/new");

        // Then: Save button should be disabled without name
        Locator saveButton = page.getByTestId("tournament-save-button");
        assertThat(saveButton.isDisabled()).isTrue();
    }

    @Test
    @Order(3)
    @DisplayName("US-TOUR-01: User can create tournament with teams and boats")
    void canCreateTournamentWithTeamsAndBoats() {
        // Given: User is on create page
        navigateTo("/tournaments/new");

        // When: User fills form
        fillTestId("tournament-name-input", TEST_TOURNAMENT_NAME);
        page.locator("textarea").fill("Test Beschreibung für E2E");
        fillTestId("tournament-flights-input", "4");

        // Add teams
        String[] teams = {"Team Alpha", "Team Beta", "Team Gamma", "Team Delta"};
        for (String team : teams) {
            fillTestId("team-name-input", team);
            clickTestId("team-add-button");
        }

        // Verify teams were added
        for (int i = 0; i < teams.length; i++) {
            assertThat(page.locator("text=" + (i + 1) + ". " + teams[i]).isVisible()).isTrue();
        }

        // Add boats
        String[] boats = {"Boot Rot", "Boot Blau", "Boot Grün", "Boot Gelb"};
        for (String boat : boats) {
            fillTestId("boat-name-input", boat);
            clickTestId("boat-add-button");
        }

        // Verify boats were added
        for (String boat : boats) {
            assertThat(page.locator("text=" + boat).isVisible()).isTrue();
        }

        // When: User submits form
        clickTestId("tournament-save-button");

        // Then: Redirected to detail page
        page.waitForURL(url -> url.matches(".*/tournaments/\\d+"),
                new Page.WaitForURLOptions().setTimeout(15000));

        createdTournamentUrl = page.url();

        // Verify tournament was created
        assertThat(getTextByTestId("tournament-name")).isEqualTo(TEST_TOURNAMENT_NAME);
    }

    @Test
    @Order(4)
    @DisplayName("US-TOUR-02: Created tournament can be accessed by URL")
    void createdTournamentCanBeAccessedByUrl() {
        // Given: Tournament was created
        assertThat(createdTournamentUrl).isNotNull();

        // When: User navigates directly to tournament
        page.navigate(createdTournamentUrl);
        page.waitForLoadState();

        // Then: Tournament details are visible
        waitForTestId("tournament-name");
        assertThat(getTextByTestId("tournament-name")).contains("E2E Test Turnier");
    }

    @Test
    @Order(5)
    @DisplayName("US-TOUR-02: User can view tournament details")
    void canViewTournamentDetails() {
        // Given: Tournament exists
        assertThat(createdTournamentUrl).isNotNull();
        page.navigate(createdTournamentUrl);
        page.waitForLoadState();
        waitForTestId("tournament-name");

        // Then: All sections are visible
        assertThat(page.locator("h3:has-text('Teams')").isVisible()).isTrue();
        assertThat(page.locator("text=Team Alpha").isVisible()).isTrue();

        assertThat(page.locator("h3:has-text('Boote')").isVisible()).isTrue();
        assertThat(page.locator("text=Boot Rot").isVisible()).isTrue();

        assertThat(page.locator("h3:has-text('Optimierung')").isVisible()).isTrue();
    }

    @Test
    @Order(6)
    @DisplayName("US-TOUR-02: Tournament shows correct configuration")
    void tournamentShowsCorrectConfiguration() {
        // Given: Tournament exists
        assertThat(createdTournamentUrl).isNotNull();
        page.navigate(createdTournamentUrl);
        page.waitForLoadState();
        waitForTestId("tournament-name");

        // Then: Configuration values are shown
        assertThat(page.locator("text=Flights:").isVisible()).isTrue();
        assertThat(page.locator("text=Teams:").isVisible()).isTrue();
        assertThat(page.locator("text=Boote:").isVisible()).isTrue();
    }

    @Test
    @Order(7)
    @DisplayName("US-TOUR-03: User can remove teams before saving")
    void canRemoveTeamsBeforeSaving() {
        // Given: User is on create page
        navigateTo("/tournaments/new");

        // When: User adds a team
        fillTestId("team-name-input", "Temp Team");
        clickTestId("team-add-button");

        // Verify team was added
        assertThat(page.locator("text=1. Temp Team").isVisible()).isTrue();

        // When: User removes the team
        page.locator("text=1. Temp Team").locator("..").locator("button").click();

        // Then: Team is removed
        assertThat(page.locator("text=1. Temp Team").isVisible()).isFalse();
    }

    @Test
    @Order(8)
    @DisplayName("US-TOUR-03: User can remove boats before saving")
    void canRemoveBoatsBeforeSaving() {
        // Given: User is on create page
        navigateTo("/tournaments/new");
        page.waitForLoadState();

        // When: User adds a boat
        fillTestId("boat-name-input", "Temp Boot XYZ");
        clickTestId("boat-add-button");
        page.waitForTimeout(500);

        // Verify boat was added
        assertThat(page.locator("text=Temp Boot XYZ").isVisible()).isTrue();

        // When: User removes the boat
        page.locator("button:has-text('✕')").last().click();
        page.waitForTimeout(500);

        // Then: Boat is removed
        assertThat(page.locator("text=Temp Boot XYZ").count()).isEqualTo(0);
    }

    @Test
    @Order(99)
    @DisplayName("US-TOUR-04: User can delete tournament")
    void canDeleteTournament() {
        // Given: Tournament exists
        assertThat(createdTournamentUrl).isNotNull();
        page.navigate(createdTournamentUrl);
        page.waitForLoadState();
        waitForTestId("tournament-name");

        // Setup: Accept confirmation dialog
        acceptNextDialog();

        // When: User clicks delete
        clickTestId("tournament-delete-button");

        // Then: Redirected to list
        page.waitForURL("**/tournaments",
                new Page.WaitForURLOptions().setTimeout(15000));
        page.waitForLoadState();

        // Cleanup
        createdTournamentUrl = null;
    }
}
