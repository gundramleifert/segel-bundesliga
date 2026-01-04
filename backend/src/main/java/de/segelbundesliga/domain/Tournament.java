package de.segelbundesliga.domain;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.time.LocalDate;
import java.util.HashSet;
import java.util.Set;

@Entity
@Table(name = "tournaments")
@Getter
@Setter
@NoArgsConstructor
public class Tournament extends BaseEntity {

    @Column(nullable = false)
    private String name;

    @Column(length = 2000)
    private String description;

    @Column(name = "event_date")
    private LocalDate eventDate;

    @Column(length = 200)
    private String location;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private TournamentStatus status = TournamentStatus.DRAFT;

    @Column(name = "owner_id", nullable = false)
    private String ownerId;

    // Schedule configuration
    @Column(nullable = false)
    private Integer flights = 3;

    @OneToMany(mappedBy = "tournament", cascade = CascadeType.ALL, orphanRemoval = true)
    @OrderBy("sortOrder ASC")
    private Set<Team> teams = new HashSet<>();

    @OneToMany(mappedBy = "tournament", cascade = CascadeType.ALL, orphanRemoval = true)
    @OrderBy("sortOrder ASC")
    private Set<Boat> boats = new HashSet<>();

    // Configuration references
    @ManyToOne
    @JoinColumn(name = "optimization_config_id")
    private OptimizationConfig optimizationConfig;

    @ManyToOne
    @JoinColumn(name = "display_config_id")
    private DisplayConfig displayConfig;

    @ManyToOne
    @JoinColumn(name = "schedule_id")
    private Schedule schedule;

    public enum TournamentStatus {
        DRAFT,
        READY,
        OPTIMIZING,
        COMPLETED,
        ARCHIVED
    }

    // Helper methods
    public void addTeam(Team team) {
        teams.add(team);
        team.setTournament(this);
    }

    public void removeTeam(Team team) {
        teams.remove(team);
        team.setTournament(null);
    }

    public void addBoat(Boat boat) {
        boats.add(boat);
        boat.setTournament(this);
    }

    public void removeBoat(Boat boat) {
        boats.remove(boat);
        boat.setTournament(null);
    }
}
