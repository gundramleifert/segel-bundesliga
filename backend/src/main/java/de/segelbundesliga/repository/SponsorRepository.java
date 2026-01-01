package de.segelbundesliga.repository;

import de.segelbundesliga.domain.Sponsor;
import de.segelbundesliga.domain.Sponsor.SponsorTier;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface SponsorRepository extends JpaRepository<Sponsor, Long> {

    List<Sponsor> findByActiveTrue();

    List<Sponsor> findByActiveTrueOrderBySortOrderAsc();

    List<Sponsor> findByTierAndActiveTrue(SponsorTier tier);

    @Query("SELECT s FROM Sponsor s WHERE s.active = true ORDER BY s.tier ASC, s.sortOrder ASC")
    List<Sponsor> findAllActiveOrderedByTier();
}
