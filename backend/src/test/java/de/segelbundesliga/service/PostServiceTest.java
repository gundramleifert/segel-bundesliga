package de.segelbundesliga.service;

import de.segelbundesliga.domain.Post;
import de.segelbundesliga.domain.Post.PostStatus;
import de.segelbundesliga.domain.Post.Visibility;
import de.segelbundesliga.dto.PostDto;
import de.segelbundesliga.repository.PostRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
@DisplayName("PostService Tests")
class PostServiceTest {

    @Mock
    private PostRepository repository;

    @InjectMocks
    private PostService service;

    private Post testPost;

    @BeforeEach
    void setUp() {
        testPost = createTestPost();
    }

    private Post createTestPost() {
        Post post = new Post();
        post.setId(1L);
        post.setTitle("Test Post");
        post.setTitleEn("Test Post EN");
        post.setSlug("test-post");
        post.setContent("Test content");
        post.setContentEn("Test content EN");
        post.setExcerpt("Short excerpt");
        post.setStatus(PostStatus.DRAFT);
        post.setVisibility(Visibility.PUBLIC);
        post.setTags(new ArrayList<>(List.of("tag1", "tag2")));
        post.setImages(new ArrayList<>());
        post.setCreatedAt(Instant.now());
        post.setUpdatedAt(Instant.now());
        return post;
    }

    @Nested
    @DisplayName("create()")
    class CreateTests {

        @Test
        @DisplayName("creates post with all fields")
        void create_allFields_success() {
            PostDto.Create dto = new PostDto.Create();
            dto.setTitle("New Post");
            dto.setTitleEn("New Post EN");
            dto.setSlug("new-post");
            dto.setContent("Content");
            dto.setContentEn("Content EN");
            dto.setExcerpt("Excerpt");
            dto.setVisibility(Visibility.PUBLIC);
            dto.setTags(List.of("tag1"));

            when(repository.existsBySlug("new-post")).thenReturn(false);
            when(repository.save(any(Post.class))).thenAnswer(invocation -> {
                Post p = invocation.getArgument(0);
                p.setId(1L);
                p.setCreatedAt(Instant.now());
                return p;
            });

            PostDto.Response response = service.create(dto);

            assertThat(response.getTitle()).isEqualTo("New Post");
            assertThat(response.getSlug()).isEqualTo("new-post");
            assertThat(response.getStatus()).isEqualTo(PostStatus.DRAFT);
            assertThat(response.getTags()).containsExactly("tag1");
        }

        @Test
        @DisplayName("throws exception for duplicate slug")
        void create_duplicateSlug_throwsException() {
            PostDto.Create dto = new PostDto.Create();
            dto.setTitle("Post");
            dto.setSlug("existing-slug");
            dto.setContent("Content");

            when(repository.existsBySlug("existing-slug")).thenReturn(true);

            assertThatThrownBy(() -> service.create(dto))
                    .isInstanceOf(IllegalArgumentException.class)
                    .hasMessageContaining("Slug already exists");
        }

        @Test
        @DisplayName("creates post without tags")
        void create_noTags_success() {
            PostDto.Create dto = new PostDto.Create();
            dto.setTitle("Post");
            dto.setSlug("post-no-tags");
            dto.setContent("Content");
            dto.setTags(null);

            when(repository.existsBySlug("post-no-tags")).thenReturn(false);
            when(repository.save(any(Post.class))).thenAnswer(invocation -> {
                Post p = invocation.getArgument(0);
                p.setId(1L);
                return p;
            });

            PostDto.Response response = service.create(dto);

            assertThat(response.getTags()).isEmpty();
        }
    }

    @Nested
    @DisplayName("getById()")
    class GetByIdTests {

        @Test
        @DisplayName("returns post when found")
        void getById_found_returnsPost() {
            when(repository.findById(1L)).thenReturn(Optional.of(testPost));

            PostDto.Response response = service.getById(1L);

            assertThat(response.getId()).isEqualTo(1L);
            assertThat(response.getTitle()).isEqualTo("Test Post");
        }

