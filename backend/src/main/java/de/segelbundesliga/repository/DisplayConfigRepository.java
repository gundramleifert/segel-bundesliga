package de.segelbundesliga.repository;

import de.segelbundesliga.domain.DisplayConfig;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface DisplayConfigRepository extends JpaRepository<DisplayConfig, Long> {
    List<DisplayConfig> findBySystemDefaultTrue();
}
