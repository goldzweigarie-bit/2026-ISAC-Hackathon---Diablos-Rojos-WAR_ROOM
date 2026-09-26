import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api, type Meta } from "./api";

export const PITCH_COLORS: Record<string, string> = {
  "Four-Seam": "#ff4d5e", Sinker: "#ff9f43", Cutter: "#c08a6a", Slider: "#ffd23f",
  Curveball: "#45c4f0", Changeup: "#2fd39a", Splitter: "#b58cff",
};

/** Sea level -> high altitude, cool to hot. */
export function altitudeColor(alt: number): string {
  const stops: [number, [number, number, number]][] = [
    [0, [69, 196, 240]], [800, [120, 200, 160]], [1500, [255, 196, 64]], [2250, [230, 30, 50]],
  ];
  let i = 0;
  while (i < stops.length - 2 && alt > stops[i + 1][0]) i++;
  const [a0, c0] = stops[i];
  const [a1, c1] = stops[i + 1];
  const f = Math.max(0, Math.min(1, (alt - a0) / (a1 - a0)));
  const c = c0.map((v, j) => Math.round(v + f * (c1[j] - v)));
  return `rgb(${c[0]},${c[1]},${c[2]})`;
}

export function stuffColor(v: number | null | undefined): string {
  if (v == null) return "var(--muted)";
  if (v >= 110) return "var(--good-strong)";
  if (v >= 103) return "var(--good)";
  if (v <= 90) return "var(--bad-strong)";
  if (v <= 97) return "var(--bad)";
  return "var(--text)";
}

export const fmt = (v: number | null | undefined, d = 1) => (v == null ? "–" : v.toFixed(d));
export const signed = (v: number | null | undefined, d = 1) => (v == null ? "–" : `${v > 0 ? "+" : ""}${v.toFixed(d)}`);

export function useApi<T>(path: string | null, params?: Record<string, string | number | undefined | null>) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const key = path ? path + JSON.stringify(params ?? {}) : null;
  useEffect(() => {
    if (!path) { setData(null); return; }
    let alive = true;
    setLoading(true);
    setError(null);
    api<T>(path, params)
      .then((d) => { if (alive) setData(d); })
      .catch((e) => { if (alive) setError(String(e)); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return { data, error, loading };
}

type AppState = {
  meta: Meta | null;
  selectedDate: string | null;
  setSelectedDate: (d: string | null) => void;
  bullpenOpen: boolean;
  setBullpenOpen: (o: boolean) => void;
};
const Ctx = createContext<AppState>(null!);

export function AppStateProvider({ children }: { children: ReactNode }) {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [bullpenOpen, setBullpenOpen] = useState(false);
  useEffect(() => { api<Meta>("/meta").then(setMeta).catch(() => setMeta(null)); }, []);
  return <Ctx.Provider value={{ meta, selectedDate, setSelectedDate, bullpenOpen, setBullpenOpen }}>{children}</Ctx.Provider>;
}
export const useAppState = () => useContext(Ctx);