        @Test
        @DisplayName("throws EntityNotFoundException when not found")
        void getById_notFound_throwsException() {
            when(repository.findById(999L)).thenReturn(Optional.empty());

            assertThatThrownBy(() -> service.getById(999L))
                    .isInstanceOf(EntityNotFoundException.class)
                    .hasMessageContaining("Post");
        }
    }

    @Nested
    @DisplayName("getBySlug()")
    class GetBySlugTests {

        @Test
        @DisplayName("returns post when found")
        void getBySlug_found_returnsPost() {
            when(repository.findBySlug("test-post")).thenReturn(Optional.of(testPost));

            PostDto.Response response = service.getBySlug("test-post");

            assertThat(response.getSlug()).isEqualTo("test-post");
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
    @DisplayName("getPublicPosts()")
    class GetPublicPostsTests {

        @Test
        @DisplayName("returns only public published posts")
        void getPublicPosts_returnsPublicPosts() {
            Pageable pageable = PageRequest.of(0, 10);
            testPost.setStatus(PostStatus.PUBLISHED);
            Page<Post> page = new PageImpl<>(List.of(testPost), pageable, 1);
            when(repository.findPublicPosts(pageable)).thenReturn(page);

            Page<PostDto.ListItem> result = service.getPublicPosts(pageable);

            assertThat(result.getContent()).hasSize(1);
            verify(repository).findPublicPosts(pageable);
        }
    }

    @Nested
    @DisplayName("update()")
    class UpdateTests {

        @Test
        @DisplayName("updates only provided fields")
        void update_partialUpdate_onlyChangesProvidedFields() {
            when(repository.findById(1L)).thenReturn(Optional.of(testPost));
            when(repository.save(any(Post.class))).thenAnswer(i -> i.getArgument(0));

            PostDto.Update dto = new PostDto.Update();
            dto.setTitle("Updated Title");
            // other fields null - should not change

            PostDto.Response response = service.update(1L, dto);

            assertThat(response.getTitle()).isEqualTo("Updated Title");
            assertThat(response.getContent()).isEqualTo("Test content"); // unchanged
        }

        @Test
        @DisplayName("allows updating slug to same value")
        void update_sameSlug_noError() {
            when(repository.findById(1L)).thenReturn(Optional.of(testPost));
            when(repository.save(any(Post.class))).thenAnswer(i -> i.getArgument(0));

            PostDto.Update dto = new PostDto.Update();
            dto.setSlug("test-post"); // same as existing

            PostDto.Response response = service.update(1L, dto);

            assertThat(response.getSlug()).isEqualTo("test-post");
            verify(repository, never()).existsBySlug(any());
        }

        @Test
        @DisplayName("throws exception when changing to existing slug")
        void update_toExistingSlug_throwsException() {
            when(repository.findById(1L)).thenReturn(Optional.of(testPost));
            when(repository.existsBySlug("taken-slug")).thenReturn(true);

            PostDto.Update dto = new PostDto.Update();
            dto.setSlug("taken-slug");

            assertThatThrownBy(() -> service.update(1L, dto))
                    .isInstanceOf(IllegalArgumentException.class)
                    .hasMessageContaining("Slug already exists");
        }

        @Test
        @DisplayName("sets publishedAt when first time PUBLISHED")
        void update_toPublished_setsPublishedAt() {
            testPost.setPublishedAt(null);
            when(repository.findById(1L)).thenReturn(Optional.of(testPost));
            when(repository.save(any(Post.class))).thenAnswer(i -> i.getArgument(0));

            PostDto.Update dto = new PostDto.Update();
            dto.setStatus(PostStatus.PUBLISHED);

            PostDto.Response response = service.update(1L, dto);

            assertThat(response.getStatus()).isEqualTo(PostStatus.PUBLISHED);
            assertThat(response.getPublishedAt()).isNotNull();
        }

        @Test
        @DisplayName("does not change publishedAt if already published")
        void update_alreadyPublished_publishedAtUnchanged() {
            Instant originalPublishedAt = Instant.parse("2025-01-01T00:00:00Z");
            testPost.setPublishedAt(originalPublishedAt);
            testPost.setStatus(PostStatus.PUBLISHED);
            when(repository.findById(1L)).thenReturn(Optional.of(testPost));
            when(repository.save(any(Post.class))).thenAnswer(i -> i.getArgument(0));

            PostDto.Update dto = new PostDto.Update();
            dto.setStatus(PostStatus.PUBLISHED); // re-publishing

            PostDto.Response response = service.update(1L, dto);

            assertThat(response.getPublishedAt()).isEqualTo(originalPublishedAt);
        }

        @Test
        @DisplayName("replaces tags when provided")
        void update_withTags_replacesTags() {
            when(repository.findById(1L)).thenReturn(Optional.of(testPost));
            when(repository.save(any(Post.class))).thenAnswer(i -> i.getArgument(0));

            PostDto.Update dto = new PostDto.Update();
            dto.setTags(List.of("newTag1", "newTag2"));

            PostDto.Response response = service.update(1L, dto);

            assertThat(response.getTags()).containsExactly("newTag1", "newTag2");
        }
    }

    @Nested
    @DisplayName("publish()")
    class PublishTests {

        @Test
        @DisplayName("sets status to PUBLISHED")
        void publish_setsStatusToPublished() {
            testPost.setStatus(PostStatus.DRAFT);
            when(repository.findById(1L)).thenReturn(Optional.of(testPost));
            when(repository.save(any(Post.class))).thenAnswer(i -> i.getArgument(0));

            PostDto.Response response = service.publish(1L);

            assertThat(response.getStatus()).isEqualTo(PostStatus.PUBLISHED);
        }

        @Test
        @DisplayName("sets publishedAt on first publish")
        void publish_firstTime_setsPublishedAt() {
            testPost.setPublishedAt(null);
            when(repository.findById(1L)).thenReturn(Optional.of(testPost));
            when(repository.save(any(Post.class))).thenAnswer(i -> i.getArgument(0));

            PostDto.Response response = service.publish(1L);

            assertThat(response.getPublishedAt()).isNotNull();
        }

        @Test
        @DisplayName("does not change publishedAt on re-publish")
        void publish_alreadyPublished_publishedAtUnchanged() {
            Instant original = Instant.parse("2025-01-01T00:00:00Z");
            testPost.setPublishedAt(original);
            when(repository.findById(1L)).thenReturn(Optional.of(testPost));
            when(repository.save(any(Post.class))).thenAnswer(i -> i.getArgument(0));

            PostDto.Response response = service.publish(1L);

            assertThat(response.getPublishedAt()).isEqualTo(original);
        }

        @Test
        @DisplayName("throws exception when post not found")
        void publish_notFound_throwsException() {
            when(repository.findById(999L)).thenReturn(Optional.empty());

            assertThatThrownBy(() -> service.publish(999L))
                    .isInstanceOf(EntityNotFoundException.class);
        }
    }

    @Nested
    @DisplayName("delete()")
    class DeleteTests {

        @Test
        @DisplayName("deletes post when exists")
        void delete_exists_deletesPost() {
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
        @DisplayName("adds image to post")
        void addImage_addsImageId() {
            when(repository.findById(1L)).thenReturn(Optional.of(testPost));
            when(repository.save(any(Post.class))).thenAnswer(i -> i.getArgument(0));

            service.addImage(1L, "image-123");

            ArgumentCaptor<Post> captor = ArgumentCaptor.forClass(Post.class);
            verify(repository).save(captor.capture());
            assertThat(captor.getValue().getImages()).contains("image-123");
        }

        @Test
        @DisplayName("throws exception when post not found")
        void addImage_notFound_throwsException() {
            when(repository.findById(999L)).thenReturn(Optional.empty());

            assertThatThrownBy(() -> service.addImage(999L, "image-123"))
                    .isInstanceOf(EntityNotFoundException.class);
        }
    }
}
