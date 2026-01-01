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
        page.waitForTimeout(2000); // Wait for auth state and page load

        // When: User clicks create button
        waitForTestId("tournament-create-button");
        clickTestId("tournament-create-button");
        page.waitForLoadState();

        // Then: User is on create page
        assertThat(page.url()).endsWith("/tournaments/new");
    }

    @Test
    @Order(2)
    @DisplayName("US-TOUR-01: Form validation requires tournament name")
    void formValidationRequiresName() {
        // Given: User is on create page
        navigateTo("/tournaments/new");
        page.waitForTimeout(1000);

        // Then: Save button should be disabled without name
        Locator saveButton = waitForTestId("tournament-save-button");
        assertThat(saveButton.isDisabled()).isTrue();
    }

    @Test
    @Order(3)
    @DisplayName("US-TOUR-01: User can create tournament with teams and boats")
    void canCreateTournamentWithTeamsAndBoats() {
        // Given: User is on create page
        navigateTo("/tournaments/new");
        page.waitForTimeout(1000);
        waitForTestId("tournament-name-input");

        // When: User fills form
        fillTestId("tournament-name-input", TEST_TOURNAMENT_NAME);
        page.locator("textarea").fill("Test Beschreibung für E2E");
        fillTestId("tournament-flights-input", "4");

        // Add teams
        String[] teams = {"Team Alpha", "Team Beta", "Team Gamma", "Team Delta"};
        for (String team : teams) {
            fillTestId("team-name-input", team);
            clickTestId("team-add-button");
            page.waitForTimeout(300);
        }

        // Add boats
        String[] boats = {"Boot Rot", "Boot Blau", "Boot Grün", "Boot Gelb"};
        for (String boat : boats) {
            fillTestId("boat-name-input", boat);
            clickTestId("boat-add-button");
            page.waitForTimeout(300);
        }

        // When: User submits form
        clickTestId("tournament-save-button");

        // Then: Redirected to detail page
        page.waitForURL(url -> url.matches(".*/tournaments/\\d+"),
                new Page.WaitForURLOptions().setTimeout(15000));

        createdTournamentUrl = page.url();

        // Verify tournament was created
        waitForTestId("tournament-name");
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
        page.waitForTimeout(2000);

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
        page.waitForTimeout(2000);
        waitForTestId("tournament-name");

        // Then: Teams section is visible
        page.locator("text=Teams").first().waitFor();
        assertThat(page.locator("text=Team Alpha").isVisible()).isTrue();

        // Then: Boats section is visible
        assertThat(page.locator("text=Boote").first().isVisible()).isTrue();
        assertThat(page.locator("text=Boot Rot").isVisible()).isTrue();

        // Then: Optimization section is visible
        assertThat(page.locator("text=Optimierung").first().isVisible()).isTrue();
    }

    @Test
    @Order(6)
    @DisplayName("US-TOUR-02: Tournament shows correct configuration")
    void tournamentShowsCorrectConfiguration() {
        // Given: Tournament exists
        assertThat(createdTournamentUrl).isNotNull();
        page.navigate(createdTournamentUrl);
        page.waitForLoadState();
        page.waitForTimeout(2000);
        waitForTestId("tournament-name");

        // Then: Configuration values are shown (Flights, Teams count, Boats count)
        assertThat(page.locator("text=Flights").isVisible()).isTrue();
        assertThat(page.locator("text=Teams").first().isVisible()).isTrue();
        assertThat(page.locator("text=Boote").first().isVisible()).isTrue();
    }

    @Test
    @Order(7)
    @DisplayName("US-TOUR-03: User can remove teams before saving")
    void canRemoveTeamsBeforeSaving() {
        // Given: User is on create page
        navigateTo("/tournaments/new");
        page.waitForTimeout(1000);
        waitForTestId("team-name-input");

        // When: User adds a team
        fillTestId("team-name-input", "Temp Team");
        clickTestId("team-add-button");
        page.waitForTimeout(500);

        // Verify team was added - look for "Temp Team" in the teams list
        assertThat(page.locator("text=Temp Team").isVisible()).isTrue();

        // When: User removes the team (click the X button next to it)
        page.locator("text=Temp Team").locator("xpath=..").locator("button").click();
        page.waitForTimeout(500);

        // Then: Team is removed
        assertThat(page.locator("text=Temp Team").count()).isEqualTo(0);
    }

    @Test
    @Order(8)
    @DisplayName("US-TOUR-03: User can remove boats before saving")
    void canRemoveBoatsBeforeSaving() {
        // Given: User is on create page
        navigateTo("/tournaments/new");
        page.waitForTimeout(1000);
        waitForTestId("boat-name-input");

        // When: User adds a boat
        fillTestId("boat-name-input", "Temp Boot XYZ");
        clickTestId("boat-add-button");
        page.waitForTimeout(500);

        // Verify boat was added
        assertThat(page.locator("text=Temp Boot XYZ").isVisible()).isTrue();

        // When: User removes the boat (click the delete button in the boat row)
        // Structure: div > div > span(text) + button is sibling of parent div
        page.locator("text=Temp Boot XYZ").locator("xpath=../..").locator("button").click();
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
        page.waitForTimeout(2000);
        waitForTestId("tournament-name");

        // When: User clicks delete button (opens dialog)
        clickTestId("tournament-delete-button");
        page.waitForTimeout(500);

        // Then: Click the confirm delete button in dialog
        page.getByRole(com.microsoft.playwright.options.AriaRole.BUTTON,
                new Page.GetByRoleOptions().setName("Endgültig löschen")).click();

        // Then: Redirected to list
        page.waitForURL("**/tournaments",
                new Page.WaitForURLOptions().setTimeout(15000));
        page.waitForLoadState();

        // Cleanup
        createdTournamentUrl = null;
    }
}
