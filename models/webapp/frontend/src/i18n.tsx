import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

export type Lang = "es" | "en";

const dict = {
  es: {
    appName: "Diablos Stuff+",
    tagline: "Calidad de pitcheo ajustada por altitud en la Liga Mexicana",
    navMap: "Mapa", navFreeAgents: "Agentes libres", navMethod: "Metodología",
    syntheticBanner: "Datos sintéticos de demostración. Se reemplazan con los datos reales al cargarlos.",
    placeholderModel: "Modelo provisional (sin entrenar)",
    searchPlaceholder: "Busca un pitcher por ID o un estadio…",
    searchPitchers: "Pitchers", searchStadiums: "Estadios", noResults: "Sin resultados",
    mapTitle: "Los 20 parques de la LMB", mapHint: "Haz clic en un estadio para ver cómo juega cada pitcher ahí.",
    movementLost: "Movimiento perdido vs. nivel del mar", pitchValue: "VALOR / PITCH",
    altitude: "Altitud", airDensity: "Densidad del aire", movementRetained: "Movimiento conservado",
    vsSeaLevel: "vs. nivel del mar", zoneNorte: "Zona Norte", zoneSur: "Zona Sur", home: "Casa",
    calendarTitle: "Calendario Diablos", record: "Récord", homeGame: "Local", awayGame: "Visita",
    postponed: "Pospuesto", noGame: "Sin juego", at: "en", vs: "vs",
    diabloHint: "¿Bullpen?", bullpenTitle: "Recomendación de bullpen", nextSeries: "Próxima serie",
    forDate: "Para el", opponentLhb: "Zurdos del rival", closer: "Cerrador", setup: "Preparador",
    middle: "Relevo intermedio", long: "Relevo largo", depth: "Disponible", rest: "Descanso",
    starters: "Abridores", available: "Disponible", limited: "Limitado", unavailable: "No disponibles",
    stuffHere: "Stuff+ aquí", platoon: "Ventaja por mano", workload: "Carga",
    pitches3d: "lanz. 3 días", workloadUnknown: "Sin fechas en los datos: la carga de trabajo no se puede calcular.",
    r_back_to_back: "Lanzó los dos últimos días", r_heavy_yesterday: "{v} lanzamientos ayer",
    r_heavy_3d: "{v} lanzamientos en 3 días", r_pitched_yesterday: "Lanzó ayer ({v})",
    r_busy_3d: "{v} lanzamientos en 3 días", r_starter_in_rotation: "Abridor en rotación",
    r_platoon_plus: "+{v} pts de whiff vs. esta alineación", r_platoon_minus: "{v} pts de whiff vs. esta alineación",
    r_park_plus: "+{v} Stuff+ en este parque", r_park_minus: "{v} Stuff+ en este parque",
    faTitle: "Agentes libres y objetivos", faHint: "Stuff+ proyectado en el Harp Helú, comparado con nuestro staff.",
    faAll: "Todos", faOnly: "Solo agentes libres", faSigned: "En otro equipo", role: "Rol", sp: "Abridor", rp: "Relevista",
    hand: "Mano", right: "Derecho", left: "Zurdo", any: "Cualquiera", sortBy: "Ordenar por",
    sortHome: "Stuff+ en casa", sortNeutral: "Stuff+ neutral", sortFit: "Mejora al staff",
    freeAgent: "Agente libre", onTeam: "En", stuffHome: "Stuff+ Harp Helú", stuffNeutral: "Stuff+ neutral",
    altitudeDelta: "Efecto altitud", fit: "vs. mediana del staff", bestPitch: "Mejor lanzamiento", seeAll: "Ver todos",
    lastSeason: "Última temporada", pitches: "Lanzamientos",
    backToMap: "Mapa", pickPitcher: "Elige un pitcher", pickPitcherHint: "Busca por ID o elige uno del ranking.",
    strikeZoneTitle: "Zona de strike (vista del cátcher)", aimHint: "Haz clic en la zona para cambiar el punto de apunte.",
    seaLevel: "Nivel del mar", here: "Aquí", missBy: "Se desvía {v} in", plateSpeed: "Vel. en home",
    ivb: "Mov. vertical inducido", hb: "Mov. horizontal", usage: "Uso", velo: "Velocidad", spin: "Giro",
    movementTitle: "Movimiento: nivel del mar → este parque", crownTitle: "Ranking del parque",
    crownHint: "Stuff+ proyectado a esta altitud (100 = promedio de la liga en este parque)",
    rank: "#", pitcher: "Pitcher", team: "Equipo", minPitches: "Mín. lanzamientos",
    leagueHere: "Lo que la altitud le hace a cada lanzamiento (promedio de la liga)",
    profileArsenal: "Arsenal", profileLink: "Ver perfil completo", profileByPark: "Stuff+ por parque vs. su promedio (de mayor a menor altitud)", profileWorkload: "Últimas salidas",
    season: "Temporada", status: "Estatus", games: "Juegos", viewInStadium: "Ver en un estadio",
    ours: "Diablos", neutral: "Neutral", bestPark: "Mejor parque", worstPark: "Peor parque", whiff: "Whiff %",
    methodTitle: "Metodología", readPaper: "Leer el paper", paperSoon: "Paper próximamente",
    mPipeline: "Cómo se construye Stuff+", mPipelineText: "Cuatro submodelos predicen, para cada lanzamiento, la probabilidad de swing y fallo, de strike cantado, de rodado y de contacto fuerte a partir solo de sus características físicas (velocidad, giro, movimiento, punto de salida, extensión). Se combinan en un valor por lanzamiento y se escalan a 100 + 10·z, normalizado por temporada y estadio.",
    mNoLocation: "La ubicación del lanzamiento en la zona se excluye: es un resultado, no una característica del lanzamiento.",
    mAltitude: "Física de la altitud", mAltitudeText: "La fuerza Magnus y el arrastre son proporcionales a la densidad del aire. Convertimos cada lanzamiento a su equivalente a nivel del mar y lo proyectamos a la densidad de cualquier parque. La gráfica compara, por estadio, la aceleración por giro medida contra la densidad del aire: si la física se cumple, los puntos caen sobre la diagonal.",
    mElasticity: "Elasticidad medida", mValidation: "Validación", mValidationPending: "Las métricas aparecen aquí cuando el pipeline de entrenamiento escribe validation_metrics.json.",
    mValidationPlan: "GroupKFold por pitcher, holdout temporal por temporada y holdout por categoría de altitud.",
    mData: "Datos", mDataRows: "lanzamientos", mSubmodels: ["Whiff", "Strike cantado", "Rodado", "Contacto fuerte"],
    densityRatio: "Densidad / promedio del pitcher", spinAccelRatio: "Aceleración por giro / promedio del pitcher",
    loading: "Cargando…", error: "No se pudo cargar",
  },
  en: {
    appName: "Diablos Stuff+",
    tagline: "Altitude-adjusted pitch quality for the Mexican League",
    navMap: "Map", navFreeAgents: "Free agents", navMethod: "Methodology",
    syntheticBanner: "Synthetic demo data. Replaced by the real data once it is loaded.",
    placeholderModel: "Placeholder model (not trained)",
    searchPlaceholder: "Search a pitcher ID or a ballpark…",
    searchPitchers: "Pitchers", searchStadiums: "Ballparks", noResults: "No results",
    mapTitle: "The 20 LMB ballparks", mapHint: "Click a ballpark to see how any pitcher plays there.",
    movementLost: "Movement lost vs. sea level", pitchValue: "PITCH VALUE",
    altitude: "Altitude", airDensity: "Air density", movementRetained: "Movement retained",
    vsSeaLevel: "vs. sea level", zoneNorte: "North Zone", zoneSur: "South Zone", home: "Home",
    calendarTitle: "Diablos schedule", record: "Record", homeGame: "Home", awayGame: "Away",
    postponed: "Postponed", noGame: "No game", at: "at", vs: "vs",
    diabloHint: "Bullpen?", bullpenTitle: "Bullpen recommendation", nextSeries: "Next series",
    forDate: "For", opponentLhb: "Opponent lefties", closer: "Closer", setup: "Setup",
    middle: "Middle relief", long: "Long relief", depth: "Available", rest: "Rest",
    starters: "Starters", available: "Available", limited: "Limited", unavailable: "Unavailable",
    stuffHere: "Stuff+ here", platoon: "Platoon edge", workload: "Workload",
    pitches3d: "pitches 3 days", workloadUnknown: "No dates in the data: workload can't be computed.",
    r_back_to_back: "Pitched the last two days", r_heavy_yesterday: "{v} pitches yesterday",
    r_heavy_3d: "{v} pitches in 3 days", r_pitched_yesterday: "Pitched yesterday ({v})",
    r_busy_3d: "{v} pitches in 3 days", r_starter_in_rotation: "Starter in rotation",
    r_platoon_plus: "+{v} whiff pts vs. this lineup", r_platoon_minus: "{v} whiff pts vs. this lineup",
    r_park_plus: "+{v} Stuff+ at this park", r_park_minus: "{v} Stuff+ at this park",
    faTitle: "Free agents & targets", faHint: "Projected Stuff+ at Harp Helú, compared with our staff.",
    faAll: "All", faOnly: "Free agents only", faSigned: "On another team", role: "Role", sp: "Starter", rp: "Reliever",
    hand: "Hand", right: "Right", left: "Left", any: "Any", sortBy: "Sort by",
    sortHome: "Stuff+ at home", sortNeutral: "Neutral Stuff+", sortFit: "Staff upgrade",
    freeAgent: "Free agent", onTeam: "On", stuffHome: "Stuff+ Harp Helú", stuffNeutral: "Neutral Stuff+",
    altitudeDelta: "Altitude effect", fit: "vs. staff median", bestPitch: "Best pitch", seeAll: "See all",
    lastSeason: "Last season", pitches: "Pitches",
    backToMap: "Map", pickPitcher: "Pick a pitcher", pickPitcherHint: "Search by ID or pick one from the ranking.",
    strikeZoneTitle: "Strike zone (catcher's view)", aimHint: "Click the zone to move the aim point.",
    seaLevel: "Sea level", here: "Here", missBy: "Misses by {v} in", plateSpeed: "Plate velo",
    ivb: "Induced vertical break", hb: "Horizontal break", usage: "Usage", velo: "Velocity", spin: "Spin",
    movementTitle: "Movement: sea level → this park", crownTitle: "Ballpark ranking",
    crownHint: "Projected Stuff+ at this altitude (100 = league average at this park)",
    rank: "#", pitcher: "Pitcher", team: "Team", minPitches: "Min. pitches",
    leagueHere: "What altitude does to each pitch (league average)",
    profileArsenal: "Arsenal", profileLink: "Full profile", profileByPark: "Stuff+ by ballpark vs. his average (highest to lowest)", profileWorkload: "Recent outings",
    season: "Season", status: "Status", games: "Games", viewInStadium: "View at a ballpark",
    ours: "Diablos", neutral: "Neutral", bestPark: "Best park", worstPark: "Worst park", whiff: "Whiff %",
    methodTitle: "Methodology", readPaper: "Read the paper", paperSoon: "Paper coming soon",
    mPipeline: "How Stuff+ is built", mPipelineText: "Four sub-models predict, for each pitch, the probability of a swinging strike, a called strike, a ground ball and hard contact from its physical traits only (velocity, spin, movement, release, extension). They combine into a per-pitch value scaled to 100 + 10·z, normalized by season and ballpark.",
    mNoLocation: "Pitch location is excluded: it is an outcome, not a trait of the pitch.",
    mAltitude: "Altitude physics", mAltitudeText: "Magnus force and drag are proportional to air density. We convert every pitch to its sea-level equivalent and project it to any ballpark's density. The chart compares, by ballpark, the measured spin-induced acceleration against air density: if the physics holds, the points sit on the diagonal.",
    mElasticity: "Measured elasticity", mValidation: "Validation", mValidationPending: "Metrics appear here once the training pipeline writes validation_metrics.json.",
    mValidationPlan: "GroupKFold by pitcher, temporal holdout by season, and holdout by altitude category.",
    mData: "Data", mDataRows: "pitches", mSubmodels: ["Whiff", "Called strike", "Ground ball", "Hard contact"],
    densityRatio: "Density / pitcher average", spinAccelRatio: "Spin acceleration / pitcher average",
    loading: "Loading…", error: "Couldn't load",
  },
} as const;

