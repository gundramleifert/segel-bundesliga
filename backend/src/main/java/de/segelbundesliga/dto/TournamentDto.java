package de.segelbundesliga.dto;

import de.segelbundesliga.domain.Tournament.TournamentStatus;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import lombok.Data;

import java.time.Instant;
import java.time.LocalDate;
import java.util.List;

public class TournamentDto {

    @Data
    public static class Create {
        @NotBlank
        private String name;
        private String description;
        private LocalDate eventDate;
        private String location;
        @Min(1)
        private Integer flights = 3;
        private List<TeamInput> teams;
        private List<BoatInput> boats;
        private OptimizationSettingsInput optimizationSettings;
    }

    @Data
    public static class Update {
        private String name;
        private String description;
        private LocalDate eventDate;
        private String location;
        private TournamentStatus status;
        @Min(1)
        private Integer flights;
        private List<TeamInput> teams;
        private List<BoatInput> boats;
        private OptimizationSettingsInput optimizationSettings;
    }

    @Data
    public static class Response {
        private Long id;
        private String name;
        private String description;
        private LocalDate eventDate;
        private String location;
        private TournamentStatus status;
        private String ownerId;
        private Integer flights;
        private List<TeamOutput> teams;
        private List<BoatOutput> boats;
        private OptimizationSettingsOutput optimizationSettings;
        private String resultSchedule;
        private Long computationTimeMs;
        private Integer savedShuttles;
        private Integer boatChanges;
        private Instant createdAt;
        private Instant updatedAt;
    }

    @Data
    public static class ListItem {
        private Long id;
        private String name;
        private LocalDate eventDate;
        private String location;
        private TournamentStatus status;
        private Integer teamCount;
        private Integer boatCount;
        private Instant createdAt;
    }

    // Team DTOs
    @Data
    public static class TeamInput {
        private Long id; // for updates
        @NotBlank
        private String name;
        private Integer sortOrder;
    }

    @Data
    public static class TeamOutput {
        private Long id;
        private String name;
        private Integer sortOrder;
    }

    // Boat DTOs
    @Data
    public static class BoatInput {
        private Long id; // for updates
        @NotBlank
        private String name;
        private String color;
        private Integer sortOrder;
    }

    @Data
    public static class BoatOutput {
        private Long id;
        private String name;
        private String color;
        private Integer sortOrder;
    }

    // Optimization Settings DTOs
    @Data
    public static class OptimizationSettingsInput {
        private Integer seed;
        // MatchMatrix
        private Integer mmSwapTeams;
        private Integer mmMaxBranches;
        private Double mmFactorLessParticipants;
        private Double mmFactorTeamMissing;
        private Integer mmLoops;
        private Integer mmIndividuals;
        private Double mmEarlyStopping;
        private Integer mmShowEveryN;
        // BoatSchedule
        private Integer bsSwapBoats;
        private Integer bsSwapRaces;
        private Double bsWeightStayOnBoat;
        private Double bsWeightStayOnShuttle;
        private Double bsWeightChangeBetweenBoats;
        private Integer bsLoops;
        private Integer bsIndividuals;
        private Double bsEarlyStopping;
        private Integer bsShowEveryN;
    }

    @Data
    public static class OptimizationSettingsOutput {
        private Integer seed;
        // MatchMatrix
        private Integer mmSwapTeams;
        private Integer mmMaxBranches;
        private Double mmFactorLessParticipants;
        private Double mmFactorTeamMissing;
        private Integer mmLoops;
        private Integer mmIndividuals;
        private Double mmEarlyStopping;
        private Integer mmShowEveryN;
        // BoatSchedule
        private Integer bsSwapBoats;
        private Integer bsSwapRaces;
        private Double bsWeightStayOnBoat;
        private Double bsWeightStayOnShuttle;
        private Double bsWeightChangeBetweenBoats;
        private Integer bsLoops;
        private Integer bsIndividuals;
        private Double bsEarlyStopping;
        private Integer bsShowEveryN;
    }
}
