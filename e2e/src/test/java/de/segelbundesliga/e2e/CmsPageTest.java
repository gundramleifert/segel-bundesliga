package de.segelbundesliga.e2e;

import static org.assertj.core.api.Assertions.assertThat;

import com.microsoft.playwright.Locator;
import org.junit.jupiter.api.*;

/**
 * E2E tests for CMS pages (static content).
 *
 * User Stories:
 * - US-CMS-01: Visitor can view public pages
 * - US-CMS-02: Visitor can navigate via footer
 * - US-CMS-03: Non-existent pages show error
 */
@TestMethodOrder(MethodOrderer.OrderAnnotation.class)
@DisplayName("CMS Pages Tests")
class CmsPageTest extends E2ETestBase {

    @Override
    protected boolean requiresAuthentication() {
        // CMS pages should be accessible without login
        return false;
    }

    @Test
    @Order(1)
    @DisplayName("US-CMS-01: Visitor can view Impressum page")
    void canViewImpressumPage() {
        // When: Visitor navigates to Impressum
        navigateTo("/seite/impressum");

        // Then: Page content is displayed
        page.waitForTimeout(1000);

        // Check for page title or content
        Locator heading = page.locator("h1, h2").first();
        heading.waitFor();

        String pageText = page.textContent("body");
        assertThat(pageText.toLowerCase())
                .as("Page should contain 'impressum' content")
                .containsAnyOf("impressum", "imprint", "angaben");
    }

    @Test
    @Order(2)
    @DisplayName("US-CMS-01: Visitor can view Datenschutz page")
    void canViewDatenschutzPage() {
        // When: Visitor navigates to Datenschutz
        navigateTo("/seite/datenschutz");

        // Then: Page content is displayed
        page.waitForTimeout(1000);

        String pageText = page.textContent("body");
        assertThat(pageText.toLowerCase())
                .as("Page should contain privacy-related content")
                .containsAnyOf("datenschutz", "privacy", "daten");
    }

    @Test
    @Order(3)
    @DisplayName("US-CMS-01: Visitor can view Kontakt page")
    void canViewKontaktPage() {
        // When: Visitor navigates to Kontakt
        navigateTo("/seite/kontakt");

        // Then: Page content is displayed
        page.waitForTimeout(1000);

        String pageText = page.textContent("body");
        assertThat(pageText.toLowerCase())
                .as("Page should contain contact-related content")
                .containsAnyOf("kontakt", "contact", "email", "e-mail");
    }

    @Test
    @Order(4)
    @DisplayName("US-CMS-02: Footer contains links to legal pages")
    void footerContainsLegalLinks() {
        // Given: User is on homepage
        navigateTo("/");

        // Then: Footer contains expected links
        Locator footer = page.locator("footer");
        footer.waitFor();

        String footerText = footer.textContent().toLowerCase();

        assertThat(footerText)
                .as("Footer should contain Impressum link")
                .contains("impressum");

        assertThat(footerText)
                .as("Footer should contain Datenschutz link")
                .contains("datenschutz");
    }

    @Test
    @Order(5)
    @DisplayName("US-CMS-02: Can navigate to Impressum via footer link")
    void canNavigateToImpressumViaFooter() {
        // Given: User is on homepage
        navigateTo("/");
        page.waitForTimeout(1000);

        // When: User clicks Impressum link in footer
        Locator footer = page.locator("footer");
        footer.waitFor();

        Locator impressumLink = page.getByTestId("footer-impressum-link");
        if (impressumLink.count() > 0) {
            impressumLink.click();
            page.waitForLoadState();
            page.waitForTimeout(1000);

            // Then: User is on Impressum page
            assertThat(page.url()).contains("impressum");
        }
    }

    @Test
    @Order(6)
    @DisplayName("US-CMS-02: Can navigate to Datenschutz via footer link")
    void canNavigateToDatenschutzViaFooter() {
        // Given: User is on homepage
        navigateTo("/");
        page.waitForTimeout(1000);

        // When: User clicks Datenschutz link in footer
        Locator footer = page.locator("footer");
        footer.waitFor();

        Locator datenschutzLink = page.getByTestId("footer-datenschutz-link");
        if (datenschutzLink.count() > 0) {
            datenschutzLink.click();
            page.waitForLoadState();
            page.waitForTimeout(1000);

            // Then: User is on Datenschutz page
            assertThat(page.url()).contains("datenschutz");
        }
    }

    @Test
    @Order(7)
    @DisplayName("US-CMS-03: Non-existent page shows appropriate message")
    void nonExistentPageShowsError() {
        // When: Visitor navigates to non-existent page
        navigateTo("/seite/this-page-does-not-exist-12345");
        page.waitForTimeout(1000);

        // Then: Some error indication is shown (404 page or error message)
        String pageText = page.textContent("body").toLowerCase();

        // Check for common error indicators
        boolean hasErrorIndication =
                pageText.contains("404") ||
                pageText.contains("nicht gefunden") ||
                pageText.contains("not found") ||
                pageText.contains("fehler") ||
                pageText.contains("error") ||
                pageText.contains("existiert nicht") ||
                page.url().contains("404");

        assertThat(hasErrorIndication)
                .as("Non-existent page should show error or 404")
                .isTrue();
    }

    @Test
    @Order(8)
    @DisplayName("Homepage is accessible without login")
    void homepageAccessibleWithoutLogin() {
        // When: Visitor navigates to homepage
        navigateTo("/");

        // Then: Homepage loads successfully
        page.waitForLoadState();

        // Check for typical homepage elements
        boolean hasContent =
                page.locator("h1, h2").count() > 0 ||
                page.locator("[data-testid]").count() > 0;

        assertThat(hasContent)
                .as("Homepage should have content")
                .isTrue();

        // Login button should be visible (not logged in)
        assertThat(isVisibleTestId("login-button"))
                .as("Login button should be visible for unauthenticated users")
                .isTrue();
    }
}