type Dict = typeof dict.es;
export type Key = { [K in keyof Dict]: Dict[K] extends string ? K : never }[keyof Dict];

const LangCtx = createContext<{ lang: Lang; setLang: (l: Lang) => void; t: (k: Key, v?: number | string | null) => string; d: Dict }>(null!);

export function LangProvider({ children }: { children: ReactNode }) {
  const [lang, setLang] = useState<Lang>(() => {
    try { return (localStorage.getItem("lang") as Lang) || "es"; } catch { return "es"; }
  });
  useEffect(() => {
    try { localStorage.setItem("lang", lang); } catch { /* storage unavailable */ }
    document.documentElement.lang = lang;
  }, [lang]);
  const value = useMemo(() => ({
    lang, setLang, d: dict[lang] as Dict,
    t: (k: Key, v?: number | string | null) => (dict[lang][k] as string).replace("{v}", v === undefined || v === null ? "" : String(v)),
  }), [lang]);
  return <LangCtx.Provider value={value}>{children}</LangCtx.Provider>;
}

export const useLang = () => useContext(LangCtx);

export const PITCH_NAMES: Record<Lang, Record<string, string>> = {
  es: { "Four-Seam": "Recta 4 costuras", Sinker: "Sinker", Cutter: "Cutter", Slider: "Slider", Curveball: "Curva", Changeup: "Cambio", Splitter: "Splitter" },
  en: { "Four-Seam": "Four-seam", Sinker: "Sinker", Cutter: "Cutter", Slider: "Slider", Curveball: "Curveball", Changeup: "Changeup", Splitter: "Splitter" },
};
