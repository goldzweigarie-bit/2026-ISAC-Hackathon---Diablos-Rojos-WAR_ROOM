import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import type { FreeAgents } from "../api";
import { PITCH_NAMES, useLang } from "../i18n";
import { PITCH_COLORS, fmt, signed, stuffColor, useApi, useAppState } from "../state";

export function FreeAgentTable({ compact = false }: { compact?: boolean }) {
  const { t, lang } = useLang();
  const navigate = useNavigate();
  const { meta } = useAppState();
  const teamsKnown = meta?.capabilities?.has_teams !== false || meta?.has_rosters === true;
  const [pickedStatus, setStatus] = useState<"fa" | "signed" | "all">(compact ? "fa" : "all");
  const status = teamsKnown ? pickedStatus : "all";   // sin equipos no hay forma de filtrar agentes libres
  const [role, setRole] = useState<"" | "SP" | "RP">("");
  const [throws, setThrows] = useState<"" | "Right" | "Left">("");
  const [sort, setSort] = useState<"home" | "neutral" | "fit">("home");
  const { data, loading } = useApi<FreeAgents>("/free-agents", { status, role, throws, sort, limit: compact ? 6 : 100 });

  return (
    <div className={compact ? "panel" : ""}>
      {compact && (
        <div className="panel-head">
          <div>
            <div className="eyebrow">{t("faTitle")}</div>
            <div className="muted small">{t("faHint")}</div>
          </div>
          <Link to="/agentes-libres" className="btn" style={{ padding: "5px 10px", fontSize: 13 }}>{t("seeAll")} →</Link>
        </div>
      )}
      {!teamsKnown && <div className="muted small" style={{ marginBottom: 10 }}>{t("faNoTeams")}</div>}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 10 }}>
        <div className="seg" style={teamsKnown ? undefined : { display: "none" }}>
          {(["fa", "signed", "all"] as const).map((s) => (
            <button key={s} className={status === s ? "on" : ""} onClick={() => setStatus(s)}>{s === "fa" ? t("faOnly") : s === "signed" ? t("faSigned") : t("faAll")}</button>
          ))}
        </div>
        <div className="seg">
          {(["", "SP", "RP"] as const).map((r) => <button key={r} className={role === r ? "on" : ""} onClick={() => setRole(r)}>{r === "" ? t("any") : r === "SP" ? t("sp") : t("rp")}</button>)}
        </div>
        {!compact && (
          <>
            <div className="seg">
              {(["", "Right", "Left"] as const).map((h) => <button key={h} className={throws === h ? "on" : ""} onClick={() => setThrows(h)}>{h === "" ? t("any") : h === "Right" ? t("right") : t("left")}</button>)}
            </div>
            <label className="muted small" style={{ display: "flex", alignItems: "center", gap: 6 }}>{t("sortBy")}
              <select className="sel" value={sort} onChange={(e) => setSort(e.target.value as typeof sort)}>
                <option value="home">{t("sortHome")}</option>
                <option value="neutral">{t("sortNeutral")}</option>
                <option value="fit">{t("sortFit")}</option>
              </select>
            </label>
          </>
        )}
      </div>
      <div className="table-wrap">
        <table className="data">
          <thead>
            <tr>
              <th>{t("pitcher")}</th>
              <th>{t("status")}</th>
              {!compact && <th>{t("role")}</th>}
              <th className="r">{t("stuffHome")}</th>
              {!compact && <th className="r">{t("stuffNeutral")}</th>}
              {!compact && <th className="r">{t("altitudeDelta")}</th>}
              <th className="r">{compact ? "Δ staff" : t("fit")}</th>
              {!compact && <th>{t("bestPitch")}</th>}
              {!compact && <th className="r">{t("lastSeason")}</th>}
            </tr>
          </thead>
          <tbody>
            {data?.rows.map((r) => (
              <tr key={r.pitcher_id} className="clickable" onClick={() => navigate(`/lanzador/${r.pitcher_id}`)}>
                <td><span className="num" style={{ fontWeight: 600 }}>{r.name}</span> <span className="faint small">{r.throws === "Right" ? "R" : "L"}{compact ? ` · ${r.role}` : ""}</span></td>
                <td>{r.status === "FA" ? <span className="chip gold">{t("freeAgent")}</span> : r.status === "?" ? <span className="chip">{t("teamUnknown")}</span> : <span className="chip" title={r.team_name ?? ""}>{t("onTeam")} {r.status}</span>}</td>
                {!compact && <td>{r.role === "SP" ? t("sp") : t("rp")}</td>}
                <td className="r num" style={{ color: stuffColor(r.stuff_home), fontWeight: 700 }}>{fmt(r.stuff_home)}</td>
                {!compact && <td className="r num">{fmt(r.stuff_neutral)}</td>}
                {!compact && <td className="r num" style={{ color: r.altitude_delta >= 0 ? "var(--good)" : "var(--bad)" }}>{signed(r.altitude_delta)}</td>}
                <td className="r num" style={{ color: (r.fit ?? 0) >= 0 ? "var(--good)" : "var(--bad)" }}>{signed(r.fit)}</td>
                {!compact && <td>{r.best_pitch && <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}><span className="dot" style={{ background: PITCH_COLORS[r.best_pitch] }} />{PITCH_NAMES[lang][r.best_pitch]} <span className="num faint">{fmt(r.best_pitch_stuff)}</span></span>}</td>}
                {!compact && <td className="r num">{r.last_season}</td>}
              </tr>
            ))}
          </tbody>
        </table>
        {loading && !data && <p className="muted">{t("loading")}</p>}
      </div>
      {!compact && data && <p className="faint small">{data.total} · {t("fit")}: {t("sp")} {fmt(data.our_medians.SP)} · {t("rp")} {fmt(data.our_medians.RP)}</p>}
    </div>
  );
}
