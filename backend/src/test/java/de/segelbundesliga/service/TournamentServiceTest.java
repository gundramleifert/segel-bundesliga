package de.segelbundesliga.service;

import de.segelbundesliga.domain.Boat;
import de.segelbundesliga.domain.OptimizationSettings;
import de.segelbundesliga.domain.Team;
import de.segelbundesliga.domain.Tournament;
import de.segelbundesliga.domain.Tournament.TournamentStatus;
import de.segelbundesliga.dto.TournamentDto;
import de.segelbundesliga.repository.TournamentRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;

import java.time.Instant;
import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
@DisplayName("TournamentService Tests")
class TournamentServiceTest {

    @Mock
    private TournamentRepository repository;

    @InjectMocks
    private TournamentService service;

    private Tournament testTournament;

    @BeforeEach
    void setUp() {
        testTournament = createTestTournament();
    }

    private Tournament createTestTournament() {
        Tournament tournament = new Tournament();
        tournament.setId(1L);
        tournament.setName("Test Regatta");
        tournament.setDescription("Test Description");
        tournament.setEventDate(LocalDate.of(2026, 6, 15));
        tournament.setLocation("Hamburg");
        tournament.setOwnerId("user-123");
        tournament.setStatus(TournamentStatus.DRAFT);
        tournament.setFlights(4);
        tournament.setCreatedAt(Instant.now());
        tournament.setUpdatedAt(Instant.now());

        // Add teams
        Team team1 = new Team();
        team1.setId(1L);
        team1.setName("Team Alpha");
        team1.setSortOrder(0);
        tournament.addTeam(team1);

        Team team2 = new Team();
        team2.setId(2L);
        team2.setName("Team Beta");
        team2.setSortOrder(1);
        tournament.addTeam(team2);

        // Add boats
        Boat boat1 = new Boat();
        boat1.setId(1L);
        boat1.setName("Boat 1");
        boat1.setColor("#FF0000");
        boat1.setSortOrder(0);
        tournament.addBoat(boat1);

        return tournament;
    }

    @Nested
    @DisplayName("create()")
    class CreateTests {

        @Test
        @DisplayName("creates tournament with minimal data")
        void create_minimalData_success() {
            TournamentDto.Create dto = new TournamentDto.Create();
            dto.setName("New Tournament");

            when(repository.save(any(Tournament.class))).thenAnswer(invocation -> {
                Tournament t = invocation.getArgument(0);
                t.setId(1L);
                t.setCreatedAt(Instant.now());
                t.setUpdatedAt(Instant.now());
                return t;
            });

            TournamentDto.Response response = service.create(dto, "user-123");

            assertThat(response.getName()).isEqualTo("New Tournament");
            assertThat(response.getOwnerId()).isEqualTo("user-123");
            assertThat(response.getStatus()).isEqualTo(TournamentStatus.DRAFT);
        }

        @Test
        @DisplayName("creates tournament with teams and boats")
        void create_withTeamsAndBoats_success() {
            TournamentDto.Create dto = new TournamentDto.Create();
            dto.setName("Full Tournament");
            dto.setFlights(5);
            dto.setTeams(List.of(
                    createTeamInput("Team A", 0),
                    createTeamInput("Team B", 1)
            ));
            dto.setBoats(List.of(
                    createBoatInput("Boat 1", "#FF0000", 0),
                    createBoatInput("Boat 2", "#00FF00", 1)
            ));

            when(repository.save(any(Tournament.class))).thenAnswer(invocation -> {
                Tournament t = invocation.getArgument(0);
                t.setId(1L);
                t.setCreatedAt(Instant.now());
                return t;
            });

            TournamentDto.Response response = service.create(dto, "user-123");

            assertThat(response.getTeams()).hasSize(2);
            assertThat(response.getBoats()).hasSize(2);
            assertThat(response.getFlights()).isEqualTo(5);
        }

        @Test
        @DisplayName("auto-increments sort order when not provided")
        void create_noSortOrder_autoIncrements() {
            TournamentDto.Create dto = new TournamentDto.Create();
            dto.setName("Tournament");
            dto.setTeams(List.of(
                    createTeamInput("Team A", null),
                    createTeamInput("Team B", null),
                    createTeamInput("Team C", null)
            ));

            ArgumentCaptor<Tournament> captor = ArgumentCaptor.forClass(Tournament.class);
            when(repository.save(captor.capture())).thenAnswer(invocation -> {
                Tournament t = invocation.getArgument(0);
                t.setId(1L);
                return t;
            });

            service.create(dto, "user-123");

            Tournament saved = captor.getValue();
            List<Team> teams = saved.getTeams();
            assertThat(teams.get(0).getSortOrder()).isEqualTo(0);
            assertThat(teams.get(1).getSortOrder()).isEqualTo(1);
            assertThat(teams.get(2).getSortOrder()).isEqualTo(2);
        }

