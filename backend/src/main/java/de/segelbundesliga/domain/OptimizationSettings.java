package de.segelbundesliga.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Embeddable;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Embeddable
@Getter
@Setter
@NoArgsConstructor
public class OptimizationSettings {

    // General
    @Column(name = "opt_seed")
    private Integer seed = 42;

    // MatchMatrix optimization
    @Column(name = "opt_mm_swap_teams")
    private Integer mmSwapTeams = 2;

    @Column(name = "opt_mm_max_branches")
    private Integer mmMaxBranches = 1;

    @Column(name = "opt_mm_factor_less_participants")
    private Double mmFactorLessParticipants = 3.01;

    @Column(name = "opt_mm_factor_team_missing")
    private Double mmFactorTeamMissing = 20.01;

    @Column(name = "opt_mm_loops")
    private Integer mmLoops = 10000;

    @Column(name = "opt_mm_individuals")
    private Integer mmIndividuals = 100;

    @Column(name = "opt_mm_early_stopping")
    private Double mmEarlyStopping = -1.0;

    @Column(name = "opt_mm_show_every_n")
    private Integer mmShowEveryN = 1000;

    // BoatSchedule optimization
    @Column(name = "opt_bs_swap_boats")
    private Integer bsSwapBoats = 2;

    @Column(name = "opt_bs_swap_races")
    private Integer bsSwapRaces = 2;

    @Column(name = "opt_bs_weight_stay_on_boat")
    private Double bsWeightStayOnBoat = 1.0;

    @Column(name = "opt_bs_weight_stay_on_shuttle")
    private Double bsWeightStayOnShuttle = 1.0;

    @Column(name = "opt_bs_weight_change_between_boats")
    private Double bsWeightChangeBetweenBoats = 1.0;

    @Column(name = "opt_bs_loops")
    private Integer bsLoops = 10000;

    @Column(name = "opt_bs_individuals")
    private Integer bsIndividuals = 100;

    @Column(name = "opt_bs_early_stopping")
    private Double bsEarlyStopping = -1.0;

    @Column(name = "opt_bs_show_every_n")
    private Integer bsShowEveryN = 1000;
}
