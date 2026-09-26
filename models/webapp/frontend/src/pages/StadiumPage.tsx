import { useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import type { LeaderRow, Projection, StadiumDetail } from "../api";
import { CrownIcon, Leaderboard } from "../components/Leaderboard";
import { MovementPlot } from "../components/MovementPlot";
import { SearchBox } from "../components/SearchBox";
import { StrikeZone } from "../components/StrikeZone";
import { PITCH_NAMES, useLang } from "../i18n";
import { PITCH_COLORS, altitudeColor, fmt, signed, stuffColor, useApi } from "../state";

export default function StadiumPage() {
  const { id = "" } = useParams();
  const { t, lang } = useLang();
  const [params, setParams] = useSearchParams();
  const pid = params.get("p");
  const [aim, setAim] = useState({ x: 0, z: 2.5 });
  const [crown, setCrown] = useState(false);
  const { data: st, error } = useApi<StadiumDetail>(`/stadiums/${id}`);
  const { data: top } = useApi<{ rows: LeaderRow[] }>(`/stadiums/${id}/leaderboard`, { limit: 6 });
  const { data: proj, loading } = useApi<Projection>(pid ? `/stadiums/${id}/pitchers/${pid}` : null, { aim_x: aim.x, aim_z: aim.z });
  const [visible, setVisible] = useState<Set<string>>(new Set());
  const projPid = proj?.pitcher.pitcher_id;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { if (proj) setVisible(new Set(proj.pitches.map((p) => p.pitch_type))); }, [projPid]);
  const pickPitcher = (p: string) => setParams({ p });
  const maxAbs = useMemo(() => Math.max(1, ...(st?.league_by_pitch_type ?? []).map((r) => Math.max(r.ivb_sea, r.hb_sea))), [st]);

  if (error) return <main className="page"><div className="empty-state">{t("error")}</div></main>;
  if (!st) return <main className="page"><div className="empty-state">{t("loading")}</div></main>;
  const toggle = (pt: string) => setVisible((v) => { const n = new Set(v); if (n.has(pt)) n.delete(pt); else n.add(pt); return n; });

  return (
    <main className="page">
      <Link to="/" className="muted small">← {t("backToMap")}</Link>
      <section className="stadium-hero" style={{ marginTop: 10 }}>
        <div>
          <div className="eyebrow">{st.team_name} · {st.zone === "Norte" ? t("zoneNorte") : t("zoneSur")}</div>
          <h1>{st.venue_name}</h1>
          <div className="muted" style={{ marginTop: 4 }}>{st.city}, {st.state}</div>
          <div className="stats-row" style={{ marginTop: 16 }}>
            <div className="stat"><span className="v num" style={{ color: altitudeColor(st.altitude_m) }}>{st.altitude_m.toLocaleString()} m</span><span className="l">{t("altitude")}</span></div>
            <div className="stat"><span className="v num">{fmt(st.air_density, 3)}</span><span className="l">{t("airDensity")} kg/m³</span></div>
            <div className="stat"><span className="v num">{fmt(st.movement_retained_pct, 0)}%</span><span className="l">{t("movementRetained")} {t("vsSeaLevel")}</span></div>
          </div>
        </div>
        <button className="crown-btn" onClick={() => setCrown(true)}><CrownIcon size={26} /> {t("crownTitle")}</button>
      </section>

      <section className="panel" style={{ marginBottom: 18 }}>
        <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 420px) 1fr", gap: 18, alignItems: "center" }} className="picker-grid">
          <SearchBox pitchersOnly onPickPitcher={pickPitcher} placeholder={t("pickPitcher") + "…"} />
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
            <CrownIcon size={16} />
            {top?.rows.map((r) => (
              <button key={r.pitcher_id} className={`chip ${pid === r.pitcher_id ? "red" : ""}`} onClick={() => pickPitcher(r.pitcher_id)} style={{ cursor: "pointer" }}>
                <span className="num">{r.name}</span> <span className="num" style={{ color: stuffColor(r.stuff_plus) }}>{fmt(r.stuff_plus, 0)}</span>
              </button>
            ))}
          </div>
        </div>
      </section>

      {!pid && <div className="panel empty-state"><h2>{t("pickPitcher")}</h2><p>{t("pickPitcherHint")}</p></div>}
      {pid && loading && !proj && <div className="panel empty-state">{t("loading")}</div>}
      {pid && proj && (
        <>
          <section className="panel" style={{ marginBottom: 18, display: "flex", gap: 24, alignItems: "center", flexWrap: "wrap" }}>
            <div style={{ flex: 1, minWidth: 220 }}>
              <div className="eyebrow">{proj.pitcher.team_name ?? t("freeAgent")} · {proj.pitcher.role === "SP" ? t("sp") : t("rp")} · {proj.pitcher.throws === "Right" ? t("right") : t("left")}</div>
              <h2 style={{ fontSize: 30 }}><span className="num" style={{ fontFamily: "var(--display)" }}>{proj.pitcher.name}</span></h2>
              <Link to={`/lanzador/${pid}`} className="muted small" style={{ textDecoration: "underline" }}>{t("profileLink")} →</Link>
            </div>
            <div className="stats-row">
              <div className="stat"><span className="v num" style={{ color: stuffColor(proj.pitcher.stuff_here) }}>{fmt(proj.pitcher.stuff_here)}</span><span className="l">Stuff+ {t("here")}</span></div>
              <div className="stat"><span className="v num muted">{fmt(proj.pitcher.stuff_sea)}</span><span className="l">Stuff+ {t("seaLevel")}</span></div>
            </div>
          </section>

          <div className="pt-legend" style={{ marginBottom: 10 }}>
            {proj.pitches.map((p) => (
              <button key={p.pitch_type} className={visible.has(p.pitch_type) ? "on" : ""} onClick={() => toggle(p.pitch_type)}>
                <span className="dot" style={{ background: PITCH_COLORS[p.pitch_type] }} /> {PITCH_NAMES[lang][p.pitch_type]} <span className="faint num">{fmt(p.usage, 0)}%</span>
              </button>
            ))}
          </div>

          <div className="stadium-grid">
            <section className="panel">
              <div className="panel-head"><h3>{t("strikeZoneTitle")}</h3><span className="faint tiny">{t("aimHint")}</span></div>
              <StrikeZone pitches={proj.pitches} visible={visible} aim={aim} onAim={(x, z) => setAim({ x, z })} labels={{ sea: t("seaLevel"), here: st.venue_name }} />
            </section>
            <section className="panel">
              <div className="panel-head"><h3>{t("movementTitle")}</h3></div>
              <MovementPlot pitches={proj.pitches} visible={visible} xLabel={t("hb")} yLabel={t("ivb")} />
              <div className="table-wrap" style={{ marginTop: 10 }}>
                <table className="data">
                  <thead><tr>
                    <th></th><th className="r">{t("velo")}</th><th className="r">IVB</th><th className="r">HB</th>
                    <th className="r">{t("plateSpeed")}</th><th className="r">Stuff+</th>
                  </tr></thead>
                  <tbody>
                    {proj.pitches.filter((p) => visible.has(p.pitch_type)).map((p) => (
                      <tr key={p.pitch_type}>
                        <td><span style={{ display: "inline-flex", gap: 6, alignItems: "center" }}><span className="dot" style={{ background: PITCH_COLORS[p.pitch_type] }} />{PITCH_NAMES[lang][p.pitch_type]}</span>
                          <div className="faint tiny">{t("missBy", fmt(p.miss_inches))}</div></td>
                        <td className="r num">{fmt(p.rel_speed)}</td>
                        <td className="r num">{fmt(p.here.ivb)}<div className="faint tiny">{fmt(p.sea.ivb)}</div></td>
                        <td className="r num">{fmt(p.here.hb)}<div className="faint tiny">{fmt(p.sea.hb)}</div></td>
                        <td className="r num">{fmt(p.here.plate_speed)}<div className="faint tiny">{fmt(p.sea.plate_speed)}</div></td>
                        <td className="r num" style={{ color: stuffColor(p.here.stuff_plus), fontWeight: 700 }}>{fmt(p.here.stuff_plus)}
                          <div className="tiny" style={{ color: p.here.stuff_plus - p.sea.stuff_plus >= 0 ? "var(--good)" : "var(--bad)", fontWeight: 400 }}>{signed(p.here.stuff_plus - p.sea.stuff_plus)}</div></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <p className="faint tiny">{t("here")} / <span>{t("seaLevel")}</span> · in, mph</p>
              </div>
            </section>
          </div>
        </>
      )}

      <section className="panel" style={{ marginTop: 18 }}>
        <div className="panel-head"><h3>{t("leagueHere")}</h3><span className="faint tiny">IVB · HB (in)</span></div>
        {st.league_by_pitch_type.map((r) => (
          <div key={r.pitch_type}>
            {(["ivb", "hb"] as const).map((k) => {
              const sea = k === "ivb" ? r.ivb_sea : r.hb_sea;
              const here = k === "ivb" ? r.ivb_here : r.hb_here;
              return (
                <div className="bar-row" key={k}>
                  <span style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{k === "ivb" ? <><span className="dot" style={{ background: PITCH_COLORS[r.pitch_type], marginRight: 6 }} />{PITCH_NAMES[lang][r.pitch_type]} <span className="faint">IVB</span></> : <span className="faint" style={{ paddingLeft: 16 }}>HB</span>}</span>
                  <div className="bar-track">
                    <div className="bar-fill" style={{ left: "50%", width: `${(Math.abs(sea) / maxAbs) * 50}%`, background: "transparent", border: `1px dashed ${PITCH_COLORS[r.pitch_type]}`, transform: sea < 0 ? "translateX(-100%)" : undefined }} />
                    <div className="bar-fill" style={{ left: "50%", width: `${(Math.abs(here) / maxAbs) * 50}%`, background: PITCH_COLORS[r.pitch_type], opacity: 0.85, transform: here < 0 ? "translateX(-100%)" : undefined }} />
                    <div className="bar-mid" style={{ left: "50%" }} />
                  </div>
                  <span className="num r" style={{ textAlign: "right" }}>{fmt(here)}<span className="faint">/{fmt(sea)}</span></span>
                </div>
              );
            })}
          </div>
        ))}
      </section>

      {crown && <Leaderboard stadiumId={id} venueName={st.venue_name} onClose={() => setCrown(false)} />}
    </main>
  );
}
