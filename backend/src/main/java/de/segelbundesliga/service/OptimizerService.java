package de.segelbundesliga.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import de.segelbundesliga.domain.Boat;
import de.segelbundesliga.domain.OptimizationSettings;
import de.segelbundesliga.domain.Team;
import de.segelbundesliga.domain.Tournament;
import de.segelbundesliga.dto.OptimizationDto;
import de.segelbundesliga.repository.TournamentRepository;
import gundramleifert.pairing_list.Optimizer;
import gundramleifert.pairing_list.configs.BoatConfig;
import gundramleifert.pairing_list.configs.OptBoatConfig;
import gundramleifert.pairing_list.configs.OptConfig;
import gundramleifert.pairing_list.configs.OptMatchMatrixConfig;
import gundramleifert.pairing_list.configs.OptimizationConfig;
import gundramleifert.pairing_list.configs.ScheduleConfig;
import gundramleifert.pairing_list.cost_calculators.CostCalculatorBoatSchedule;
import gundramleifert.pairing_list.types.Schedule;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.IOException;
import java.io.StringWriter;
import java.lang.reflect.Field;
import java.util.List;
import java.util.Map;
import java.util.Random;
import java.util.concurrent.ConcurrentHashMap;

@Service
@RequiredArgsConstructor
@Slf4j
public class OptimizerService {

    private final TournamentRepository tournamentRepository;
    private final ObjectMapper objectMapper;

    // Active SSE emitters per tournament
    private final Map<Long, SseEmitter> activeEmitters = new ConcurrentHashMap<>();

    // Running optimizations
    private final Map<Long, Boolean> runningOptimizations = new ConcurrentHashMap<>();

    public SseEmitter createEmitter(Long tournamentId) {
        // No timeout - optimization may take a while
        SseEmitter emitter = new SseEmitter(0L);

        emitter.onCompletion(() -> {
            log.debug("SSE emitter completed for tournament {}", tournamentId);
            activeEmitters.remove(tournamentId);
        });

        emitter.onTimeout(() -> {
            log.debug("SSE emitter timeout for tournament {}", tournamentId);
            activeEmitters.remove(tournamentId);
        });

        emitter.onError(e -> {
            log.error("SSE emitter error for tournament {}", tournamentId, e);
            activeEmitters.remove(tournamentId);
        });

        activeEmitters.put(tournamentId, emitter);
        return emitter;
    }

    public boolean isRunning(Long tournamentId) {
        return runningOptimizations.getOrDefault(tournamentId, false);
    }

    public void cancelOptimization(Long tournamentId) {
        runningOptimizations.put(tournamentId, false);
    }

