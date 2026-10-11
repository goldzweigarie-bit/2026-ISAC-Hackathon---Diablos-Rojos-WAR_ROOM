import { useState } from "react";
import { useNavigate } from "react-router-dom";
import type { LeaderRow } from "../api";
import { PITCH_NAMES, useLang } from "../i18n";
import { PITCH_COLORS, fmt, signed, stuffColor, useApi, useAppState } from "../state";

type Board = { stadium_id: string; season: number; min_pitches: number; total: number; rows: LeaderRow[] };

export function CrownIcon({ size = 22 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <path d="M3 8 L7.5 12 L12 5 L16.5 12 L21 8 L19 18 H5 Z" fill="var(--gold)" stroke="#7a5a16" strokeWidth="1" strokeLinejoin="round" />
      <rect x="5" y="19" width="14" height="2.2" rx="1" fill="var(--gold)" />
      <circle cx="12" cy="5" r="1.4" fill="#fff4d6" /><circle cx="3" cy="8" r="1.2" fill="#fff4d6" /><circle cx="21" cy="8" r="1.2" fill="#fff4d6" />
    </svg>
  );
}

export function Leaderboard({ stadiumId, venueName, onPick, onClose }: { stadiumId: string; venueName: string; onPick?: (id: string) => void; onClose: () => void }) {
  const { t, lang } = useLang();
  const navigate = useNavigate();
  const [role, setRole] = useState<"" | "SP" | "RP">("");
  const { data } = useApi<Board>(`/stadiums/${stadiumId}/leaderboard`, { role, limit: 100 });
  const ourTeam = useAppState().meta?.our_team_code ?? "MEX";

  return (
    <>
      <div className="drawer-scrim" onClick={onClose} />
      <aside className="drawer" style={{ width: "min(860px, 100vw)" }} role="dialog" aria-label={t("crownTitle")}>
        <button className="drawer-close" onClick={onClose} aria-label="close">✕</button>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <CrownIcon size={40} />
          <div>
            <div className="eyebrow" style={{ color: "var(--gold)" }}>{t("crownTitle")}</div>
            <h2 style={{ fontSize: 26 }}>{venueName}</h2>
          </div>
        </div>
        <p className="muted small">{t("crownHint")}</p>
        <div className="seg" style={{ marginBottom: 10 }}>
          {(["", "SP", "RP"] as const).map((r) => <button key={r} className={role === r ? "on" : ""} onClick={() => setRole(r)}>{r === "" ? t("any") : r === "SP" ? t("sp") : t("rp")}</button>)}
        </div>
        <div className="table-wrap">
          <table className="data">
            <thead><tr>
              <th>{t("rank")}</th><th>{t("pitcher")}</th><th>{t("team")}</th><th>{t("bestPitch")}</th>
              <th className="r">Stuff+</th><th className="r">{t("neutral")}</th><th className="r">{t("altitudeDelta")}</th>
            </tr></thead>
            <tbody>
              {data?.rows.map((r) => (
                <tr key={r.pitcher_id} className="clickable" onClick={() => (onPick ? onPick(r.pitcher_id) : navigate(`/lanzador/${r.pitcher_id}`))}
                  style={r.status === ourTeam ? { background: "rgba(213,16,47,0.10)" } : undefined}>
                  <td className="num" style={{ color: r.rank <= 3 ? "var(--gold)" : "var(--muted)", fontWeight: 700 }}>{r.rank}</td>
                  <td><span className="num" style={{ fontWeight: 600 }}>{r.name}</span> <span className="faint small">{r.throws === "Right" ? "R" : "L"} · {r.role}</span></td>
                  <td>{r.status === "FA" ? <span className="chip gold">{t("freeAgent")}</span> : <span className={`chip ${r.status === ourTeam ? "red" : ""}`}>{r.status}</span>}</td>
                  <td>{r.best_pitch && <span style={{ display: "inline-flex", gap: 6, alignItems: "center" }}><span className="dot" style={{ background: PITCH_COLORS[r.best_pitch] }} />{PITCH_NAMES[lang][r.best_pitch]}</span>}</td>
                  <td className="r num" style={{ color: stuffColor(r.stuff_plus), fontWeight: 700 }}>{fmt(r.stuff_plus)}</td>
                  <td className="r num muted">{fmt(r.stuff_neutral)}</td>
                  <td className="r num" style={{ color: r.altitude_delta >= 0 ? "var(--good)" : "var(--bad)" }}>{signed(r.altitude_delta)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {data && <p className="faint small">{t("minPitches")}: {data.min_pitches} · {data.total}</p>}
      </aside>
    </>
  );
}
