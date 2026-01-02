package de.segelbundesliga.service;

import de.segelbundesliga.domain.Page;
import de.segelbundesliga.domain.Page.Visibility;
import de.segelbundesliga.dto.PageDto;
import de.segelbundesliga.repository.PageRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;

import java.time.Instant;
import java.util.ArrayList;
import java.util.Collection;
import java.util.List;
import java.util.Optional;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
@DisplayName("PageService Tests")
class PageServiceTest {

    @Mock
    private PageRepository repository;

    @InjectMocks
    private PageService service;

    private Page testPage;

    @BeforeEach
    void setUp() {
        testPage = createTestPage();
    }

    private Page createTestPage() {
        Page page = new Page();
        page.setId(1L);
        page.setTitle("Test Page");
        page.setTitleEn("Test Page EN");
        page.setSlug("test-page");
        page.setContent("Test content");
        page.setContentEn("Test content EN");
        page.setVisibility(Visibility.PUBLIC);
        page.setSortOrder(0);
        page.setShowInMenu(true);
        page.setParent(null);
        page.setImages(new ArrayList<>());
        page.setCreatedAt(Instant.now());
        page.setUpdatedAt(Instant.now());
        return page;
    }

    @Nested
    @DisplayName("create()")
    class CreateTests {

        @Test
        @DisplayName("creates page with all fields")
        void create_allFields_success() {
            PageDto.Create dto = new PageDto.Create();
            dto.setTitle("New Page");
            dto.setTitleEn("New Page EN");
            dto.setSlug("new-page");
            dto.setContent("Content");
            dto.setContentEn("Content EN");
            dto.setVisibility(Visibility.PUBLIC);
            dto.setSortOrder(5);
            dto.setShowInMenu(true);
            dto.setParentId(10L);

            Page parentPage = new Page();
            parentPage.setId(10L);
            parentPage.setTitle("Parent Page");
            parentPage.setSlug("parent");
            parentPage.setContent("Parent content");

            when(repository.existsBySlug("new-page")).thenReturn(false);
            when(repository.findById(10L)).thenReturn(Optional.of(parentPage));
            when(repository.save(any(Page.class))).thenAnswer(invocation -> {
                Page p = invocation.getArgument(0);
                p.setId(1L);
                p.setCreatedAt(Instant.now());
                return p;
            });

            PageDto.Response response = service.create(dto);

            assertThat(response.getTitle()).isEqualTo("New Page");
            assertThat(response.getSlug()).isEqualTo("new-page");
            assertThat(response.getSortOrder()).isEqualTo(5);
            assertThat(response.getShowInMenu()).isTrue();
            assertThat(response.getParentId()).isEqualTo(10L);
        }

        @Test
        @DisplayName("throws exception for duplicate slug")
        void create_duplicateSlug_throwsException() {
            PageDto.Create dto = new PageDto.Create();
            dto.setTitle("Page");
            dto.setSlug("existing-slug");
            dto.setContent("Content");

            when(repository.existsBySlug("existing-slug")).thenReturn(true);

            assertThatThrownBy(() -> service.create(dto))
                    .isInstanceOf(IllegalArgumentException.class)
                    .hasMessageContaining("Slug already exists");
        }

        @Test
        @DisplayName("creates page with minimal fields")
        void create_minimalFields_success() {
            PageDto.Create dto = new PageDto.Create();
            dto.setTitle("Minimal Page");
            dto.setSlug("minimal-page");
            dto.setContent("Content");

            when(repository.existsBySlug("minimal-page")).thenReturn(false);
            when(repository.save(any(Page.class))).thenAnswer(invocation -> {
                Page p = invocation.getArgument(0);
                p.setId(1L);
                return p;
            });

            PageDto.Response response = service.create(dto);

            assertThat(response.getTitle()).isEqualTo("Minimal Page");
            assertThat(response.getParentId()).isNull();
        }
    }

    @Nested
    @DisplayName("getById()")
    class GetByIdTests {

        @Test
        @DisplayName("returns page when found")
        void getById_found_returnsPage() {
            when(repository.findById(1L)).thenReturn(Optional.of(testPage));

            PageDto.Response response = service.getById(1L);

            assertThat(response.getId()).isEqualTo(1L);
            assertThat(response.getTitle()).isEqualTo("Test Page");
        }