        @Test
        @DisplayName("applies optimization settings")
        void create_withOptimizationSettings_success() {
            TournamentDto.Create dto = new TournamentDto.Create();
            dto.setName("Optimized Tournament");

            TournamentDto.OptimizationSettingsInput settings = new TournamentDto.OptimizationSettingsInput();
            settings.setSeed(42);
            settings.setMmLoops(100);
            settings.setBsLoops(200);
            dto.setOptimizationSettings(settings);

            when(repository.save(any(Tournament.class))).thenAnswer(invocation -> {
                Tournament t = invocation.getArgument(0);
                t.setId(1L);
                return t;
            });

            TournamentDto.Response response = service.create(dto, "user-123");

            assertThat(response.getOptimizationSettings().getSeed()).isEqualTo(42);
            assertThat(response.getOptimizationSettings().getMmLoops()).isEqualTo(100);
            assertThat(response.getOptimizationSettings().getBsLoops()).isEqualTo(200);
        }
    }

    @Nested
    @DisplayName("getById()")
    class GetByIdTests {

        @Test
        @DisplayName("returns tournament when found")
        void getById_found_returnsTournament() {
            when(repository.findById(1L)).thenReturn(Optional.of(testTournament));

            TournamentDto.Response response = service.getById(1L);

            assertThat(response.getId()).isEqualTo(1L);
            assertThat(response.getName()).isEqualTo("Test Regatta");
            assertThat(response.getTeams()).hasSize(2);
            assertThat(response.getBoats()).hasSize(1);
        }

        @Test
        @DisplayName("throws EntityNotFoundException when not found")
        void getById_notFound_throwsException() {
            when(repository.findById(999L)).thenReturn(Optional.empty());

            assertThatThrownBy(() -> service.getById(999L))
                    .isInstanceOf(EntityNotFoundException.class)
                    .hasMessageContaining("Tournament")
                    .hasMessageContaining("999");
        }
    }

    @Nested
    @DisplayName("getAll()")
    class GetAllTests {

        @Test
        @DisplayName("returns paginated list of tournaments")
        void getAll_returnsPaginatedList() {
            Pageable pageable = PageRequest.of(0, 10);
            Page<Tournament> page = new PageImpl<>(List.of(testTournament), pageable, 1);
            when(repository.findAll(pageable)).thenReturn(page);

            Page<TournamentDto.ListItem> result = service.getAll(pageable);

            assertThat(result.getContent()).hasSize(1);
            assertThat(result.getContent().get(0).getName()).isEqualTo("Test Regatta");
            assertThat(result.getContent().get(0).getTeamCount()).isEqualTo(2);
            assertThat(result.getContent().get(0).getBoatCount()).isEqualTo(1);
        }

        @Test
        @DisplayName("returns empty page when no tournaments")
        void getAll_noTournaments_returnsEmptyPage() {
            Pageable pageable = PageRequest.of(0, 10);
            Page<Tournament> emptyPage = new PageImpl<>(List.of(), pageable, 0);
            when(repository.findAll(pageable)).thenReturn(emptyPage);

            Page<TournamentDto.ListItem> result = service.getAll(pageable);

            assertThat(result.getContent()).isEmpty();
            assertThat(result.getTotalElements()).isZero();
        }
    }

    @Nested
    @DisplayName("getByOwner()")
    class GetByOwnerTests {

        @Test
        @DisplayName("returns tournaments for owner")
        void getByOwner_returnsOwnersTournaments() {
            Pageable pageable = PageRequest.of(0, 10);
            Page<Tournament> page = new PageImpl<>(List.of(testTournament), pageable, 1);
            when(repository.findByOwnerId("user-123", pageable)).thenReturn(page);

            Page<TournamentDto.ListItem> result = service.getByOwner("user-123", pageable);

            assertThat(result.getContent()).hasSize(1);
            verify(repository).findByOwnerId("user-123", pageable);
        }
    }

    @Nested
    @DisplayName("update()")
    class UpdateTests {

