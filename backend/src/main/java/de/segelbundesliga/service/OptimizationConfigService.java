package de.segelbundesliga.service;

import de.segelbundesliga.domain.OptimizationConfig;
import de.segelbundesliga.dto.OptimizationConfigDto;
import de.segelbundesliga.repository.OptimizationConfigRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
public class OptimizationConfigService {

    @Autowired
    private OptimizationConfigRepository repository;

    public List<OptimizationConfig> getAllConfigs() {
        return repository.findAll();
    }

    public OptimizationConfig getById(Long id) {
        return repository.findById(id)
            .orElseThrow(() -> new IllegalArgumentException("OptimizationConfig not found: " + id));
    }

    @Transactional
    public OptimizationConfig create(OptimizationConfigDto.Create dto) {
        OptimizationConfig config = new OptimizationConfig();
        config.setName(dto.getName());
        config.setDescription(dto.getDescription());
        config.setSystemDefault(false);

        // Match Matrix settings
        config.setSeed(dto.getSeed());
        config.setMmSwapTeams(dto.getMmSwapTeams());
        config.setMmMaxBranches(dto.getMmMaxBranches());
        config.setMmFactorLessParticipants(dto.getMmFactorLessParticipants());
        config.setMmFactorTeamMissing(dto.getMmFactorTeamMissing());
        config.setMmLoops(dto.getMmLoops());
        config.setMmIndividuals(dto.getMmIndividuals());
        config.setMmEarlyStopping(dto.getMmEarlyStopping());
        config.setMmShowEveryN(dto.getMmShowEveryN());

        // Boat Schedule settings
        config.setBsSwapBoats(dto.getBsSwapBoats());
        config.setBsSwapRaces(dto.getBsSwapRaces());
        config.setBsWeightStayOnBoat(dto.getBsWeightStayOnBoat());
        config.setBsWeightStayOnShuttle(dto.getBsWeightStayOnShuttle());
        config.setBsWeightChangeBetweenBoats(dto.getBsWeightChangeBetweenBoats());
        config.setBsLoops(dto.getBsLoops());
        config.setBsIndividuals(dto.getBsIndividuals());
        config.setBsEarlyStopping(dto.getBsEarlyStopping());
        config.setBsShowEveryN(dto.getBsShowEveryN());

        return repository.save(config);
    }

    @Transactional
    public OptimizationConfig update(Long id, OptimizationConfigDto.Update dto) {
        OptimizationConfig config = getById(id);
        if (config.isSystemDefault()) {
            throw new IllegalStateException("Cannot modify system default configs");
        }

        if (dto.getName() != null) config.setName(dto.getName());
        if (dto.getDescription() != null) config.setDescription(dto.getDescription());

        if (dto.getSeed() != null) config.setSeed(dto.getSeed());
        if (dto.getMmSwapTeams() != null) config.setMmSwapTeams(dto.getMmSwapTeams());
        if (dto.getMmMaxBranches() != null) config.setMmMaxBranches(dto.getMmMaxBranches());
        if (dto.getMmFactorLessParticipants() != null) config.setMmFactorLessParticipants(dto.getMmFactorLessParticipants());
        if (dto.getMmFactorTeamMissing() != null) config.setMmFactorTeamMissing(dto.getMmFactorTeamMissing());
        if (dto.getMmLoops() != null) config.setMmLoops(dto.getMmLoops());
        if (dto.getMmIndividuals() != null) config.setMmIndividuals(dto.getMmIndividuals());
        if (dto.getMmEarlyStopping() != null) config.setMmEarlyStopping(dto.getMmEarlyStopping());
        if (dto.getMmShowEveryN() != null) config.setMmShowEveryN(dto.getMmShowEveryN());

        if (dto.getBsSwapBoats() != null) config.setBsSwapBoats(dto.getBsSwapBoats());
        if (dto.getBsSwapRaces() != null) config.setBsSwapRaces(dto.getBsSwapRaces());
        if (dto.getBsWeightStayOnBoat() != null) config.setBsWeightStayOnBoat(dto.getBsWeightStayOnBoat());
        if (dto.getBsWeightStayOnShuttle() != null) config.setBsWeightStayOnShuttle(dto.getBsWeightStayOnShuttle());
        if (dto.getBsWeightChangeBetweenBoats() != null) config.setBsWeightChangeBetweenBoats(dto.getBsWeightChangeBetweenBoats());
        if (dto.getBsLoops() != null) config.setBsLoops(dto.getBsLoops());
        if (dto.getBsIndividuals() != null) config.setBsIndividuals(dto.getBsIndividuals());
        if (dto.getBsEarlyStopping() != null) config.setBsEarlyStopping(dto.getBsEarlyStopping());
        if (dto.getBsShowEveryN() != null) config.setBsShowEveryN(dto.getBsShowEveryN());

        return repository.save(config);
    }

    @Transactional
    public void delete(Long id) {
        OptimizationConfig config = getById(id);
        if (config.isSystemDefault()) {
            throw new IllegalStateException("Cannot delete system default configs");
        }
        repository.delete(config);
    }
}
