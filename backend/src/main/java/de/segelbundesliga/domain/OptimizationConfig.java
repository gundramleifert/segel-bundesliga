package de.segelbundesliga.domain;

import jakarta.persistence.*;
import org.springframework.data.annotation.CreatedDate;
import org.springframework.data.annotation.LastModifiedDate;
import org.springframework.data.jpa.domain.support.AuditingEntityListener;

import java.time.Instant;

@Entity
@Table(name = "optimization_configs")
@EntityListeners(AuditingEntityListener.class)
public class OptimizationConfig {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private String name;
    private String description;
    private boolean systemDefault = false;

    // Match Matrix settings
    private Integer seed = 42;
    private Integer mmSwapTeams = 2;
    private Integer mmMaxBranches = 1;
    private Double mmFactorLessParticipants = 3.01;
    private Double mmFactorTeamMissing = 20.01;
    private Integer mmLoops = 10000;
    private Integer mmIndividuals = 100;
    private Double mmEarlyStopping = -1.0;
    private Integer mmShowEveryN = 1000;

    // Boat Schedule settings
    private Integer bsSwapBoats = 2;
    private Integer bsSwapRaces = 2;
    private Double bsWeightStayOnBoat = 1.0;
    private Double bsWeightStayOnShuttle = 1.0;
    private Double bsWeightChangeBetweenBoats = 1.0;
    private Integer bsLoops = 10000;
    private Integer bsIndividuals = 100;
    private Double bsEarlyStopping = -1.0;
    private Integer bsShowEveryN = 1000;

    @CreatedDate
    private Instant createdAt;

    @LastModifiedDate
    private Instant updatedAt;

    // Getters and setters

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    public String getDescription() {
        return description;
    }

    public void setDescription(String description) {
        this.description = description;
    }

    public boolean isSystemDefault() {
        return systemDefault;
    }

    public void setSystemDefault(boolean systemDefault) {
        this.systemDefault = systemDefault;
    }

    public Integer getSeed() {
        return seed;
    }

    public void setSeed(Integer seed) {
        this.seed = seed;
    }

    public Integer getMmSwapTeams() {
        return mmSwapTeams;
    }

    public void setMmSwapTeams(Integer mmSwapTeams) {
        this.mmSwapTeams = mmSwapTeams;
    }

    public Integer getMmMaxBranches() {
        return mmMaxBranches;
    }

    public void setMmMaxBranches(Integer mmMaxBranches) {
        this.mmMaxBranches = mmMaxBranches;
    }

    public Double getMmFactorLessParticipants() {
        return mmFactorLessParticipants;
    }

    public void setMmFactorLessParticipants(Double mmFactorLessParticipants) {
        this.mmFactorLessParticipants = mmFactorLessParticipants;
    }

    public Double getMmFactorTeamMissing() {
        return mmFactorTeamMissing;
    }

    public void setMmFactorTeamMissing(Double mmFactorTeamMissing) {
        this.mmFactorTeamMissing = mmFactorTeamMissing;
    }

    public Integer getMmLoops() {
        return mmLoops;
    }

    public void setMmLoops(Integer mmLoops) {
        this.mmLoops = mmLoops;
    }

    public Integer getMmIndividuals() {
        return mmIndividuals;
    }

    public void setMmIndividuals(Integer mmIndividuals) {
        this.mmIndividuals = mmIndividuals;
    }

    public Double getMmEarlyStopping() {
        return mmEarlyStopping;
    }

    public void setMmEarlyStopping(Double mmEarlyStopping) {
        this.mmEarlyStopping = mmEarlyStopping;
    }

    public Integer getMmShowEveryN() {
        return mmShowEveryN;
    }

    public void setMmShowEveryN(Integer mmShowEveryN) {
        this.mmShowEveryN = mmShowEveryN;
    }

    public Integer getBsSwapBoats() {
        return bsSwapBoats;
    }

    public void setBsSwapBoats(Integer bsSwapBoats) {
        this.bsSwapBoats = bsSwapBoats;
    }

    public Integer getBsSwapRaces() {
        return bsSwapRaces;
    }

    public void setBsSwapRaces(Integer bsSwapRaces) {
        this.bsSwapRaces = bsSwapRaces;
    }

    public Double getBsWeightStayOnBoat() {
        return bsWeightStayOnBoat;
    }

    public void setBsWeightStayOnBoat(Double bsWeightStayOnBoat) {
        this.bsWeightStayOnBoat = bsWeightStayOnBoat;
    }

    public Double getBsWeightStayOnShuttle() {
        return bsWeightStayOnShuttle;
    }

    public void setBsWeightStayOnShuttle(Double bsWeightStayOnShuttle) {
        this.bsWeightStayOnShuttle = bsWeightStayOnShuttle;
    }

    public Double getBsWeightChangeBetweenBoats() {
        return bsWeightChangeBetweenBoats;
    }

    public void setBsWeightChangeBetweenBoats(Double bsWeightChangeBetweenBoats) {
        this.bsWeightChangeBetweenBoats = bsWeightChangeBetweenBoats;
    }

    public Integer getBsLoops() {
        return bsLoops;
    }

    public void setBsLoops(Integer bsLoops) {
        this.bsLoops = bsLoops;
    }

    public Integer getBsIndividuals() {
        return bsIndividuals;
    }

    public void setBsIndividuals(Integer bsIndividuals) {
        this.bsIndividuals = bsIndividuals;
    }

    public Double getBsEarlyStopping() {
        return bsEarlyStopping;
    }

    public void setBsEarlyStopping(Double bsEarlyStopping) {
        this.bsEarlyStopping = bsEarlyStopping;
    }

    public Integer getBsShowEveryN() {
        return bsShowEveryN;
    }

    public void setBsShowEveryN(Integer bsShowEveryN) {
        this.bsShowEveryN = bsShowEveryN;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public void setCreatedAt(Instant createdAt) {
        this.createdAt = createdAt;
    }

    public Instant getUpdatedAt() {
        return updatedAt;
    }

    public void setUpdatedAt(Instant updatedAt) {
        this.updatedAt = updatedAt;
    }
}
