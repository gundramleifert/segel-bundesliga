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

// OptimizationConfig types
export interface OptimizationConfig {
  id: number;
  name: string;
  description?: string;
  systemDefault: boolean;
  // Match Matrix settings
  seed: number;
  mmSwapTeams: number;
  mmMaxBranches: number;
  mmFactorLessParticipants: number;
  mmFactorTeamMissing: number;
  mmLoops: number;
  mmIndividuals: number;
  mmEarlyStopping: number;
  mmShowEveryN: number;
  // Boat Schedule settings
  bsSwapBoats: number;
  bsSwapRaces: number;
  bsWeightStayOnBoat: number;
  bsWeightStayOnShuttle: number;
  bsWeightChangeBetweenBoats: number;
  bsLoops: number;
  bsIndividuals: number;
  bsEarlyStopping: number;
  bsShowEveryN: number;
  createdAt: string;
  updatedAt: string;
}

// DisplayConfig types
export interface DisplayConfig {
  id: number;
  name: string;
  description?: string;
  systemDefault: boolean;
  fontFamily: 'HELVETICA' | 'ARIAL' | 'TIMES_NEW_ROMAN';
  fontSize: number;
  orientation: 'PORTRAIT' | 'LANDSCAPE';
  createdAt: string;
  updatedAt: string;
}

// Schedule types
export interface Schedule {
  id: number;
  scheduleJson: string;
  computationTimeMs: number;
  savedShuttles: number;
  boatChanges: number;
  finalScore: number;
  createdAt: string;
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
  optimizationConfig?: OptimizationConfig;
  displayConfig?: DisplayConfig;
  schedule?: Schedule;
  createdAt: string;
  updatedAt: string;
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
  optimizationConfigId?: number;
  displayConfigId?: number;
}

export interface UpdateTournament {
  name?: string;
  description?: string;
  eventDate?: string;
  location?: string;
  flights?: number;
  teams?: TeamInput[];
  boats?: BoatInput[];
  optimizationConfigId?: number;
  displayConfigId?: number;
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
  exportPdf: (tournamentId: number) => api.get(`/optimization/${tournamentId}/export-pdf`, {
    responseType: 'blob',
  }),
};

export const optimizationConfigApi = {
  getAll: () => api.get<OptimizationConfig[]>('/optimization-configs'),
  getById: (id: number) => api.get<OptimizationConfig>(`/optimization-configs/${id}`),
};

export const displayConfigApi = {
  getAll: () => api.get<DisplayConfig[]>('/display-configs'),
  getById: (id: number) => api.get<DisplayConfig>(`/display-configs/${id}`),
};