    @Async("optimizerExecutor")
    public void runOptimization(Long tournamentId) {
        if (isRunning(tournamentId)) {
            sendEvent(tournamentId, OptimizationDto.ProgressEvent.failed(tournamentId, "Optimization already running"));
            return;
        }

        runningOptimizations.put(tournamentId, true);
        long startTime = System.currentTimeMillis();

        try {
            Tournament tournament = tournamentRepository.findById(tournamentId)
                    .orElseThrow(() -> new IllegalArgumentException("Tournament not found: " + tournamentId));

            // Build configs from entities
            ScheduleConfig scheduleConfig = buildScheduleConfig(tournament);
            OptimizationConfig optimizationConfig = buildOptimizationConfig(tournament.getOptimizationSettings());

            // Update status
            tournament.setStatus(Tournament.TournamentStatus.OPTIMIZING);
            tournamentRepository.save(tournament);

            sendEvent(tournamentId, OptimizationDto.ProgressEvent.started(tournamentId, scheduleConfig.flights));

            // Initialize optimizer
            Random random = new Random(optimizationConfig.seed);
            Optimizer optimizer = new Optimizer();
            optimizer.init(scheduleConfig, optimizationConfig, random);

            // Phase 1: Match Matrix Optimization
            sendEvent(tournamentId, OptimizationDto.ProgressEvent.phaseStarted(
                    tournamentId, "MATCH_MATRIX", 1, scheduleConfig.flights));

            Schedule schedule = optimizer.optimizeMatchMatrix(s -> {
                if (!runningOptimizations.getOrDefault(tournamentId, false)) {
                    throw new OptimizationCancelledException("Optimization cancelled");
                }
                // Progress callback during match matrix optimization
                sendEvent(tournamentId, OptimizationDto.ProgressEvent.progress(
                        tournamentId, "MATCH_MATRIX", 0, 0, 0, 0));
            });

            sendEvent(tournamentId, OptimizationDto.ProgressEvent.phaseCompleted(
                    tournamentId, "MATCH_MATRIX", 0));

            // Phase 2: Boat Schedule Optimization
            if (optimizationConfig.optBoatUsage != null && optimizationConfig.optBoatUsage.loops > 0) {
                sendEvent(tournamentId, OptimizationDto.ProgressEvent.phaseStarted(
                        tournamentId, "BOAT_SCHEDULE", scheduleConfig.flights, scheduleConfig.flights));

                schedule = gundramleifert.pairing_list.Util.shuffleBoats(schedule, random);
                schedule = optimizer.optimizeBoatSchedule(schedule, s -> {
                    if (!runningOptimizations.getOrDefault(tournamentId, false)) {
                        throw new OptimizationCancelledException("Optimization cancelled");
                    }
                    sendEvent(tournamentId, OptimizationDto.ProgressEvent.progress(
                            tournamentId, "BOAT_SCHEDULE", 0, 0, 0, 0));
                });

                sendEvent(tournamentId, OptimizationDto.ProgressEvent.phaseCompleted(
                        tournamentId, "BOAT_SCHEDULE", 0));
            }

            // Calculate statistics
            int[] interFlightStats = CostCalculatorBoatSchedule.getInterFlightStat(schedule, scheduleConfig.numTeams);
            int savedShuttlesHarbour = interFlightStats[0];
            int savedShuttlesSea = interFlightStats[1];
            int boatChanges = interFlightStats[2];

            // Serialize result
            StringWriter writer = new StringWriter();
            objectMapper.writeValue(writer, schedule);
            String scheduleJson = writer.toString();

            long computationTime = System.currentTimeMillis() - startTime;

            // Save result
            tournament.setResultSchedule(scheduleJson);
            tournament.setComputationTimeMs(computationTime);
            tournament.setSavedShuttles(savedShuttlesHarbour + savedShuttlesSea);
            tournament.setBoatChanges(boatChanges);
            tournament.setStatus(Tournament.TournamentStatus.COMPLETED);
            tournamentRepository.save(tournament);

            sendEvent(tournamentId, OptimizationDto.ProgressEvent.completed(tournamentId, computationTime));

            log.info("Optimization completed for tournament {} in {}ms", tournamentId, computationTime);

        } catch (OptimizationCancelledException e) {
            log.info("Optimization cancelled for tournament {}", tournamentId);
            sendEvent(tournamentId, OptimizationDto.ProgressEvent.failed(tournamentId, "Optimization cancelled"));
            updateTournamentStatus(tournamentId, Tournament.TournamentStatus.READY);

        } catch (Exception e) {
            log.error("Optimization failed for tournament {}", tournamentId, e);
            sendEvent(tournamentId, OptimizationDto.ProgressEvent.failed(tournamentId, e.getMessage()));
            updateTournamentStatus(tournamentId, Tournament.TournamentStatus.READY);

        } finally {
            runningOptimizations.remove(tournamentId);
            completeEmitter(tournamentId);
        }
    }

    private ScheduleConfig buildScheduleConfig(Tournament tournament) {
        ScheduleConfig config = new ScheduleConfig();

        config.flights = tournament.getFlights();

        // Teams
        List<Team> teams = tournament.getTeams();
        config.teams = teams.stream()
                .map(Team::getName)
                .toArray(String[]::new);

        // Boats
        List<Boat> boats = tournament.getBoats();
        config.boats = boats.stream()
                .map(b -> {
                    BoatConfig bc = createBoatConfig();
                    bc.name = b.getName();
                    bc.color = b.getColor();
                    return bc;
                })
                .toArray(BoatConfig[]::new);

        config.init();
        return config;
    }

    private BoatConfig createBoatConfig() {
        try {
            // BoatConfig has private constructor, use reflection
            var constructor = BoatConfig.class.getDeclaredConstructor();
            constructor.setAccessible(true);
            return constructor.newInstance();
        } catch (Exception e) {
            throw new RuntimeException("Failed to create BoatConfig", e);
        }
    }

