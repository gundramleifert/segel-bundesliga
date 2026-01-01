package de.segelbundesliga.e2e;

import static de.segelbundesliga.e2e.TestFixtures.*;

import com.microsoft.playwright.*;
import com.microsoft.playwright.options.AriaRole;

/**
 * Helper class for Zitadel authentication in E2E tests.
 */
public class TestLogins {

    /**
     * Perform login and save the authenticated state for reuse.
     * Call this once before running authenticated tests.
     */
    public static void getZitadelLoginState() {
        Page page = PlaywrightThreadFactory.getPage(false);
        page.navigate(TEST_TARGET);
        loginToZitadelAs(TEST_USER, TEST_PASSWORD, page);
        PlaywrightThreadFactory.saveStorageState();
        PlaywrightThreadFactory.closePage();
    }

    /**
     * Login to Zitadel with the given credentials.
     * Uses the proven approach from jaide tests with getByRole and dispatchEvent.
     * Note: German Zitadel UI uses "Loginname", "Passwort", "Weiter"
     *
     * @param user Username/login name
     * @param pwd Password
     * @param page Playwright page instance
     */
    public static void loginToZitadelAs(String user, String pwd, Page page) {
        // Click login button to redirect to Zitadel
        Locator loginButton = page.getByTestId("login-button");
        if (loginButton.isVisible()) {
            loginButton.click();
            page.waitForURL(url -> url.contains(ZITADEL_URL),
                    new Page.WaitForURLOptions().setTimeout(DEFAULT_NAVIGATION_TIMEOUT_IN_MS));
        }

        // Wait for Zitadel page to load
        page.waitForLoadState();

        // Enter username (German: "Loginname")
        Locator loginName = page.getByRole(AriaRole.TEXTBOX,
                new Page.GetByRoleOptions().setName("Loginname"));
        loginName.dispatchEvent("click");
        loginName.fill(user);
        page.getByRole(AriaRole.BUTTON, new Page.GetByRoleOptions().setName("Weiter"))
                .dispatchEvent("click");

        // Wait for password page
        page.waitForTimeout(1000);

        // Enter password (German: "Passwort")
        Locator loginPassword = page.getByRole(AriaRole.TEXTBOX,
                new Page.GetByRoleOptions().setName("Passwort"));
        loginPassword.dispatchEvent("click");
        loginPassword.fill(pwd);
        page.getByRole(AriaRole.BUTTON, new Page.GetByRoleOptions().setName("Weiter"))
                .dispatchEvent("click");

        // Wait and handle 2FA setup prompt if it appears
        page.waitForTimeout(2000);
        String title = page.title();
        if (title.contains("2-Faktor") || title.contains("2-Factor")) {
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
    }
}
