package de.segelbundesliga.domain;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

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

    // Optimization settings (embedded)
    @Embedded
    private OptimizationSettings optimizationSettings = new OptimizationSettings();

    // Optimierungsergebnis (bleibt JSON, da komplexe Struktur)
    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "result_schedule", columnDefinition = "jsonb")
    private String resultSchedule;

    @Column(name = "computation_time_ms")
    private Long computationTimeMs;

    @Column(name = "saved_shuttles")
    private Integer savedShuttles;

    @Column(name = "boat_changes")
    private Integer boatChanges;

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
