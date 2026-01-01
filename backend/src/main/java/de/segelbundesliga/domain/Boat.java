package de.segelbundesliga.domain;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Entity
@Table(name = "boats")
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
}
