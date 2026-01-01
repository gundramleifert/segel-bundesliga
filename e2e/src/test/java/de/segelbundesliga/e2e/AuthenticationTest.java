package de.segelbundesliga.e2e;

import static de.segelbundesliga.e2e.TestFixtures.*;
import static org.assertj.core.api.Assertions.assertThat;

import com.microsoft.playwright.*;
import com.microsoft.playwright.options.AriaRole;
import org.junit.jupiter.api.*;

/**
 * E2E tests for authentication flows via Zitadel.
 * Uses the same approach as jaide tests.
 */
@TestMethodOrder(MethodOrderer.OrderAnnotation.class)
class AuthenticationTest {

    private Page page;

    @BeforeEach
    void setUp() {
        page = PlaywrightThreadFactory.getPage(false);
    }

    @AfterEach
    void tearDown() {
        PlaywrightThreadFactory.closePage();
    }

    @Test
    @Order(1)
    @DisplayName("User can log in via Zitadel")
    void userCanLogin() {
        // Navigate to app
        page.navigate(TEST_TARGET);
        page.waitForLoadState();
        System.out.println("App loaded: " + page.url());

        // Click login button
        Locator loginButton = page.getByTestId("login-button");
        page.waitForTimeout(1000);  // Wait for JS to initialize
        System.out.println("Login button visible: " + loginButton.isVisible());

        if (loginButton.isVisible()) {
            System.out.println("Login button visible, clicking...");
            loginButton.click();
        } else {
            // Maybe already on Zitadel or auto-redirect
            System.out.println("No login button found, checking current URL...");
        }

        // Wait for redirect to Zitadel
        page.waitForURL(url -> url.contains("localhost:8081"),
                new Page.WaitForURLOptions().setTimeout(DEFAULT_NAVIGATION_TIMEOUT_IN_MS));
        System.out.println("On Zitadel login page: " + page.url());

        // Wait for Zitadel page to fully load
        page.waitForLoadState();
        page.waitForTimeout(2000);

        // Debug: Print page title and screenshot
        System.out.println("Zitadel page title: " + page.title());
        page.screenshot(new Page.ScreenshotOptions().setPath(java.nio.file.Paths.get("./build/debug-zitadel-page.png")));
        System.out.println("Screenshot saved to ./build/debug-zitadel-page.png");

        // Enter username - German UI: "Loginname" not "Login Name"
        Locator loginName = page.getByRole(AriaRole.TEXTBOX,
                new Page.GetByRoleOptions().setName("Loginname"));
        loginName.waitFor(new Locator.WaitForOptions().setTimeout(10000));
        loginName.dispatchEvent("click");
        loginName.fill(TEST_USER);
        // German button: "Weiter" not "Next"
        page.getByRole(AriaRole.BUTTON, new Page.GetByRoleOptions().setName("Weiter"))
                .dispatchEvent("click");

        System.out.println("After username: " + page.url());

        // Wait for password page
        page.waitForTimeout(1000);

        // Enter password - German UI: "Passwort" not "Password"
        Locator loginPassword = page.getByRole(AriaRole.TEXTBOX,
                new Page.GetByRoleOptions().setName("Passwort"));
        loginPassword.dispatchEvent("click");
        loginPassword.fill(TEST_PASSWORD);
        page.getByRole(AriaRole.BUTTON, new Page.GetByRoleOptions().setName("Weiter"))
                .dispatchEvent("click");

        page.waitForTimeout(2000);
        System.out.println("After password: " + page.url());

        // Handle 2-Factor Setup if it appears (German: "2-Faktor-Einrichtung" or similar)
        String title = page.title();
        System.out.println("Page title after password: " + title);
        if (title.contains("2-Faktor") || title.contains("2-Factor")) {
            // Try German "Überspringen" or English "Skip"
            Locator skipButton = page.getByRole(AriaRole.BUTTON,
                    new Page.GetByRoleOptions().setName("Überspringen"));
            if (!skipButton.isVisible()) {
                skipButton = page.getByRole(AriaRole.BUTTON,
                        new Page.GetByRoleOptions().setName("Skip"));
            }
            if (skipButton.isVisible()) {
                skipButton.dispatchEvent("click");
            }
        }

        // Wait for redirect back to app
        page.waitForURL(url -> url.startsWith(TEST_TARGET),
                new Page.WaitForURLOptions().setTimeout(DEFAULT_NAVIGATION_TIMEOUT_IN_MS));

        // Verify we're on the homepage
        assertThat(page.url()).startsWith(TEST_TARGET);
        System.out.println("Login successful: " + page.url());

        // Save the authenticated state for other tests
        PlaywrightThreadFactory.saveStorageState();
    }
}