        @Test
        @DisplayName("throws EntityNotFoundException when not found")
        void getById_notFound_throwsException() {
            when(repository.findById(999L)).thenReturn(Optional.empty());

            assertThatThrownBy(() -> service.getById(999L))
                    .isInstanceOf(EntityNotFoundException.class)
                    .hasMessageContaining("Page");
        }
    }

    @Nested
    @DisplayName("getBySlug()")
    class GetBySlugTests {

        @Test
        @DisplayName("returns page when found")
        void getBySlug_found_returnsPage() {
            when(repository.findBySlug("test-page")).thenReturn(Optional.of(testPage));

            PageDto.Response response = service.getBySlug("test-page");

            assertThat(response.getSlug()).isEqualTo("test-page");
        }

        @Test
        @DisplayName("throws EntityNotFoundException when not found")
        void getBySlug_notFound_throwsException() {
            when(repository.findBySlug("nonexistent")).thenReturn(Optional.empty());

            assertThatThrownBy(() -> service.getBySlug("nonexistent"))
                    .isInstanceOf(EntityNotFoundException.class);
        }
    }

    @Nested
    @DisplayName("getAll()")
    class GetAllTests {

        @Test
        @DisplayName("returns paginated list")
        void getAll_returnsPaginatedList() {
            Pageable pageable = PageRequest.of(0, 10);
            org.springframework.data.domain.Page<Page> page = new PageImpl<>(List.of(testPage), pageable, 1);
            when(repository.findAll(pageable)).thenReturn(page);

            org.springframework.data.domain.Page<PageDto.ListItem> result = service.getAll(pageable);

            assertThat(result.getContent()).hasSize(1);
            assertThat(result.getContent().get(0).getTitle()).isEqualTo("Test Page");
        }
    }

    @Nested
    @DisplayName("getPublicPages()")
    class GetPublicPagesTests {

        @Test
        @DisplayName("returns only public pages")
        void getPublicPages_returnsPublicPages() {
            when(repository.findByVisibilityOrderBySortOrderAsc(Visibility.PUBLIC)).thenReturn(List.of(testPage));

            List<PageDto.ListItem> result = service.getPublicPages();

            assertThat(result).hasSize(1);
            verify(repository).findByVisibilityOrderBySortOrderAsc(Visibility.PUBLIC);
        }

        @Test
        @DisplayName("returns empty list when no public pages")
        void getPublicPages_noPages_returnsEmptyList() {
            when(repository.findByVisibilityOrderBySortOrderAsc(Visibility.PUBLIC)).thenReturn(List.of());

            List<PageDto.ListItem> result = service.getPublicPages();

            assertThat(result).isEmpty();
        }
    }

    @Nested
    @DisplayName("getVisiblePages()")
    class GetVisiblePagesTests {

        @Test
        @DisplayName("returns only PUBLIC pages when user has no internal access")
        void getVisiblePages_noInternalAccess_returnsOnlyPublic() {
            when(repository.findByVisibilityInOrderBySortOrderAsc(Set.of(Visibility.PUBLIC)))
                    .thenReturn(List.of(testPage));

            List<PageDto.ListItem> result = service.getVisiblePages(false);

            assertThat(result).hasSize(1);
            verify(repository).findByVisibilityInOrderBySortOrderAsc(Set.of(Visibility.PUBLIC));
        }

        @Test
        @DisplayName("returns PUBLIC and INTERNAL pages when user has internal access")
        void getVisiblePages_hasInternalAccess_returnsPublicAndInternal() {
            Page internalPage = createTestPage();
            internalPage.setId(2L);
            internalPage.setVisibility(Visibility.INTERNAL);
            internalPage.setSlug("internal-page");

            when(repository.findByVisibilityInOrderBySortOrderAsc(Set.of(Visibility.PUBLIC, Visibility.INTERNAL)))
                    .thenReturn(List.of(testPage, internalPage));

            List<PageDto.ListItem> result = service.getVisiblePages(true);

            assertThat(result).hasSize(2);
            verify(repository).findByVisibilityInOrderBySortOrderAsc(Set.of(Visibility.PUBLIC, Visibility.INTERNAL));
        }
    }

    @Nested
    @DisplayName("getMenuPages()")
    class GetMenuPagesTests {

