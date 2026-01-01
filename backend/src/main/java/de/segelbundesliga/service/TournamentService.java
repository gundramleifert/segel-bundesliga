package de.segelbundesliga.service;

import de.segelbundesliga.domain.Boat;
import de.segelbundesliga.domain.OptimizationSettings;
import de.segelbundesliga.domain.Team;
import de.segelbundesliga.domain.Tournament;
import de.segelbundesliga.domain.Tournament.TournamentStatus;
import de.segelbundesliga.dto.TournamentDto;
import de.segelbundesliga.repository.TournamentRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.List;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
@Transactional
public class TournamentService {

    private final TournamentRepository repository;

    public TournamentDto.Response create(TournamentDto.Create dto, String ownerId) {
        Tournament entity = new Tournament();
        entity.setName(dto.getName());
        entity.setDescription(dto.getDescription());
        entity.setEventDate(dto.getEventDate());
        entity.setLocation(dto.getLocation());
        entity.setOwnerId(ownerId);
        entity.setStatus(TournamentStatus.DRAFT);

        if (dto.getFlights() != null) {
            entity.setFlights(dto.getFlights());
        }

        // Add teams
        if (dto.getTeams() != null) {
            int order = 0;
            for (TournamentDto.TeamInput teamInput : dto.getTeams()) {
                Team team = new Team();
                team.setName(teamInput.getName());
                team.setSortOrder(teamInput.getSortOrder() != null ? teamInput.getSortOrder() : order++);
                entity.addTeam(team);
            }
        }

        // Add boats
        if (dto.getBoats() != null) {
            int order = 0;
            for (TournamentDto.BoatInput boatInput : dto.getBoats()) {
                Boat boat = new Boat();
                boat.setName(boatInput.getName());
                boat.setColor(boatInput.getColor());
                boat.setSortOrder(boatInput.getSortOrder() != null ? boatInput.getSortOrder() : order++);
                entity.addBoat(boat);
            }
        }

        // Optimization settings
        if (dto.getOptimizationSettings() != null) {
            applyOptimizationSettings(entity.getOptimizationSettings(), dto.getOptimizationSettings());
        }

        return toResponse(repository.save(entity));
    }

    @Transactional(readOnly = true)
    public TournamentDto.Response getById(Long id) {
        return repository.findById(id)
                .map(this::toResponse)
                .orElseThrow(() -> new EntityNotFoundException("Tournament", id));
    }

    @Transactional(readOnly = true)
    public Page<TournamentDto.ListItem> getAll(Pageable pageable) {
        return repository.findAll(pageable).map(this::toListItem);
    }

    @Transactional(readOnly = true)
    public Page<TournamentDto.ListItem> getByOwner(String ownerId, Pageable pageable) {
        return repository.findByOwnerId(ownerId, pageable).map(this::toListItem);
    }

    public TournamentDto.Response update(Long id, TournamentDto.Update dto) {
        Tournament entity = repository.findById(id)
                .orElseThrow(() -> new EntityNotFoundException("Tournament", id));

        if (dto.getName() != null) entity.setName(dto.getName());
        if (dto.getDescription() != null) entity.setDescription(dto.getDescription());
        if (dto.getEventDate() != null) entity.setEventDate(dto.getEventDate());
        if (dto.getLocation() != null) entity.setLocation(dto.getLocation());
        if (dto.getStatus() != null) entity.setStatus(dto.getStatus());
        if (dto.getFlights() != null) entity.setFlights(dto.getFlights());

        // Update teams (replace all)
        if (dto.getTeams() != null) {
            entity.getTeams().clear();
            int order = 0;
            for (TournamentDto.TeamInput teamInput : dto.getTeams()) {
                Team team = new Team();
                team.setName(teamInput.getName());
                team.setSortOrder(teamInput.getSortOrder() != null ? teamInput.getSortOrder() : order++);
                entity.addTeam(team);
            }
        }

        // Update boats (replace all)
        if (dto.getBoats() != null) {
            entity.getBoats().clear();
            int order = 0;
            for (TournamentDto.BoatInput boatInput : dto.getBoats()) {
                Boat boat = new Boat();
                boat.setName(boatInput.getName());
                boat.setColor(boatInput.getColor());
                boat.setSortOrder(boatInput.getSortOrder() != null ? boatInput.getSortOrder() : order++);
                entity.addBoat(boat);
            }
        }

        // Update optimization settings
        if (dto.getOptimizationSettings() != null) {
            applyOptimizationSettings(entity.getOptimizationSettings(), dto.getOptimizationSettings());
        }

        return toResponse(repository.save(entity));
    }

    public void delete(Long id) {
        if (!repository.existsById(id)) {
            throw new EntityNotFoundException("Tournament", id);
        }
        repository.deleteById(id);
    }

    public boolean isOwner(Long id, String userId) {
        return repository.findById(id)
                .map(t -> t.getOwnerId().equals(userId))
                .orElse(false);
    }

