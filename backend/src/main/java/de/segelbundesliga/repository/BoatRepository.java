package de.segelbundesliga.repository;

import de.segelbundesliga.domain.Boat;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface BoatRepository extends JpaRepository<Boat, Long> {
    List<Boat> findByTournamentIdOrderBySortOrderAsc(Long tournamentId);
}
