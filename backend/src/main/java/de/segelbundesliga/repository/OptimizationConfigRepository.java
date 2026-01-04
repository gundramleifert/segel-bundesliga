package de.segelbundesliga.repository;

import de.segelbundesliga.domain.OptimizationConfig;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface OptimizationConfigRepository extends JpaRepository<OptimizationConfig, Long> {
    List<OptimizationConfig> findBySystemDefaultTrue();
}