        @Test
        @DisplayName("returns only PUBLIC menu pages when user has no internal access")
        void getMenuPages_noInternalAccess_returnsOnlyPublicMenuPages() {
            when(repository.findByShowInMenuTrueAndVisibilityInOrderBySortOrderAsc(Set.of(Visibility.PUBLIC)))
                    .thenReturn(List.of(testPage));

            List<PageDto.ListItem> result = service.getMenuPages(false);

            assertThat(result).hasSize(1);
            verify(repository).findByShowInMenuTrueAndVisibilityInOrderBySortOrderAsc(Set.of(Visibility.PUBLIC));
        }

        @Test
        @DisplayName("returns PUBLIC and INTERNAL menu pages when user has internal access")
        void getMenuPages_hasInternalAccess_returnsPublicAndInternalMenuPages() {
            Page internalPage = createTestPage();
            internalPage.setId(2L);
            internalPage.setVisibility(Visibility.INTERNAL);
            internalPage.setSlug("internal-menu-page");

            when(repository.findByShowInMenuTrueAndVisibilityInOrderBySortOrderAsc(Set.of(Visibility.PUBLIC, Visibility.INTERNAL)))
                    .thenReturn(List.of(testPage, internalPage));

            List<PageDto.ListItem> result = service.getMenuPages(true);

            assertThat(result).hasSize(2);
            verify(repository).findByShowInMenuTrueAndVisibilityInOrderBySortOrderAsc(Set.of(Visibility.PUBLIC, Visibility.INTERNAL));
        }
    }

    @Nested
    @DisplayName("getBySlugWithAccessCheck()")
    class GetBySlugWithAccessCheckTests {

        @Test
        @DisplayName("returns PUBLIC page for anonymous user")
        void getBySlugWithAccessCheck_publicPage_noAccess_returnsPage() {
            testPage.setVisibility(Visibility.PUBLIC);
            when(repository.findBySlug("test-page")).thenReturn(Optional.of(testPage));

            PageDto.Response result = service.getBySlugWithAccessCheck("test-page", false);

            assertThat(result.getSlug()).isEqualTo("test-page");
        }

        @Test
        @DisplayName("throws exception for INTERNAL page when user has no internal access")
        void getBySlugWithAccessCheck_internalPage_noAccess_throwsException() {
            testPage.setVisibility(Visibility.INTERNAL);
            when(repository.findBySlug("test-page")).thenReturn(Optional.of(testPage));

            assertThatThrownBy(() -> service.getBySlugWithAccessCheck("test-page", false))
                    .isInstanceOf(EntityNotFoundException.class);
        }

        @Test
        @DisplayName("returns INTERNAL page when user has internal access")
        void getBySlugWithAccessCheck_internalPage_hasAccess_returnsPage() {
            testPage.setVisibility(Visibility.INTERNAL);
            when(repository.findBySlug("test-page")).thenReturn(Optional.of(testPage));

            PageDto.Response result = service.getBySlugWithAccessCheck("test-page", true);

            assertThat(result.getSlug()).isEqualTo("test-page");
        }

        @Test
        @DisplayName("throws exception when page not found")
        void getBySlugWithAccessCheck_notFound_throwsException() {
            when(repository.findBySlug("nonexistent")).thenReturn(Optional.empty());

            assertThatThrownBy(() -> service.getBySlugWithAccessCheck("nonexistent", true))
                    .isInstanceOf(EntityNotFoundException.class);
        }
    }

    @Nested
    @DisplayName("update()")
    class UpdateTests {

        @Test
        @DisplayName("updates only provided fields")
        void update_partialUpdate_onlyChangesProvidedFields() {
            when(repository.findById(1L)).thenReturn(Optional.of(testPage));
            when(repository.save(any(Page.class))).thenAnswer(i -> i.getArgument(0));

            PageDto.Update dto = new PageDto.Update();
            dto.setTitle("Updated Title");
            // other fields null - should not change

            PageDto.Response response = service.update(1L, dto);

            assertThat(response.getTitle()).isEqualTo("Updated Title");
            assertThat(response.getContent()).isEqualTo("Test content"); // unchanged
        }

        @Test
        @DisplayName("allows updating slug to same value")
        void update_sameSlug_noError() {
            when(repository.findById(1L)).thenReturn(Optional.of(testPage));
            when(repository.save(any(Page.class))).thenAnswer(i -> i.getArgument(0));

            PageDto.Update dto = new PageDto.Update();
            dto.setSlug("test-page"); // same as existing

            PageDto.Response response = service.update(1L, dto);

            assertThat(response.getSlug()).isEqualTo("test-page");
            verify(repository, never()).existsBySlug(any());
        }

