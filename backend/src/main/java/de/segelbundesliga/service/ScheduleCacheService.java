package de.segelbundesliga.service;

import de.segelbundesliga.domain.Schedule;
import de.segelbundesliga.domain.Team;
import de.segelbundesliga.domain.Tournament;
import de.segelbundesliga.repository.ScheduleRepository;
import org.apache.commons.codec.digest.DigestUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.Comparator;
import java.util.List;
import java.util.Optional;
import java.util.stream.Collectors;

@Service
public class ScheduleCacheService {

    @Autowired
    private ScheduleRepository scheduleRepository;

    /**
     * Compute cache key from tournament configuration
     * Key = SHA-256(numTeams + numBoats + flights + sorted team names)
     */
    public String computeConfigHash(Tournament tournament) {
        List<String> teamNames = tournament.getTeams().stream()
            .sorted(Comparator.comparing(Team::getSortOrder))
            .map(Team::getName)
            .collect(Collectors.toList());

        String configString = String.format(
            "%d|%d|%d|%s",
            tournament.getTeams().size(),
            tournament.getBoats().size(),
            tournament.getFlights(),
            String.join(",", teamNames)
        );

        return DigestUtils.sha256Hex(configString);
    }

    /**
     * Lookup cached schedule by configuration hash
     */
    public Optional<Schedule> findCachedSchedule(String configHash) {
        return scheduleRepository.findByConfigHash(configHash);
    }

    /**
     * Save new schedule to cache
     */
    @Transactional
    public Schedule saveSchedule(String configHash, Tournament tournament,
                                 String scheduleJson, Long computationTimeMs,
                                 Integer savedShuttles, Integer boatChanges, Double finalScore) {
        Schedule schedule = new Schedule();
        schedule.setConfigHash(configHash);
        schedule.setNumTeams(tournament.getTeams().size());
        schedule.setNumBoats(tournament.getBoats().size());
        schedule.setNumFlights(tournament.getFlights());
        schedule.setScheduleJson(scheduleJson);
        schedule.setComputationTimeMs(computationTimeMs);
        schedule.setSavedShuttles(savedShuttles);
        schedule.setBoatChanges(boatChanges);
        schedule.setFinalScore(finalScore);

        return scheduleRepository.save(schedule);
    }
}
