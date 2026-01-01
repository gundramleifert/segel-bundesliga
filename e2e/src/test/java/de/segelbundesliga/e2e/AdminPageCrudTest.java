package de.segelbundesliga.e2e;

import static de.segelbundesliga.e2e.TestFixtures.*;
import static org.assertj.core.api.Assertions.assertThat;

import com.microsoft.playwright.Locator;
import com.microsoft.playwright.Page;
import com.microsoft.playwright.options.AriaRole;
import lombok.extern.slf4j.Slf4j;
import org.junit.jupiter.api.*;

import java.util.UUID;

/**
 * E2E tests for Admin Panel page management.
 *
 * User Stories:
 * - US-ADMIN-01: Admin can create a new page via Admin Panel
 * - US-ADMIN-02: Admin can edit an existing page
 * - US-ADMIN-03: Admin can delete a page
 * - US-ADMIN-04: Created page is accessible via public URL
 */
@Slf4j
@TestMethodOrder(MethodOrderer.OrderAnnotation.class)
@DisplayName("Admin Panel - Page CRUD Tests")
class AdminPageCrudTest extends E2ETestBase {

    // Admin credentials (user with ADMIN role)
    private static final String ADMIN_USER = "admin";
    private static final String ADMIN_PASSWORD = "test1234";

    // Unique test data to avoid conflicts
    private static final String TEST_PAGE_SLUG = "e2e-test-page-" + UUID.randomUUID().toString().substring(0, 8);
    private static final String TEST_PAGE_TITLE = "E2E Test Page";
    private static final String TEST_PAGE_CONTENT = "This is a test page created by E2E tests.";
    private static final String TEST_PAGE_TITLE_UPDATED = "E2E Test Page (Updated)";

    @Override
    protected boolean requiresAuthentication() {
        return true;
    }

    /**
     * Override login to use admin credentials instead of testuser.
     */
    @Override
    protected void performLogin() {
        performLogin(ADMIN_USER, ADMIN_PASSWORD);
    }

    @Test
    @Order(1)
    @DisplayName("US-ADMIN-01: Admin can navigate to Admin Panel")
    void canNavigateToAdminPanel() {
        navigateTo("/admin");
        page.waitForTimeout(2000);
        page.waitForLoadState();

        String bodyText = page.textContent("body");
        log.debug("Admin URL: {}", page.url());

        assertThat(bodyText)
                .as("Admin panel should show 'Seiten' resource")
                .containsIgnoringCase("seiten");
    }

    @Test
    @Order(2)
    @DisplayName("US-ADMIN-01: Admin can open page creation form")
    void canOpenPageCreationForm() {
        navigateTo("/admin/pages");
        page.waitForTimeout(2000);

        Locator createButton = page.getByRole(AriaRole.LINK, new Page.GetByRoleOptions().setName("Create"));
        if (!createButton.isVisible()) {
            createButton = page.locator("a[href*='create'], button:has-text('Create'), button:has-text('Erstellen')").first();
        }
        createButton.click();
        page.waitForTimeout(1000);

        assertThat(page.url())
                .as("Should be on page creation form")
                .contains("/pages/create");
    }

    @Test
    @Order(3)
    @DisplayName("US-ADMIN-01: Admin can create a new page")
    void canCreateNewPage() {
        navigateTo("/admin/pages/create");
        page.waitForTimeout(2000);

        Locator titleInput = page.getByTestId("admin-page-title-input");
        titleInput.waitFor();
        titleInput.fill(TEST_PAGE_TITLE);

        Locator slugInput = page.getByTestId("admin-page-slug-input");
        slugInput.fill(TEST_PAGE_SLUG);

        Locator contentInput = page.getByTestId("admin-page-content-input");
        contentInput.fill(TEST_PAGE_CONTENT);

        page.waitForTimeout(500);
        Locator saveButton = page.getByTestId("admin-page-save-button");
        saveButton.waitFor();
        saveButton.click();

        page.waitForTimeout(3000);
        page.waitForLoadState();

        log.debug("URL after save: {}", page.url());

        assertThat(page.url())
                .as("Should redirect after successful creation")
                .containsAnyOf("/admin/pages", "/admin#/pages", "/pages/create");

        navigateTo("/admin/pages");
        page.waitForTimeout(2000);

        String listContent = page.textContent("body");
        assertThat(listContent)
                .as("Created page should appear in the list")
                .contains(TEST_PAGE_TITLE);
    }

