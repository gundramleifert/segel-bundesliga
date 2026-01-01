package de.segelbundesliga.repository;

import de.segelbundesliga.domain.Post;
import de.segelbundesliga.domain.Post.PostStatus;
import de.segelbundesliga.domain.Post.Visibility;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.stereotype.Repository;

import java.util.Optional;

@Repository
public interface PostRepository extends JpaRepository<Post, Long> {

    Optional<Post> findBySlug(String slug);

    Page<Post> findByStatus(PostStatus status, Pageable pageable);

    Page<Post> findByStatusAndVisibility(PostStatus status, Visibility visibility, Pageable pageable);

    @Query("SELECT p FROM Post p WHERE p.status = 'PUBLISHED' AND p.visibility = 'PUBLIC' ORDER BY p.publishedAt DESC")
    Page<Post> findPublicPosts(Pageable pageable);

    @Query("SELECT p FROM Post p WHERE p.status = 'PUBLISHED' ORDER BY p.publishedAt DESC")
    Page<Post> findAllPublishedPosts(Pageable pageable);

    boolean existsBySlug(String slug);
}
