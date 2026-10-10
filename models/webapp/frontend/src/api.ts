// Typed client for the FastAPI backend. Set VITE_API_URL when the API lives on another host.
const BASE = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") ?? "";

export async function api<T>(path: string, params?: Record<string, string | number | undefined | null>): Promise<T> {
  const url = new URL(`${BASE}/api${path}`, window.location.origin);
  if (params) for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, String(v));
  const res = await fetch(url.toString());
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json() as Promise<T>;
}

export type Meta = {
  our_team_code: string; our_team_name: string; home_stadium_id: string; seasons: number[];
  schedule_seasons: number[]; current_season: number; paper_url: string | null; model: string;
  synthetic: boolean; capabilities: Record<string, boolean>; has_rosters?: boolean;
  sources?: Record<string, string>;
};

export type Stadium = {
  id: string; venue_name: string; city: string; state: string; zone: string; team_code: string; team_name: string;
  lat: number; lon: number; altitude_m: number; typical_temp_c: number; air_density: number;
  density_vs_sea_level: number; movement_retained_pct: number; is_home: boolean;
};

export type StadiumDetail = Stadium & {
  league_by_pitch_type: { pitch_type: string; ivb_here: number; ivb_sea: number; hb_here: number; hb_sea: number; plate_speed_here: number; plate_speed_sea: number }[];
  our_games_here: { date: string; away_code: string; home_code: string }[];
};

export type LeaderRow = {
  rank: number; pitcher_id: string; name: string; team_code: string | null; status: string | null; role: string;
  throws: string; n_pitches: number; stuff_plus: number; stuff_neutral: number; altitude_delta: number; best_pitch: string | null;
};

export type PitcherHeader = {
  pitcher_id: string; name: string; season: number; throws: string; role: string; team_code: string | null;
  team_name: string | null; status: string | null; n_pitches: number; games: number | null; is_ours: boolean;
  seasons: number[]; stuff_neutral?: number; stuff_home?: number; stuff_here?: number; stuff_sea?: number;
};

export type PathPoint = { y: number; x: number; z: number };
export type PitchSide = { px: number; pz: number; plate_speed: number; ivb: number; hb: number; vaa: number; stuff_plus: number; path: PathPoint[] };
export type ProjectedPitch = {
  pitch_type: string; n: number; usage: number; rel_speed: number; spin_rate: number; spin_axis: number;
  whiff_pct: number | null; sea: PitchSide; here: PitchSide; stuff_neutral: number; miss_inches: number;
};
export type Projection = { stadium: Stadium; pitcher: PitcherHeader; aim: { x: number; z: number }; pitches: ProjectedPitch[] };

export type Profile = {
  pitcher: PitcherHeader;
  arsenal: { pitch_type: string; n: number; usage: number; rel_speed: number; spin_rate: number; extension: number; ivb_sea: number; hb_sea: number; whiff_pct: number | null; stuff_neutral: number; stuff_best_park: number; stuff_worst_park: number }[];
  by_park: { stadium_id: string; venue_name: string; team_code: string; altitude_m: number; stuff_plus: number }[];
  workload: { date: string; pitches: number; stadium_id: string | null }[];
};

export type Game = {
  date: string; home: boolean; opponent_code: string; opponent_name: string; stadium_id: string; venue_name: string;
  altitude_m: number; runs_for: number | null; runs_against: number | null; result: "W" | "L" | null; status: string;
};
export type Schedule = { season: number; team_code: string; games: Game[]; record: { w: number; l: number } | null };

export type Reason = { code: string; value?: number };
export type Reliever = {
  pitcher_id: string; name: string; throws: string; role: string; stuff_here: number; stuff_neutral: number;
  platoon_edge: number; score: number; status: "available" | "limited" | "rest"; reasons: Reason[];
  pitches_last_1d: number; pitches_last_3d: number; pitches_last_7d: number; pitches_per_game: number | null; slot?: string;
};
export type Bullpen = {
  available: boolean; reason?: string; as_of: string; season: number; stadium: Stadium; opponent_code: string;
  opponent_name: string; opponent_lhb_share: number | null; games: { date: string; home: boolean; opponent_code: string }[];
  workload_known: boolean; relievers: Reliever[]; starters: Reliever[];
};

export type FreeAgentRow = {
  pitcher_id: string; name: string; status: string; team_name: string | null; role: string; throws: string;
  last_season: number; n_pitches: number; stuff_home: number; stuff_neutral: number; altitude_delta: number;
  fit: number | null; best_pitch: string | null; best_pitch_stuff: number | null;
};
export type FreeAgents = { home_stadium_id: string; our_medians: Record<string, number | null>; total: number; rows: FreeAgentRow[] };

export type SearchResult = {
  pitchers: { pitcher_id: string; name: string; status: string; throws: string; role: string; season: number }[];
  stadiums: { id: string; venue_name: string; city: string; team_name: string; altitude_m: number }[];
};

export type Methodology = {
  model: string;
  validation: null | { metrics?: { name: string; value: number | string; split?: string }[]; submodels?: { name: string; target: string; metric: string; value: number | string }[]; notes?: string };
  altitude_study: { grouped_by: string; rows: { group: string; n: number; altitude_m: number; rho_ratio: number; spin_accel_ratio: number; spin_accel_se: number; drag_ratio: number }[]; elasticity_spin_vs_density: number | null };
  paper_url: string | null;
  data: { seasons: number[]; rows: number; capabilities: Record<string, boolean>; synthetic: boolean; source_files: string[] };
  rho_ref: number;
};
