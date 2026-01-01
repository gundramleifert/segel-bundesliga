package de.segelbundesliga.e2e;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.*;

/**
 * E2E tests for authentication flows.
 *
 * User Stories:
 * - US-AUTH-01: User can log in via Zitadel
 * - US-AUTH-02: User can log out
 */
@TestMethodOrder(MethodOrderer.OrderAnnotation.class)
@DisplayName("Authentication Tests")
class AuthTest extends E2ETestBase {

    @Override
    protected boolean requiresAuthentication() {
        // First test needs to login manually
        return false;
    }

    @Test
    @Order(1)
    @DisplayName("US-AUTH-01: User can log in via Zitadel")
    void userCanLogin() {
        // Given: User is on the homepage, not logged in
        navigateTo("/");
        assertThat(isVisibleTestId("login-button")).isTrue();

        // When: User performs login
        performLogin();

        // Then: User is logged in and sees their name
        assertThat(isLoggedIn()).isTrue();
        assertThat(page.url()).startsWith(TestFixtures.TEST_TARGET);
    }

    @Test
    @Order(2)
    @DisplayName("US-AUTH-02: User can log out")
    void userCanLogout() {
        // Given: User is logged in
        if (!isLoggedIn()) {
            performLogin();
        }
        assertThat(isLoggedIn()).isTrue();

        // When: User clicks logout
        performLogout();

        // Then: User is logged out, login button visible
        assertThat(isLoggedIn()).isFalse();
        assertThat(isVisibleTestId("login-button")).isTrue();
    }

    @Test
    @Order(3)
    @DisplayName("Protected routes redirect to login")
    void protectedRoutesRedirectToLogin() {
        // Given: User is not logged in
        if (isLoggedIn()) {
            performLogout();
        }

        // When: User tries to access protected route
        navigateTo("/tournaments");

        // Then: Either redirected to login or login button shown
        // (behavior depends on app implementation)
        page.waitForTimeout(2000);

        boolean onLoginPage = page.url().contains("localhost:8081");
        boolean showsLoginButton = isVisibleTestId("login-button");

        assertThat(onLoginPage || showsLoginButton)
                .as("Should either redirect to Zitadel or show login button")
                .isTrue();
    }
}
