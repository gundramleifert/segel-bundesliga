package de.segelbundesliga.dto;

import de.segelbundesliga.domain.OptimizationConfig;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Data;

import java.time.Instant;

public class OptimizationConfigDto {

    @Data
    public static class Create {
        @NotBlank
        private String name;
        private String description;

        // Match Matrix settings
        @NotNull
        @Min(0)
        private Integer seed = 42;

        @NotNull
        @Min(1)
        private Integer mmSwapTeams = 2;

        @NotNull
        @Min(1)
        private Integer mmMaxBranches = 1;

        @NotNull
        private Double mmFactorLessParticipants = 3.01;

        @NotNull
        private Double mmFactorTeamMissing = 20.01;

        @NotNull
        @Min(1)
        private Integer mmLoops = 10000;

        @NotNull
        @Min(1)
        private Integer mmIndividuals = 100;

        @NotNull
        private Double mmEarlyStopping = -1.0;

        @NotNull
        @Min(1)
        private Integer mmShowEveryN = 1000;

        // Boat Schedule settings
        @NotNull
        @Min(1)
        private Integer bsSwapBoats = 2;

        @NotNull
        @Min(1)
        private Integer bsSwapRaces = 2;

        @NotNull
        private Double bsWeightStayOnBoat = 1.0;

        @NotNull
        private Double bsWeightStayOnShuttle = 1.0;

        @NotNull
        private Double bsWeightChangeBetweenBoats = 1.0;

        @NotNull
        @Min(1)
        private Integer bsLoops = 10000;

        @NotNull
        @Min(1)
        private Integer bsIndividuals = 100;

        @NotNull
        private Double bsEarlyStopping = -1.0;

        @NotNull
        @Min(1)
        private Integer bsShowEveryN = 1000;
    }

    @Data
    public static class Update {
        private String name;
        private String description;

        // Match Matrix settings
        @Min(0)
        private Integer seed;

        @Min(1)
        private Integer mmSwapTeams;

        @Min(1)
        private Integer mmMaxBranches;

        private Double mmFactorLessParticipants;
        private Double mmFactorTeamMissing;

        @Min(1)
        private Integer mmLoops;

        @Min(1)
        private Integer mmIndividuals;

        private Double mmEarlyStopping;

        @Min(1)
        private Integer mmShowEveryN;

        // Boat Schedule settings
        @Min(1)
        private Integer bsSwapBoats;

        @Min(1)
        private Integer bsSwapRaces;

        private Double bsWeightStayOnBoat;
        private Double bsWeightStayOnShuttle;
        private Double bsWeightChangeBetweenBoats;

        @Min(1)
        private Integer bsLoops;

        @Min(1)
        private Integer bsIndividuals;

        private Double bsEarlyStopping;

        @Min(1)
        private Integer bsShowEveryN;
    }

    @Data
    public static class Response {
        private Long id;
        private String name;
        private String description;
        private boolean systemDefault;

        // Match Matrix settings
        private Integer seed;
        private Integer mmSwapTeams;
        private Integer mmMaxBranches;
        private Double mmFactorLessParticipants;
        private Double mmFactorTeamMissing;
        private Integer mmLoops;
        private Integer mmIndividuals;
        private Double mmEarlyStopping;
        private Integer mmShowEveryN;

        // Boat Schedule settings
        private Integer bsSwapBoats;
        private Integer bsSwapRaces;
        private Double bsWeightStayOnBoat;
        private Double bsWeightStayOnShuttle;
        private Double bsWeightChangeBetweenBoats;
        private Integer bsLoops;
        private Integer bsIndividuals;
        private Double bsEarlyStopping;
        private Integer bsShowEveryN;

        private Instant createdAt;
        private Instant updatedAt;

        public static Response from(OptimizationConfig entity) {
            Response dto = new Response();
            dto.setId(entity.getId());
            dto.setName(entity.getName());
            dto.setDescription(entity.getDescription());
            dto.setSystemDefault(entity.isSystemDefault());

            // Match Matrix settings
            dto.setSeed(entity.getSeed());
            dto.setMmSwapTeams(entity.getMmSwapTeams());
            dto.setMmMaxBranches(entity.getMmMaxBranches());
            dto.setMmFactorLessParticipants(entity.getMmFactorLessParticipants());
            dto.setMmFactorTeamMissing(entity.getMmFactorTeamMissing());
            dto.setMmLoops(entity.getMmLoops());
            dto.setMmIndividuals(entity.getMmIndividuals());
            dto.setMmEarlyStopping(entity.getMmEarlyStopping());
            dto.setMmShowEveryN(entity.getMmShowEveryN());

            // Boat Schedule settings
            dto.setBsSwapBoats(entity.getBsSwapBoats());
            dto.setBsSwapRaces(entity.getBsSwapRaces());
            dto.setBsWeightStayOnBoat(entity.getBsWeightStayOnBoat());
            dto.setBsWeightStayOnShuttle(entity.getBsWeightStayOnShuttle());
            dto.setBsWeightChangeBetweenBoats(entity.getBsWeightChangeBetweenBoats());
            dto.setBsLoops(entity.getBsLoops());
            dto.setBsIndividuals(entity.getBsIndividuals());
            dto.setBsEarlyStopping(entity.getBsEarlyStopping());
            dto.setBsShowEveryN(entity.getBsShowEveryN());

            dto.setCreatedAt(entity.getCreatedAt());
            dto.setUpdatedAt(entity.getUpdatedAt());

            return dto;
        }
    }
}
