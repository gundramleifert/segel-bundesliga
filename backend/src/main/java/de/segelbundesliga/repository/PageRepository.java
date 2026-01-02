package de.segelbundesliga.repository;

import de.segelbundesliga.domain.Page;
import de.segelbundesliga.domain.Page.Visibility;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Collection;
import java.util.List;
import java.util.Optional;

@Repository
public interface PageRepository extends JpaRepository<Page, Long> {

    Optional<Page> findBySlug(String slug);

    List<Page> findByVisibility(Visibility visibility);

    List<Page> findByVisibilityOrderBySortOrderAsc(Visibility visibility);

    List<Page> findByVisibilityInOrderBySortOrderAsc(Collection<Visibility> visibilities);

    List<Page> findByShowInMenuTrueOrderBySortOrderAsc();

    List<Page> findByShowInMenuTrueAndVisibilityOrderBySortOrderAsc(Visibility visibility);

    List<Page> findByShowInMenuTrueAndVisibilityInOrderBySortOrderAsc(Collection<Visibility> visibilities);

    List<Page> findByParentIdOrderBySortOrderAsc(Long parentId);

    boolean existsBySlug(String slug);
}
