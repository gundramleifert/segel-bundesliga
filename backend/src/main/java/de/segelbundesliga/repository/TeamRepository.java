package de.segelbundesliga.repository;

import de.segelbundesliga.domain.Team;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface TeamRepository extends JpaRepository<Team, Long> {
    List<Team> findByTournamentIdOrderBySortOrderAsc(Long tournamentId);
}
