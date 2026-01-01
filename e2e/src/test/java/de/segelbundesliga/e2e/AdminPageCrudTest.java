package de.segelbundesliga.e2e;

import static de.segelbundesliga.e2e.TestFixtures.*;
import static org.assertj.core.api.Assertions.assertThat;

import com.microsoft.playwright.Locator;
import com.microsoft.playwright.Page;
import com.microsoft.playwright.options.AriaRole;
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
        // When: Admin navigates to admin panel
        navigateTo("/admin");
        page.waitForTimeout(2000);

        // Then: Admin panel is displayed with Pages resource
        page.waitForLoadState();

        // React-admin should show the resource list
        // Look for "Seiten" (German for Pages) in the sidebar
        String bodyText = page.textContent("body");
        System.out.println("Admin URL: " + page.url());
        System.out.println("Admin sees 'Seiten': " + bodyText.toLowerCase().contains("seiten"));

        assertThat(bodyText)
                .as("Admin panel should show 'Seiten' resource")
                .containsIgnoringCase("seiten");
    }

    @Test
    @Order(2)
    @DisplayName("US-ADMIN-01: Admin can open page creation form")
    void canOpenPageCreationForm() {
        // Given: Admin is on admin panel
        navigateTo("/admin/pages");
        page.waitForTimeout(2000);

        // When: Admin clicks Create button
        Locator createButton = page.getByRole(AriaRole.LINK, new Page.GetByRoleOptions().setName("Create"));
        if (!createButton.isVisible()) {
            // Try alternative: button with "Create" or "Erstellen"
            createButton = page.locator("a[href*='create'], button:has-text('Create'), button:has-text('Erstellen')").first();
        }
        createButton.click();
        page.waitForTimeout(1000);

        // Then: Creation form is displayed
        assertThat(page.url())
                .as("Should be on page creation form")
                .contains("/pages/create");
    }

    @Test
    @Order(3)
    @DisplayName("US-ADMIN-01: Admin can create a new page")
    void canCreateNewPage() {
        // Given: Admin is on page creation form
        navigateTo("/admin/pages/create");
        page.waitForTimeout(2000);

        // When: Admin fills the form using data-testid selectors
        // Title (DE)
        Locator titleInput = page.getByTestId("admin-page-title-input");
        titleInput.waitFor();
        titleInput.fill(TEST_PAGE_TITLE);

        // Slug
        Locator slugInput = page.getByTestId("admin-page-slug-input");
        slugInput.fill(TEST_PAGE_SLUG);

        // Content (DE)
        Locator contentInput = page.getByTestId("admin-page-content-input");
        contentInput.fill(TEST_PAGE_CONTENT);

        // Visibility defaults to PUBLIC - no need to change

        // And: Admin clicks Save using data-testid
        page.waitForTimeout(500);
        Locator saveButton = page.getByTestId("admin-page-save-button");
        saveButton.waitFor();
        saveButton.click();

        // Then: Page is created and user is redirected to list or show view
        page.waitForTimeout(3000);
        page.waitForLoadState();

        // Debug output
        System.out.println("URL after save: " + page.url());
        System.out.println("Body after save: " + page.textContent("body").substring(0, Math.min(500, page.textContent("body").length())));

        // Verify we're back on the list or show page (react-admin uses hash routing)
        assertThat(page.url())
                .as("Should redirect after successful creation")
                .containsAnyOf("/admin/pages", "/admin#/pages", "/pages/create");

        // Verify the page appears in the list
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
        // When: Visitor navigates to the created page
        navigateTo("/seite/" + TEST_PAGE_SLUG);
        page.waitForTimeout(2000);

        // Then: Page content is displayed
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
        // Given: Admin is on pages list
        navigateTo("/admin/pages");
        page.waitForTimeout(2000);

        // Debug output
        System.out.println("Looking for page with title: " + TEST_PAGE_TITLE);
        System.out.println("Looking for page with slug: " + TEST_PAGE_SLUG);
        System.out.println("Current page list:\n" + page.textContent("body").substring(0, Math.min(1000, page.textContent("body").length())));

        // When: Admin clicks edit on the test page
        // Find the row with our test page by SLUG (unique identifier)
        Locator testPageRow = page.locator("tr:has-text('" + TEST_PAGE_SLUG + "')").first();
        System.out.println("Found row with slug: " + testPageRow.isVisible());

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
        System.out.println("Edit form URL: " + page.url());

        // Update the title using data-testid
        Locator titleInput = page.getByTestId("admin-page-title-input");
        titleInput.waitFor();

        // Clear and type new value for proper React form handling
        titleInput.clear();
        titleInput.type(TEST_PAGE_TITLE_UPDATED);
        page.waitForTimeout(300);
        System.out.println("Title input value after change: " + titleInput.inputValue());

        // Save changes using data-testid
        Locator saveButton = page.getByTestId("admin-page-save-button");
        saveButton.waitFor();
        System.out.println("Save button visible: " + saveButton.isVisible());
        System.out.println("Clicking save button...");
        saveButton.click();

        // Wait for pessimistic mutation to complete
        page.waitForTimeout(2000);
        System.out.println("URL after clicking save: " + page.url());

        page.waitForTimeout(3000);
        System.out.println("URL after save: " + page.url());
        System.out.println("Body after save: " + page.textContent("body").substring(0, Math.min(300, page.textContent("body").length())));

        // Then: Changes are saved
        navigateTo("/admin/pages");
        page.waitForTimeout(3000);

        // Wait for table to be visible
        page.locator("table").first().waitFor();
        page.waitForTimeout(1000);

        System.out.println("URL after navigate to list: " + page.url());
        // Check if still logged in
        System.out.println("User still logged in: " + isLoggedIn());
        String listContent = page.textContent("body");
        System.out.println("After edit, looking for: " + TEST_PAGE_TITLE_UPDATED);
        System.out.println("List contains updated title: " + listContent.contains(TEST_PAGE_TITLE_UPDATED));
        System.out.println("List content trimmed: '" + listContent.trim().replaceAll("\\s+", " ").substring(0, Math.min(500, listContent.trim().length())) + "'");

        assertThat(listContent)
                .as("Updated page title should appear in the list")
                .contains(TEST_PAGE_TITLE_UPDATED);
    }

    @Test
    @Order(6)
    @DisplayName("US-ADMIN-03: Admin can delete a page")
    void canDeletePage() {
        // Given: Admin is on pages list
        navigateTo("/admin/pages");
        page.waitForTimeout(2000);

        // When: Admin clicks delete on the test page (by unique slug)
        Locator testPageRow = page.locator("tr:has-text('" + TEST_PAGE_SLUG + "')").first();
        System.out.println("Looking for row with slug: " + TEST_PAGE_SLUG);
        System.out.println("Found row for delete: " + testPageRow.isVisible());

        if (testPageRow.isVisible()) {
            // Click delete button using data-testid (pessimistic mode shows confirmation)
            Locator deleteButton = testPageRow.getByTestId("admin-page-delete-button");
            System.out.println("Delete button found: " + deleteButton.isVisible());
            deleteButton.click();

            // Wait for and confirm the react-admin confirmation dialog
            page.waitForTimeout(500);
            Locator confirmButton = page.getByRole(AriaRole.BUTTON, new Page.GetByRoleOptions().setName("Confirm"));
            if (confirmButton.isVisible()) {
                System.out.println("Clicking confirm button...");
                confirmButton.click();
            }
        } else {
            throw new AssertionError("Test page with slug '" + TEST_PAGE_SLUG + "' not found for deletion");
        }

        // Wait for delete to complete
        page.waitForTimeout(3000);

        // Then: Page is removed from the list
        navigateTo("/admin/pages");
        page.waitForTimeout(2000);

        String listContent = page.textContent("body");
        System.out.println("List after delete contains slug: " + listContent.contains(TEST_PAGE_SLUG));
        assertThat(listContent)
                .as("Deleted page should not appear in the list")
                .doesNotContain(TEST_PAGE_SLUG);
    }

    @Test
    @Order(7)
    @DisplayName("Deleted page returns 404 or error")
    void deletedPageReturnsError() {
        // When: Visitor tries to access the deleted page
        navigateTo("/seite/" + TEST_PAGE_SLUG);
        page.waitForTimeout(2000);

        // Then: Error is displayed
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