    private void applyOptimizationSettings(OptimizationSettings target, TournamentDto.OptimizationSettingsInput source) {
        if (source.getSeed() != null) target.setSeed(source.getSeed());
        // MatchMatrix
        if (source.getMmSwapTeams() != null) target.setMmSwapTeams(source.getMmSwapTeams());
        if (source.getMmMaxBranches() != null) target.setMmMaxBranches(source.getMmMaxBranches());
        if (source.getMmFactorLessParticipants() != null) target.setMmFactorLessParticipants(source.getMmFactorLessParticipants());
        if (source.getMmFactorTeamMissing() != null) target.setMmFactorTeamMissing(source.getMmFactorTeamMissing());
        if (source.getMmLoops() != null) target.setMmLoops(source.getMmLoops());
        if (source.getMmIndividuals() != null) target.setMmIndividuals(source.getMmIndividuals());
        if (source.getMmEarlyStopping() != null) target.setMmEarlyStopping(source.getMmEarlyStopping());
        if (source.getMmShowEveryN() != null) target.setMmShowEveryN(source.getMmShowEveryN());
        // BoatSchedule
        if (source.getBsSwapBoats() != null) target.setBsSwapBoats(source.getBsSwapBoats());
        if (source.getBsSwapRaces() != null) target.setBsSwapRaces(source.getBsSwapRaces());
        if (source.getBsWeightStayOnBoat() != null) target.setBsWeightStayOnBoat(source.getBsWeightStayOnBoat());
        if (source.getBsWeightStayOnShuttle() != null) target.setBsWeightStayOnShuttle(source.getBsWeightStayOnShuttle());
        if (source.getBsWeightChangeBetweenBoats() != null) target.setBsWeightChangeBetweenBoats(source.getBsWeightChangeBetweenBoats());
        if (source.getBsLoops() != null) target.setBsLoops(source.getBsLoops());
        if (source.getBsIndividuals() != null) target.setBsIndividuals(source.getBsIndividuals());
        if (source.getBsEarlyStopping() != null) target.setBsEarlyStopping(source.getBsEarlyStopping());
        if (source.getBsShowEveryN() != null) target.setBsShowEveryN(source.getBsShowEveryN());
    }

    private TournamentDto.Response toResponse(Tournament entity) {
        TournamentDto.Response dto = new TournamentDto.Response();
        dto.setId(entity.getId());
        dto.setName(entity.getName());
        dto.setDescription(entity.getDescription());
        dto.setEventDate(entity.getEventDate());
        dto.setLocation(entity.getLocation());
        dto.setStatus(entity.getStatus());
        dto.setOwnerId(entity.getOwnerId());
        dto.setFlights(entity.getFlights());

        // Teams
        dto.setTeams(entity.getTeams().stream()
                .map(this::toTeamOutput)
                .collect(Collectors.toList()));

        // Boats
        dto.setBoats(entity.getBoats().stream()
                .map(this::toBoatOutput)
                .collect(Collectors.toList()));

        // Optimization settings
        dto.setOptimizationSettings(toOptimizationSettingsOutput(entity.getOptimizationSettings()));

        dto.setResultSchedule(entity.getResultSchedule());
        dto.setComputationTimeMs(entity.getComputationTimeMs());
        dto.setSavedShuttles(entity.getSavedShuttles());
        dto.setBoatChanges(entity.getBoatChanges());
        dto.setCreatedAt(entity.getCreatedAt());
        dto.setUpdatedAt(entity.getUpdatedAt());
        return dto;
    }

    private TournamentDto.ListItem toListItem(Tournament entity) {
        TournamentDto.ListItem dto = new TournamentDto.ListItem();
        dto.setId(entity.getId());
        dto.setName(entity.getName());
        dto.setEventDate(entity.getEventDate());
        dto.setLocation(entity.getLocation());
        dto.setStatus(entity.getStatus());
        dto.setTeamCount(entity.getTeams().size());
        dto.setBoatCount(entity.getBoats().size());
        dto.setCreatedAt(entity.getCreatedAt());
        return dto;
    }

    private TournamentDto.TeamOutput toTeamOutput(Team team) {
        TournamentDto.TeamOutput dto = new TournamentDto.TeamOutput();
        dto.setId(team.getId());
        dto.setName(team.getName());
        dto.setSortOrder(team.getSortOrder());
        return dto;
    }

    private TournamentDto.BoatOutput toBoatOutput(Boat boat) {
        TournamentDto.BoatOutput dto = new TournamentDto.BoatOutput();
        dto.setId(boat.getId());
        dto.setName(boat.getName());
        dto.setColor(boat.getColor());
        dto.setSortOrder(boat.getSortOrder());
        return dto;
    }

    private TournamentDto.OptimizationSettingsOutput toOptimizationSettingsOutput(OptimizationSettings settings) {
        TournamentDto.OptimizationSettingsOutput dto = new TournamentDto.OptimizationSettingsOutput();
        dto.setSeed(settings.getSeed());
        // MatchMatrix
        dto.setMmSwapTeams(settings.getMmSwapTeams());
        dto.setMmMaxBranches(settings.getMmMaxBranches());
        dto.setMmFactorLessParticipants(settings.getMmFactorLessParticipants());
        dto.setMmFactorTeamMissing(settings.getMmFactorTeamMissing());
        dto.setMmLoops(settings.getMmLoops());
        dto.setMmIndividuals(settings.getMmIndividuals());
        dto.setMmEarlyStopping(settings.getMmEarlyStopping());
        dto.setMmShowEveryN(settings.getMmShowEveryN());
        // BoatSchedule
        dto.setBsSwapBoats(settings.getBsSwapBoats());
        dto.setBsSwapRaces(settings.getBsSwapRaces());
        dto.setBsWeightStayOnBoat(settings.getBsWeightStayOnBoat());
        dto.setBsWeightStayOnShuttle(settings.getBsWeightStayOnShuttle());
        dto.setBsWeightChangeBetweenBoats(settings.getBsWeightChangeBetweenBoats());
        dto.setBsLoops(settings.getBsLoops());
        dto.setBsIndividuals(settings.getBsIndividuals());
        dto.setBsEarlyStopping(settings.getBsEarlyStopping());
        dto.setBsShowEveryN(settings.getBsShowEveryN());
        return dto;
    }
}
