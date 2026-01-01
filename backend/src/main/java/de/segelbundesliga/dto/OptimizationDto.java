package de.segelbundesliga.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

public class OptimizationDto {

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class StartRequest {
        private Long tournamentId;
    }

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class ProgressEvent {
        private EventType type;
        private String phase;
        private int currentFlight;
        private int totalFlights;
        private int iteration;
        private int totalIterations;
        private double currentScore;
        private double bestScore;
        private String message;
        private Long tournamentId;

        public enum EventType {
            STARTED,
            PHASE_STARTED,
            PROGRESS,
            PHASE_COMPLETED,
            COMPLETED,
            FAILED
        }

        public static ProgressEvent started(Long tournamentId, int totalFlights) {
            return ProgressEvent.builder()
                    .type(EventType.STARTED)
                    .tournamentId(tournamentId)
                    .totalFlights(totalFlights)
                    .message("Optimization started")
                    .build();
        }

        public static ProgressEvent phaseStarted(Long tournamentId, String phase, int currentFlight, int totalFlights) {
            return ProgressEvent.builder()
                    .type(EventType.PHASE_STARTED)
                    .tournamentId(tournamentId)
                    .phase(phase)
                    .currentFlight(currentFlight)
                    .totalFlights(totalFlights)
                    .message("Phase started: " + phase)
                    .build();
        }

        public static ProgressEvent progress(Long tournamentId, String phase, int iteration, int totalIterations, double currentScore, double bestScore) {
            return ProgressEvent.builder()
                    .type(EventType.PROGRESS)
                    .tournamentId(tournamentId)
                    .phase(phase)
                    .iteration(iteration)
                    .totalIterations(totalIterations)
                    .currentScore(currentScore)
                    .bestScore(bestScore)
                    .build();
        }

        public static ProgressEvent phaseCompleted(Long tournamentId, String phase, double bestScore) {
            return ProgressEvent.builder()
                    .type(EventType.PHASE_COMPLETED)
                    .tournamentId(tournamentId)
                    .phase(phase)
                    .bestScore(bestScore)
                    .message("Phase completed: " + phase)
                    .build();
        }

        public static ProgressEvent completed(Long tournamentId, long computationTimeMs) {
            return ProgressEvent.builder()
                    .type(EventType.COMPLETED)
                    .tournamentId(tournamentId)
                    .message("Optimization completed in " + computationTimeMs + "ms")
                    .build();
        }

        public static ProgressEvent failed(Long tournamentId, String errorMessage) {
            return ProgressEvent.builder()
                    .type(EventType.FAILED)
                    .tournamentId(tournamentId)
                    .message(errorMessage)
                    .build();
        }
    }

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class Result {
        private Long tournamentId;
        private String schedule;
        private Long computationTimeMs;
        private Integer savedShuttles;
        private Integer boatChanges;
        private double finalScore;
    }
}
