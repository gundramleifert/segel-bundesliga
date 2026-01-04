package de.segelbundesliga.config;

import de.segelbundesliga.domain.DisplayConfig;
import de.segelbundesliga.domain.FontFamily;
import de.segelbundesliga.domain.OptimizationConfig;
import de.segelbundesliga.domain.PageOrientation;
import de.segelbundesliga.repository.DisplayConfigRepository;
import de.segelbundesliga.repository.OptimizationConfigRepository;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;

/**
 * Initializes default optimization and display configs on application startup.
 */
@Component
@Order(101)
@RequiredArgsConstructor
public class ConfigDataInitializer implements ApplicationRunner {

    private static final Logger log = LoggerFactory.getLogger(ConfigDataInitializer.class);

    private final OptimizationConfigRepository optimizationConfigRepository;
    private final DisplayConfigRepository displayConfigRepository;

    @Override
    public void run(ApplicationArguments args) {
        log.info("Checking for default optimization and display configs...");

        int createdOpt = createOptimizationConfigs();
        int createdDisp = createDisplayConfigs();

        if (createdOpt > 0 || createdDisp > 0) {
            log.info("Created {} optimization configs and {} display configs", createdOpt, createdDisp);
        } else {
            log.info("All default configs already exist");
        }
    }

    private int createOptimizationConfigs() {
        int created = 0;

        if (optimizationConfigRepository.count() == 0) {
            // Minimal config - ID will be 1 (for E2E tests, 10x faster than Fast)
            OptimizationConfig minimal = new OptimizationConfig();
            minimal.setName("Minimal");
            minimal.setDescription("Fast optimization for E2E testing (100 iterations)");
            minimal.setSystemDefault(true);
            minimal.setMmLoops(100);
            minimal.setBsLoops(100);
            optimizationConfigRepository.save(minimal);
            created++;

            // Fast config - ID will be 2
            OptimizationConfig fast = new OptimizationConfig();
            fast.setName("Fast");
            fast.setDescription("Quick optimization for testing (1000 iterations)");
            fast.setSystemDefault(true);
            fast.setMmLoops(1000);
            fast.setBsLoops(1000);
            optimizationConfigRepository.save(fast);
            created++;

            // Balanced config - ID will be 3
            OptimizationConfig balanced = new OptimizationConfig();
            balanced.setName("Balanced");
            balanced.setDescription("Default balanced optimization (10000 iterations)");
            balanced.setSystemDefault(true);
            balanced.setMmLoops(10000);
            balanced.setBsLoops(10000);
            optimizationConfigRepository.save(balanced);
            created++;

            // Thorough config - ID will be 4
            OptimizationConfig thorough = new OptimizationConfig();
            thorough.setName("Thorough");
            thorough.setDescription("High-quality optimization (50000 iterations)");
            thorough.setSystemDefault(true);
            thorough.setMmLoops(50000);
            thorough.setBsLoops(50000);
            thorough.setMmIndividuals(200);
            thorough.setBsIndividuals(200);
            optimizationConfigRepository.save(thorough);
            created++;

            log.info("Created {} optimization configs", created);
        }

        return created;
    }

    private int createDisplayConfigs() {
        int created = 0;

        if (displayConfigRepository.count() == 0) {
            // Example config - ID will be 1 (simple config for testing)
            DisplayConfig example = new DisplayConfig();
            example.setName("Example");
            example.setDescription("Basic configuration for E2E testing");
            example.setSystemDefault(true);
            example.setFontFamily(FontFamily.HELVETICA);
            example.setFontSize(10);
            example.setOrientation(PageOrientation.PORTRAIT);
            displayConfigRepository.save(example);
            created++;

            // Compact config - ID will be 2
            DisplayConfig compact = new DisplayConfig();
            compact.setName("Compact");
            compact.setDescription("Small font, portrait orientation - fits more on page");
            compact.setSystemDefault(true);
            compact.setFontFamily(FontFamily.HELVETICA);
            compact.setFontSize(9);
            compact.setOrientation(PageOrientation.PORTRAIT);
            displayConfigRepository.save(compact);
            created++;

            // Standard config - ID will be 3
            DisplayConfig standard = new DisplayConfig();
            standard.setName("Standard");
            standard.setDescription("Balanced layout with readable font size");
            standard.setSystemDefault(true);
            standard.setFontFamily(FontFamily.HELVETICA);
            standard.setFontSize(10);
            standard.setOrientation(PageOrientation.LANDSCAPE);
            displayConfigRepository.save(standard);
            created++;

            // Large config - ID will be 4
            DisplayConfig large = new DisplayConfig();
            large.setName("Large");
            large.setDescription("Large font for better readability");
            large.setSystemDefault(true);
            large.setFontFamily(FontFamily.ARIAL);
            large.setFontSize(12);
            large.setOrientation(PageOrientation.LANDSCAPE);
            displayConfigRepository.save(large);
            created++;

            log.info("Created {} display configs", created);
        }

        return created;
    }
}
