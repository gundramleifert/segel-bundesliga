import axios from 'axios';

export const api = axios.create({
  baseURL: '/api',
});

// Add auth token to requests
export function setAuthToken(token: string | null) {
  if (token) {
    api.defaults.headers.common['Authorization'] = `Bearer ${token}`;
  } else {
    delete api.defaults.headers.common['Authorization'];
  }
}

// Tournament types
export interface TeamInput {
  id?: number;
  name: string;
  sortOrder?: number;
}

export interface TeamOutput {
  id: number;
  name: string;
  sortOrder: number;
}

export interface BoatInput {
  id?: number;
  name: string;
  color?: string;
  sortOrder?: number;
}

export interface BoatOutput {
  id: number;
  name: string;
  color?: string;
  sortOrder: number;
}

export interface OptimizationSettings {
  seed?: number;
  // MatchMatrix
  mmSwapTeams?: number;
  mmMaxBranches?: number;
  mmFactorLessParticipants?: number;
  mmFactorTeamMissing?: number;
  mmLoops?: number;
  mmIndividuals?: number;
  mmEarlyStopping?: number;
  mmShowEveryN?: number;
  // BoatSchedule
  bsSwapBoats?: number;
  bsSwapRaces?: number;
  bsWeightStayOnBoat?: number;
  bsWeightStayOnShuttle?: number;
  bsWeightChangeBetweenBoats?: number;
  bsLoops?: number;
  bsIndividuals?: number;
  bsEarlyStopping?: number;
  bsShowEveryN?: number;
}

export interface Tournament {
  id: number;
  name: string;
  description?: string;
  eventDate?: string;
  location?: string;
  status: 'DRAFT' | 'READY' | 'OPTIMIZING' | 'COMPLETED' | 'ARCHIVED';
  flights: number;
  teams: TeamOutput[];
  boats: BoatOutput[];
  optimizationSettings: OptimizationSettings;
  resultSchedule?: string;
  computationTimeMs?: number;
  savedShuttles?: number;
  boatChanges?: number;
  createdAt: string;
}

export interface TournamentListItem {
  id: number;
  name: string;
  eventDate?: string;
  location?: string;
  status: string;
  teamCount: number;
  boatCount: number;
  createdAt: string;
}

export interface CreateTournament {
  name: string;
  description?: string;
  eventDate?: string;
  location?: string;
  flights?: number;
  teams?: TeamInput[];
  boats?: BoatInput[];
  optimizationSettings?: OptimizationSettings;
}

export interface UpdateTournament {
  name?: string;
  description?: string;
  eventDate?: string;
  location?: string;
  flights?: number;
  teams?: TeamInput[];
  boats?: BoatInput[];
  optimizationSettings?: OptimizationSettings;
}

// API functions
export const tournamentApi = {
  getAll: () => api.get<{ content: TournamentListItem[] }>('/tournaments'),
  getMy: () => api.get<{ content: TournamentListItem[] }>('/tournaments/my'),
  getById: (id: number) => api.get<Tournament>(`/tournaments/${id}`),
  create: (data: CreateTournament) => api.post<Tournament>('/tournaments', data),
  update: (id: number, data: UpdateTournament) => api.put<Tournament>(`/tournaments/${id}`, data),
  delete: (id: number) => api.delete(`/tournaments/${id}`),
};

export const optimizationApi = {
  start: (tournamentId: number) => api.post(`/optimization/${tournamentId}/start`),
  cancel: (tournamentId: number) => api.post(`/optimization/${tournamentId}/cancel`),
  getStatus: (tournamentId: number) => api.get<{
    tournamentId: number;
    status: string;
    isRunning: boolean;
    hasResult: boolean;
  }>(`/optimization/${tournamentId}/status`),
  getResult: (tournamentId: number) => api.get(`/optimization/${tournamentId}/result`),
};
