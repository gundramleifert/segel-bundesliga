package de.segelbundesliga.repository;

import de.segelbundesliga.domain.Schedule;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.Instant;
import java.util.List;
import java.util.Optional;

@Repository
public interface ScheduleRepository extends JpaRepository<Schedule, Long> {
    Optional<Schedule> findByConfigHash(String configHash);

    @Query("SELECT s FROM Schedule s WHERE s.createdAt < :cutoffDate AND SIZE(s.tournaments) = 0")
    List<Schedule> findOrphanedSchedules(@Param("cutoffDate") Instant cutoffDate);
}
