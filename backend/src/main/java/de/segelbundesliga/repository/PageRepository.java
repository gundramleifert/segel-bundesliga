package de.segelbundesliga.repository;

import de.segelbundesliga.domain.Page;
import de.segelbundesliga.domain.Page.Visibility;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface PageRepository extends JpaRepository<Page, Long> {

    Optional<Page> findBySlug(String slug);

    List<Page> findByVisibility(Visibility visibility);

    @Query("SELECT p FROM Page p WHERE p.visibility = 'PUBLIC' ORDER BY p.sortOrder ASC")
    List<Page> findPublicPages();

    @Query("SELECT p FROM Page p WHERE p.showInMenu = true ORDER BY p.sortOrder ASC")
    List<Page> findMenuPages();

    @Query("SELECT p FROM Page p WHERE p.showInMenu = true AND p.visibility = 'PUBLIC' ORDER BY p.sortOrder ASC")
    List<Page> findPublicMenuPages();

    List<Page> findByParentIdOrderBySortOrderAsc(Long parentId);

    boolean existsBySlug(String slug);
}
