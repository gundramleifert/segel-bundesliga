package de.segelbundesliga.e2e;

import com.microsoft.playwright.Locator;
import org.junit.jupiter.api.*;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * E2E tests for tournament CRUD operations.
 */
@TestMethodOrder(MethodOrderer.OrderAnnotation.class)
class TournamentTest extends BaseE2ETest {

    private static final String TEST_TOURNAMENT_NAME = "E2E Test Turnier " + System.currentTimeMillis();
    private static String createdTournamentUrl = null;

    @BeforeEach
    void loginBeforeTest() {
        login();
    }

    @Test
    @Order(1)
    @DisplayName("User can navigate to create tournament page")
    void canNavigateToCreateTournament() {
        navigateTo("/tournaments");

        // Click create button
        clickTestId("tournament-create-button");

        // Verify we're on the create page
        assertThat(page.url()).endsWith("/tournaments/new");
        assertThat(page.locator("h2 >> text=Neues Turnier erstellen").isVisible()).isTrue();
    }

    @Test
    @Order(2)
    @DisplayName("User can create a tournament with teams and boats")
    void canCreateTournamentWithTeamsAndBoats() {
        navigateTo("/tournaments/new");

        // Fill basic info
        fillTestId("tournament-name-input", TEST_TOURNAMENT_NAME);
        page.locator("textarea").fill("Test Beschreibung");
        page.locator("input[type='text']").nth(1).fill("Hamburg"); // Location
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

        // Submit form
        clickTestId("tournament-save-button");

        // Wait for redirect to detail page
        page.waitForURL(url -> url.matches(".*/tournaments/\\d+"),
            new com.microsoft.playwright.Page.WaitForURLOptions().setTimeout(10000));

        // Store the URL for subsequent tests
        createdTournamentUrl = page.url();

        // Verify tournament was created
        assertThat(page.getByTestId("tournament-name").textContent()).isEqualTo(TEST_TOURNAMENT_NAME);
    }

    @Test
    @Order(3)
    @DisplayName("Created tournament can be accessed by URL")
    void createdTournamentCanBeAccessedByUrl() {
        assertThat(createdTournamentUrl).isNotNull();

        // Navigate directly to the tournament
        page.navigate(createdTournamentUrl);
        page.waitForLoadState();

        // Verify we can see the tournament
        waitForTestId("tournament-name");
        assertThat(page.getByTestId("tournament-name").textContent()).contains("E2E Test Turnier");
    }

    @Test
    @Order(4)
    @DisplayName("User can view tournament details")
    void canViewTournamentDetails() {
        assertThat(createdTournamentUrl).isNotNull();

        // Navigate directly to the tournament
        page.navigate(createdTournamentUrl);
        page.waitForLoadState();

        // Verify tournament details are shown
        waitForTestId("tournament-name");
        assertThat(page.getByTestId("tournament-name").textContent()).contains("E2E Test Turnier");

        // Verify teams section
        assertThat(page.locator("h3:has-text('Teams')").isVisible()).isTrue();
        assertThat(page.locator("text=Team Alpha").isVisible()).isTrue();

        // Verify boats section
        assertThat(page.locator("h3:has-text('Boote')").isVisible()).isTrue();
        assertThat(page.locator("text=Boot Rot").isVisible()).isTrue();

        // Verify optimization section
        assertThat(page.locator("h3:has-text('Optimierung')").isVisible()).isTrue();
    }

    @Test
    @Order(5)
    @DisplayName("Tournament shows correct configuration")
    void tournamentShowsCorrectConfiguration() {
        assertThat(createdTournamentUrl).isNotNull();

        // Navigate directly to the tournament
        page.navigate(createdTournamentUrl);
        page.waitForLoadState();
        waitForTestId("tournament-name");

        // Verify configuration - use more specific selectors
        assertThat(page.locator("text=Flights:").isVisible()).isTrue();
        assertThat(page.locator("text=Teams:").isVisible()).isTrue();
        assertThat(page.locator("text=Boote:").isVisible()).isTrue();
    }

    @Test
    @Order(6)
    @DisplayName("User can delete tournament")
    void canDeleteTournament() {
        assertThat(createdTournamentUrl).isNotNull();

        // Navigate directly to the tournament
        page.navigate(createdTournamentUrl);
        page.waitForLoadState();
        waitForTestId("tournament-name");

        // Handle confirmation dialog
        page.onDialog(dialog -> dialog.accept());

        // Click delete button
        clickTestId("tournament-delete-button");

        // Should redirect to tournaments list
        page.waitForURL("**/tournaments",
            new com.microsoft.playwright.Page.WaitForURLOptions().setTimeout(15000));
        page.waitForLoadState();

        // Reset the URL since tournament is deleted
        createdTournamentUrl = null;
    }

    @Test
    @Order(7)
    @DisplayName("Form validation requires tournament name")
    void formValidationRequiresName() {
        navigateTo("/tournaments/new");

        // Try to submit without name
        // The save button should be disabled
        Locator saveButton = page.getByTestId("tournament-save-button");
        assertThat(saveButton.isDisabled()).isTrue();
    }

    @Test
    @Order(8)
    @DisplayName("User can remove teams before saving")
    void canRemoveTeamsBeforeSaving() {
        navigateTo("/tournaments/new");

        // Add a team
        fillTestId("team-name-input", "Test Team");
        clickTestId("team-add-button");

        // Verify team was added
        assertThat(page.locator("text=1. Test Team").isVisible()).isTrue();

        // Remove the team (click the ✕ button)
        page.locator("text=1. Test Team").locator("..").locator("button").click();

        // Verify team was removed
        assertThat(page.locator("text=1. Test Team").isVisible()).isFalse();
    }

    @Test
    @Order(9)
    @DisplayName("User can remove boats before saving")
    void canRemoveBoatsBeforeSaving() {
        navigateTo("/tournaments/new");
        page.waitForLoadState();

        // Add a boat
        fillTestId("boat-name-input", "Test Boot XYZ");
        clickTestId("boat-add-button");
        page.waitForTimeout(500);

        // Verify boat was added
        assertThat(page.locator("text=Test Boot XYZ").isVisible()).isTrue();

        // Remove the boat - click the X button that's a sibling of the boat name
        // The structure is: <div><div>boat name</div><button>✕</button></div>
        page.locator("button:has-text('✕')").last().click();
        page.waitForTimeout(500);

        // Verify boat was removed
        assertThat(page.locator("text=Test Boot XYZ").count()).isEqualTo(0);
    }
}
