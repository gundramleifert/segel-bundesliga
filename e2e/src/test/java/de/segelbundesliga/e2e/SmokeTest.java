package de.segelbundesliga.e2e;

import org.junit.jupiter.api.*;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Basic smoke tests to verify the application is running.
 */
@TestMethodOrder(MethodOrderer.OrderAnnotation.class)
class SmokeTest extends BaseE2ETest {

    @Test
    @Order(1)
    @DisplayName("Homepage loads successfully")
    void homepageLoads() {
        navigateTo("/");

        // Verify page loaded
        assertThat(page.title()).isNotEmpty();
    }

    @Test
    @Order(2)
    @DisplayName("App title is visible")
    void appTitleIsVisible() {
        navigateTo("/");

        assertThat(page.getByTestId("app-title").isVisible()).isTrue();
        assertThat(page.getByTestId("app-title").textContent()).isEqualTo("Segel-Bundesliga");
    }

    @Test
    @Order(3)
    @DisplayName("Welcome message is visible")
    void welcomeMessageIsVisible() {
        navigateTo("/");

        assertThat(page.getByTestId("welcome-message").isVisible()).isTrue();
        assertThat(page.getByTestId("welcome-message").textContent())
            .contains("Willkommen zur Segel-Bundesliga");
    }

    @Test
    @Order(4)
    @DisplayName("Login button is visible for unauthenticated users")
    void loginButtonIsVisible() {
        navigateTo("/");

        assertThat(page.getByTestId("login-button").isVisible()).isTrue();
    }

    @Test
    @Order(5)
    @DisplayName("API is accessible")
    void apiIsAccessible() {
        // Navigate to API - any endpoint that returns JSON
        page.navigate("http://localhost:8080/api/tournaments");

        // Should return some response (even if 401 unauthorized)
        assertThat(page.content()).isNotEmpty();
    }
}