        @Test
        @DisplayName("updates only provided fields")
        void update_partialUpdate_onlyChangesProvidedFields() {
            when(repository.findById(1L)).thenReturn(Optional.of(testTournament));
            when(repository.save(any(Tournament.class))).thenAnswer(i -> i.getArgument(0));

            TournamentDto.Update dto = new TournamentDto.Update();
            dto.setName("Updated Name");
            // description, eventDate, location left null

            TournamentDto.Response response = service.update(1L, dto);

            assertThat(response.getName()).isEqualTo("Updated Name");
            assertThat(response.getDescription()).isEqualTo("Test Description"); // unchanged
            assertThat(response.getLocation()).isEqualTo("Hamburg"); // unchanged
        }

        @Test
        @DisplayName("replaces all teams when teams provided")
        void update_withTeams_replacesAllTeams() {
            when(repository.findById(1L)).thenReturn(Optional.of(testTournament));
            when(repository.save(any(Tournament.class))).thenAnswer(i -> i.getArgument(0));

            TournamentDto.Update dto = new TournamentDto.Update();
            dto.setTeams(List.of(
                    createTeamInput("New Team 1", 0),
                    createTeamInput("New Team 2", 1),
                    createTeamInput("New Team 3", 2)
            ));

            TournamentDto.Response response = service.update(1L, dto);

            assertThat(response.getTeams()).hasSize(3);
            assertThat(response.getTeams().get(0).getName()).isEqualTo("New Team 1");
        }

        @Test
        @DisplayName("updates status")
        void update_status_updatesStatus() {
            when(repository.findById(1L)).thenReturn(Optional.of(testTournament));
            when(repository.save(any(Tournament.class))).thenAnswer(i -> i.getArgument(0));

            TournamentDto.Update dto = new TournamentDto.Update();
            dto.setStatus(TournamentStatus.READY);

            TournamentDto.Response response = service.update(1L, dto);

            assertThat(response.getStatus()).isEqualTo(TournamentStatus.READY);
        }

        @Test
        @DisplayName("throws EntityNotFoundException when tournament not found")
        void update_notFound_throwsException() {
            when(repository.findById(999L)).thenReturn(Optional.empty());

            TournamentDto.Update dto = new TournamentDto.Update();
            dto.setName("Updated");

            assertThatThrownBy(() -> service.update(999L, dto))
                    .isInstanceOf(EntityNotFoundException.class);
        }
    }

    @Nested
    @DisplayName("delete()")
    class DeleteTests {

        @Test
        @DisplayName("deletes tournament when exists")
        void delete_exists_deletesTournament() {
            when(repository.existsById(1L)).thenReturn(true);
            doNothing().when(repository).deleteById(1L);

            service.delete(1L);

            verify(repository).deleteById(1L);
        }

        @Test
        @DisplayName("throws EntityNotFoundException when not exists")
        void delete_notExists_throwsException() {
            when(repository.existsById(999L)).thenReturn(false);

            assertThatThrownBy(() -> service.delete(999L))
                    .isInstanceOf(EntityNotFoundException.class);

            verify(repository, never()).deleteById(any());
        }
    }

    @Nested
    @DisplayName("isOwner()")
    class IsOwnerTests {

        @Test
        @DisplayName("returns true for actual owner")
        void isOwner_actualOwner_returnsTrue() {
            when(repository.findById(1L)).thenReturn(Optional.of(testTournament));

            boolean result = service.isOwner(1L, "user-123");

            assertThat(result).isTrue();
        }

        @Test
        @DisplayName("returns false for different user")
        void isOwner_differentUser_returnsFalse() {
            when(repository.findById(1L)).thenReturn(Optional.of(testTournament));

            boolean result = service.isOwner(1L, "other-user");

            assertThat(result).isFalse();
        }

        @Test
        @DisplayName("returns false when tournament not found")
        void isOwner_notFound_returnsFalse() {
            when(repository.findById(999L)).thenReturn(Optional.empty());

            boolean result = service.isOwner(999L, "user-123");

            assertThat(result).isFalse();
        }
    }

    // Helper methods for creating test DTOs
    private TournamentDto.TeamInput createTeamInput(String name, Integer sortOrder) {
        TournamentDto.TeamInput input = new TournamentDto.TeamInput();
        input.setName(name);
        input.setSortOrder(sortOrder);
        return input;
    }

    private TournamentDto.BoatInput createBoatInput(String name, String color, Integer sortOrder) {
        TournamentDto.BoatInput input = new TournamentDto.BoatInput();
        input.setName(name);
        input.setColor(color);
        input.setSortOrder(sortOrder);
        return input;
    }
}
