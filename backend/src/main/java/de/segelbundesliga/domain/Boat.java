package de.segelbundesliga.domain;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.util.Objects;

@Entity
@Table(name = "boats", uniqueConstraints = {
    @UniqueConstraint(name = "uk_boats_tournament_name", columnNames = {"tournament_id", "name"})
})
@Getter
@Setter
@NoArgsConstructor
public class Boat extends BaseEntity {

    @Column(nullable = false)
    private String name;

    @Column(length = 7)
    private String color;

    @Column(name = "sort_order")
    private Integer sortOrder = 0;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "tournament_id", nullable = false)
    private Tournament tournament;

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (o == null || getClass() != o.getClass()) return false;
        Boat boat = (Boat) o;
        return getId() != null && Objects.equals(getId(), boat.getId());
    }

    @Override
    public int hashCode() {
        return getClass().hashCode();
    }
}
