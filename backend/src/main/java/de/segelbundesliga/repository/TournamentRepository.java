package de.segelbundesliga.repository;

import de.segelbundesliga.domain.Tournament;
import de.segelbundesliga.domain.Tournament.TournamentStatus;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface TournamentRepository extends JpaRepository<Tournament, Long> {

    @EntityGraph(attributePaths = {"teams", "boats"})
    Page<Tournament> findByOwnerId(String ownerId, Pageable pageable);

    List<Tournament> findByOwnerIdAndStatus(String ownerId, TournamentStatus status);

    Page<Tournament> findByStatus(TournamentStatus status, Pageable pageable);

    @Override
    @EntityGraph(attributePaths = {"teams", "boats"})
    Optional<Tournament> findById(Long id);

    @Override
    @EntityGraph(attributePaths = {"teams", "boats"})
    Page<Tournament> findAll(Pageable pageable);
}
