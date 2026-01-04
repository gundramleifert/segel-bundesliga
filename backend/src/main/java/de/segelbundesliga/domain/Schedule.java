package de.segelbundesliga.domain;

import jakarta.persistence.*;
import org.springframework.data.annotation.CreatedDate;
import org.springframework.data.jpa.domain.support.AuditingEntityListener;

import java.time.Instant;
import java.util.HashSet;
import java.util.Set;

@Entity
@Table(name = "schedules", indexes = {
    @Index(name = "idx_config_hash", columnList = "configHash")
})
@EntityListeners(AuditingEntityListener.class)
public class Schedule {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(unique = true, nullable = false, length = 64)
    private String configHash;

    private Integer numTeams;
    private Integer numBoats;
    private Integer numFlights;

    @Column(columnDefinition = "TEXT", nullable = false)
    private String scheduleJson;

    private Long computationTimeMs;
    private Integer savedShuttles;
    private Integer boatChanges;
    private Double finalScore;

    @CreatedDate
    private Instant createdAt;

    @OneToMany(mappedBy = "schedule")
    private Set<Tournament> tournaments = new HashSet<>();

    // Getters and setters

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public String getConfigHash() {
        return configHash;
    }

    public void setConfigHash(String configHash) {
        this.configHash = configHash;
    }

    public Integer getNumTeams() {
        return numTeams;
    }

    public void setNumTeams(Integer numTeams) {
        this.numTeams = numTeams;
    }

    public Integer getNumBoats() {
        return numBoats;
    }

    public void setNumBoats(Integer numBoats) {
        this.numBoats = numBoats;
    }

    public Integer getNumFlights() {
        return numFlights;
    }

    public void setNumFlights(Integer numFlights) {
        this.numFlights = numFlights;
    }

    public String getScheduleJson() {
        return scheduleJson;
    }

    public void setScheduleJson(String scheduleJson) {
        this.scheduleJson = scheduleJson;
    }

    public Long getComputationTimeMs() {
        return computationTimeMs;
    }

    public void setComputationTimeMs(Long computationTimeMs) {
        this.computationTimeMs = computationTimeMs;
    }

    public Integer getSavedShuttles() {
        return savedShuttles;
    }

    public void setSavedShuttles(Integer savedShuttles) {
        this.savedShuttles = savedShuttles;
    }

    public Integer getBoatChanges() {
        return boatChanges;
    }

    public void setBoatChanges(Integer boatChanges) {
        this.boatChanges = boatChanges;
    }

    public Double getFinalScore() {
        return finalScore;
    }

    public void setFinalScore(Double finalScore) {
        this.finalScore = finalScore;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public void setCreatedAt(Instant createdAt) {
        this.createdAt = createdAt;
    }

    public Set<Tournament> getTournaments() {
        return tournaments;
    }

    public void setTournaments(Set<Tournament> tournaments) {
        this.tournaments = tournaments;
    }
}
