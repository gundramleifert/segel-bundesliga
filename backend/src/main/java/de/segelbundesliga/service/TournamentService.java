package de.segelbundesliga.service;

import de.segelbundesliga.domain.Boat;
import de.segelbundesliga.domain.Team;
import de.segelbundesliga.domain.Tournament;
import de.segelbundesliga.domain.Tournament.TournamentStatus;
import de.segelbundesliga.dto.DisplayConfigDto;
import de.segelbundesliga.dto.OptimizationConfigDto;
import de.segelbundesliga.dto.TournamentDto;
import de.segelbundesliga.repository.TournamentRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
@Transactional
public class TournamentService {

    private final TournamentRepository repository;
    private final OptimizationConfigService optimizationConfigService;
    private final DisplayConfigService displayConfigService;

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

        // Set optimization config (optional - can be set later)
        if (dto.getOptimizationConfigId() != null) {
            entity.setOptimizationConfig(optimizationConfigService.getById(dto.getOptimizationConfigId()));
        }

        // Set display config (optional)
        if (dto.getDisplayConfigId() != null) {
            entity.setDisplayConfig(displayConfigService.getById(dto.getDisplayConfigId()));
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

        // Update optimization config
        if (dto.getOptimizationConfigId() != null) {
            entity.setOptimizationConfig(optimizationConfigService.getById(dto.getOptimizationConfigId()));
        }

        // Update display config
        if (dto.getDisplayConfigId() != null) {
            entity.setDisplayConfig(displayConfigService.getById(dto.getDisplayConfigId()));
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

        // Optimization config (can be null)
        if (entity.getOptimizationConfig() != null) {
            dto.setOptimizationConfig(OptimizationConfigDto.Response.from(entity.getOptimizationConfig()));
        }

        // Display config (can be null)
        if (entity.getDisplayConfig() != null) {
            dto.setDisplayConfig(DisplayConfigDto.Response.from(entity.getDisplayConfig()));
        }

        // Schedule (can be null)
        if (entity.getSchedule() != null) {
            dto.setSchedule(toScheduleOutput(entity.getSchedule()));
        }

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

    private TournamentDto.ScheduleOutput toScheduleOutput(de.segelbundesliga.domain.Schedule schedule) {
        TournamentDto.ScheduleOutput dto = new TournamentDto.ScheduleOutput();
        dto.setId(schedule.getId());
        dto.setScheduleJson(schedule.getScheduleJson());
        dto.setComputationTimeMs(schedule.getComputationTimeMs());
        dto.setSavedShuttles(schedule.getSavedShuttles());
        dto.setBoatChanges(schedule.getBoatChanges());
        dto.setFinalScore(schedule.getFinalScore());
        dto.setCreatedAt(schedule.getCreatedAt());
        return dto;
    }
}