    private OptimizationConfig buildOptimizationConfig(OptimizationSettings settings) {
        OptimizationConfig config = new OptimizationConfig();

        config.seed = settings.getSeed();

        // MatchMatrix config
        config.optMatchMatrix = createOptMatchMatrixConfig();
        config.optMatchMatrix.swapTeams = settings.getMmSwapTeams();
        config.optMatchMatrix.maxBranches = settings.getMmMaxBranches();
        config.optMatchMatrix.factorLessParticipants = settings.getMmFactorLessParticipants();
        config.optMatchMatrix.factorTeamMissing = settings.getMmFactorTeamMissing();
        config.optMatchMatrix.loops = settings.getMmLoops();
        config.optMatchMatrix.individuals = settings.getMmIndividuals();
        config.optMatchMatrix.earlyStopping = settings.getMmEarlyStopping();
        config.optMatchMatrix.showEveryN = settings.getMmShowEveryN();

        // BoatUsage config
        config.optBoatUsage = createOptBoatConfig();
        config.optBoatUsage.swapBoats = settings.getBsSwapBoats();
        config.optBoatUsage.swapRaces = settings.getBsSwapRaces();
        config.optBoatUsage.weightStayOnBoat = settings.getBsWeightStayOnBoat();
        config.optBoatUsage.weightStayOnShuttle = settings.getBsWeightStayOnShuttle();
        config.optBoatUsage.weightChangeBetweenBoats = settings.getBsWeightChangeBetweenBoats();
        config.optBoatUsage.loops = settings.getBsLoops();
        config.optBoatUsage.individuals = settings.getBsIndividuals();
        config.optBoatUsage.earlyStopping = settings.getBsEarlyStopping();
        config.optBoatUsage.showEveryN = settings.getBsShowEveryN();

        return config;
    }

    private OptMatchMatrixConfig createOptMatchMatrixConfig() {
        try {
            var constructor = OptMatchMatrixConfig.class.getDeclaredConstructor();
            constructor.setAccessible(true);
            return constructor.newInstance();
        } catch (Exception e) {
            throw new RuntimeException("Failed to create OptMatchMatrixConfig", e);
        }
    }

    private OptBoatConfig createOptBoatConfig() {
        try {
            var constructor = OptBoatConfig.class.getDeclaredConstructor();
            constructor.setAccessible(true);
            return constructor.newInstance();
        } catch (Exception e) {
            throw new RuntimeException("Failed to create OptBoatConfig", e);
        }
    }

    private void sendEvent(Long tournamentId, OptimizationDto.ProgressEvent event) {
        SseEmitter emitter = activeEmitters.get(tournamentId);
        if (emitter != null) {
            try {
                emitter.send(SseEmitter.event()
                        .name(event.getType().name().toLowerCase())
                        .data(event));
            } catch (IOException e) {
                log.warn("Failed to send SSE event to tournament {}", tournamentId, e);
                activeEmitters.remove(tournamentId);
            }
        }
    }

    private void completeEmitter(Long tournamentId) {
        SseEmitter emitter = activeEmitters.remove(tournamentId);
        if (emitter != null) {
            try {
                emitter.complete();
            } catch (Exception e) {
                log.debug("Error completing emitter for tournament {}", tournamentId, e);
            }
        }
    }

    private void updateTournamentStatus(Long tournamentId, Tournament.TournamentStatus status) {
        tournamentRepository.findById(tournamentId).ifPresent(t -> {
            t.setStatus(status);
            tournamentRepository.save(t);
        });
    }

    public OptimizationDto.Result getResult(Long tournamentId) {
        Tournament tournament = tournamentRepository.findById(tournamentId)
                .orElseThrow(() -> new IllegalArgumentException("Tournament not found: " + tournamentId));

        return OptimizationDto.Result.builder()
                .tournamentId(tournamentId)
                .schedule(tournament.getResultSchedule())
                .computationTimeMs(tournament.getComputationTimeMs())
                .savedShuttles(tournament.getSavedShuttles())
                .boatChanges(tournament.getBoatChanges())
                .build();
    }

    public boolean hasRequiredConfig(Tournament tournament) {
        return tournament.getTeams() != null && !tournament.getTeams().isEmpty()
                && tournament.getBoats() != null && !tournament.getBoats().isEmpty();
    }

    public static class OptimizationCancelledException extends RuntimeException {
        public OptimizationCancelledException(String message) {
            super(message);
        }
    }
}