        @Test
        @DisplayName("throws exception when changing to existing slug")
        void update_toExistingSlug_throwsException() {
            when(repository.findById(1L)).thenReturn(Optional.of(testPage));
            when(repository.existsBySlug("taken-slug")).thenReturn(true);

            PageDto.Update dto = new PageDto.Update();
            dto.setSlug("taken-slug");

            assertThatThrownBy(() -> service.update(1L, dto))
                    .isInstanceOf(IllegalArgumentException.class)
                    .hasMessageContaining("Slug already exists");
        }

        @Test
        @DisplayName("updates sortOrder")
        void update_sortOrder_success() {
            when(repository.findById(1L)).thenReturn(Optional.of(testPage));
            when(repository.save(any(Page.class))).thenAnswer(i -> i.getArgument(0));

            PageDto.Update dto = new PageDto.Update();
            dto.setSortOrder(99);

            PageDto.Response response = service.update(1L, dto);

            assertThat(response.getSortOrder()).isEqualTo(99);
        }

        @Test
        @DisplayName("updates showInMenu")
        void update_showInMenu_success() {
            when(repository.findById(1L)).thenReturn(Optional.of(testPage));
            when(repository.save(any(Page.class))).thenAnswer(i -> i.getArgument(0));

            PageDto.Update dto = new PageDto.Update();
            dto.setShowInMenu(false);

            PageDto.Response response = service.update(1L, dto);

            assertThat(response.getShowInMenu()).isFalse();
        }

        @Test
        @DisplayName("updates parentId")
        void update_parentId_success() {
            Page parentPage = new Page();
            parentPage.setId(5L);
            parentPage.setTitle("Parent");
            parentPage.setSlug("parent");
            parentPage.setContent("Parent content");

            when(repository.findById(1L)).thenReturn(Optional.of(testPage));
            when(repository.findById(5L)).thenReturn(Optional.of(parentPage));
            when(repository.save(any(Page.class))).thenAnswer(i -> i.getArgument(0));

            PageDto.Update dto = new PageDto.Update();
            dto.setParentId(5L);

            PageDto.Response response = service.update(1L, dto);

            assertThat(response.getParentId()).isEqualTo(5L);
        }

        @Test
        @DisplayName("throws exception when not found")
        void update_notFound_throwsException() {
            when(repository.findById(999L)).thenReturn(Optional.empty());

            PageDto.Update dto = new PageDto.Update();
            dto.setTitle("Updated");

            assertThatThrownBy(() -> service.update(999L, dto))
                    .isInstanceOf(EntityNotFoundException.class);
        }
    }

    @Nested
    @DisplayName("delete()")
    class DeleteTests {

        @Test
        @DisplayName("deletes page when exists")
        void delete_exists_deletesPage() {
            when(repository.existsById(1L)).thenReturn(true);

            service.delete(1L);

            verify(repository).deleteById(1L);
        }

        @Test
        @DisplayName("throws exception when not exists")
        void delete_notExists_throwsException() {
            when(repository.existsById(999L)).thenReturn(false);

            assertThatThrownBy(() -> service.delete(999L))
                    .isInstanceOf(EntityNotFoundException.class);
        }
    }

    @Nested
    @DisplayName("addImage()")
    class AddImageTests {

        @Test
        @DisplayName("adds image to page")
        void addImage_addsImageId() {
            when(repository.findById(1L)).thenReturn(Optional.of(testPage));
            when(repository.save(any(Page.class))).thenAnswer(i -> i.getArgument(0));

            service.addImage(1L, "image-456");

            ArgumentCaptor<Page> captor = ArgumentCaptor.forClass(Page.class);
            verify(repository).save(captor.capture());
            assertThat(captor.getValue().getImages()).contains("image-456");
        }

        @Test
        @DisplayName("throws exception when page not found")
        void addImage_notFound_throwsException() {
            when(repository.findById(999L)).thenReturn(Optional.empty());

            assertThatThrownBy(() -> service.addImage(999L, "image-456"))
                    .isInstanceOf(EntityNotFoundException.class);
        }
    }
}