    @Test
    @Order(4)
    @DisplayName("US-ADMIN-04: Created page is accessible via public URL")
    void createdPageIsAccessiblePublicly() {
        navigateTo("/seite/" + TEST_PAGE_SLUG);
        page.waitForTimeout(2000);

        String pageText = page.textContent("body");

        assertThat(pageText)
                .as("Page should display the title")
                .contains(TEST_PAGE_TITLE);

        assertThat(pageText)
                .as("Page should display the content")
                .contains(TEST_PAGE_CONTENT);
    }

    @Test
    @Order(5)
    @DisplayName("US-ADMIN-02: Admin can edit an existing page")
    void canEditExistingPage() {
        navigateTo("/admin/pages");
        page.waitForTimeout(2000);

        Locator testPageRow = page.locator("tr:has-text('" + TEST_PAGE_SLUG + "')").first();
        log.debug("Looking for page with slug: {}, found: {}", TEST_PAGE_SLUG, testPageRow.isVisible());

        if (testPageRow.isVisible()) {
            Locator editButton = testPageRow.getByRole(AriaRole.LINK, new Locator.GetByRoleOptions().setName("Edit"));
            if (!editButton.isVisible()) {
                editButton = testPageRow.locator("a[href*='edit'], button:has-text('Edit')").first();
            }
            editButton.click();
        } else {
            throw new AssertionError("Test page with slug '" + TEST_PAGE_SLUG + "' not found in list");
        }

        page.waitForTimeout(2000);
        log.debug("Edit form URL: {}", page.url());

        Locator titleInput = page.getByTestId("admin-page-title-input");
        titleInput.waitFor();
        titleInput.clear();
        titleInput.type(TEST_PAGE_TITLE_UPDATED);
        page.waitForTimeout(300);

        Locator saveButton = page.getByTestId("admin-page-save-button");
        saveButton.waitFor();
        log.debug("Save button visible: {}", saveButton.isVisible());
        saveButton.click();

        page.waitForTimeout(5000);
        log.debug("URL after save: {}", page.url());

        navigateTo("/admin/pages");
        page.waitForTimeout(3000);

        page.locator("table").first().waitFor();
        page.waitForTimeout(1000);

        String listContent = page.textContent("body");
        log.debug("List contains updated title: {}", listContent.contains(TEST_PAGE_TITLE_UPDATED));

        assertThat(listContent)
                .as("Updated page title should appear in the list")
                .contains(TEST_PAGE_TITLE_UPDATED);
    }

    @Test
    @Order(6)
    @DisplayName("US-ADMIN-03: Admin can delete a page")
    void canDeletePage() {
        navigateTo("/admin/pages");
        page.waitForTimeout(2000);

        Locator testPageRow = page.locator("tr:has-text('" + TEST_PAGE_SLUG + "')").first();
        log.debug("Looking for row with slug: {}, found: {}", TEST_PAGE_SLUG, testPageRow.isVisible());

        if (testPageRow.isVisible()) {
            Locator deleteButton = testPageRow.getByTestId("admin-page-delete-button");
            log.debug("Delete button found: {}", deleteButton.isVisible());
            deleteButton.click();

            page.waitForTimeout(500);
            Locator confirmButton = page.getByTestId("admin-confirm-delete-button");
            confirmButton.waitFor();
            log.debug("Clicking confirm button");
            confirmButton.click();
        } else {
            throw new AssertionError("Test page with slug '" + TEST_PAGE_SLUG + "' not found for deletion");
        }

        page.waitForTimeout(3000);

        navigateTo("/admin/pages");
        page.waitForTimeout(2000);

        String listContent = page.textContent("body");
        log.debug("List after delete contains slug: {}", listContent.contains(TEST_PAGE_SLUG));
        assertThat(listContent)
                .as("Deleted page should not appear in the list")
                .doesNotContain(TEST_PAGE_SLUG);
    }

    @Test
    @Order(7)
    @DisplayName("Deleted page returns 404 or error")
    void deletedPageReturnsError() {
        navigateTo("/seite/" + TEST_PAGE_SLUG);
        page.waitForTimeout(2000);

        String pageText = page.textContent("body").toLowerCase();

        boolean hasErrorIndication =
                pageText.contains("404") ||
                pageText.contains("nicht gefunden") ||
                pageText.contains("not found") ||
                pageText.contains("fehler") ||
                pageText.contains("error") ||
                pageText.contains("existiert nicht");

        assertThat(hasErrorIndication)
                .as("Deleted page should show error or 404")
                .isTrue();
    }
}
