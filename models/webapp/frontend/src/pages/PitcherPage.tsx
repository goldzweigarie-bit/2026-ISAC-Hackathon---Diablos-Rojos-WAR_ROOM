import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import type { Profile, Stadium } from "../api";
import { PITCH_NAMES, useLang } from "../i18n";
import { PITCH_COLORS, altitudeColor, fmt, stuffColor, useApi, useAppState } from "../state";

export default function PitcherPage() {
  const { id = "" } = useParams();
  const { t, lang } = useLang();
  const navigate = useNavigate();
  const { meta } = useAppState();
  const [season, setSeason] = useState<number | undefined>(undefined);
  const { data, error } = useApi<Profile>(`/pitchers/${id}`, { season });
  const { data: stadiums } = useApi<Stadium[]>("/stadiums");

  if (error) return <main className="page"><div className="empty-state">{t("error")}</div></main>;
  if (!data) return <main className="page"><div className="empty-state">{t("loading")}</div></main>;
  const p = data.pitcher;
  const ours = p.status === meta?.our_team_code;
  const center = p.stuff_neutral ?? 100;
  const spread = Math.max(1, ...data.by_park.map((b) => Math.abs(b.stuff_plus - center)));
  const maxW = Math.max(1, ...data.workload.map((w) => w.pitches));

  return (
    <main className="page">
      <Link to="/" className="muted small">← {t("backToMap")}</Link>
      <section className="stadium-hero" style={{ marginTop: 10 }}>
        <div>
          <div className="eyebrow">{p.role === "SP" ? t("sp") : t("rp")} · {p.throws === "Right" ? t("right") : t("left")}</div>
          <h1 className="num" style={{ fontFamily: "var(--display)" }}>{p.name}</h1>
          <div style={{ display: "flex", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
            {p.status === "FA" ? <span className="chip gold">{t("freeAgent")}</span> : <span className={`chip ${ours ? "red" : ""}`}>{ours ? t("ours") : `${t("onTeam")} ${p.status}`}</span>}
            {p.team_name && <span className="chip">{p.season}: {p.team_name}</span>}
            <span className="chip num">{p.n_pitches} {t("pitches").toLowerCase()}{p.games ? ` · ${p.games} ${t("games").toLowerCase()}` : ""}</span>
          </div>
          <div className="stats-row" style={{ marginTop: 16 }}>
            <div className="stat"><span className="v num" style={{ color: stuffColor(p.stuff_neutral) }}>{fmt(p.stuff_neutral)}</span><span className="l">{t("stuffNeutral")}</span></div>
            <div className="stat"><span className="v num" style={{ color: stuffColor(p.stuff_home) }}>{fmt(p.stuff_home)}</span><span className="l">{t("stuffHome")}</span></div>
          </div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 10, alignItems: "flex-end" }}>
          {p.seasons.length > 1 && (
            <div className="seg">{p.seasons.map((s) => <button key={s} className={p.season === s ? "on" : ""} onClick={() => setSeason(s)}>{s}</button>)}</div>
          )}
          <select className="sel" value="" onChange={(e) => e.target.value && navigate(`/estadio/${e.target.value}?p=${p.pitcher_id}`)}>
            <option value="">{t("viewInStadium")}…</option>
            {stadiums?.map((s) => <option key={s.id} value={s.id}>{s.venue_name} ({s.altitude_m} m)</option>)}
          </select>
        </div>
      </section>

      <section className="panel" style={{ marginBottom: 18 }}>
        <div className="panel-head"><h3>{t("profileArsenal")} {p.season}</h3></div>
        <div className="table-wrap">
          <table className="data">
            <thead><tr>
              <th></th><th className="r">{t("usage")}</th><th className="r">{t("velo")}</th><th className="r">{t("spin")}</th>
              <th className="r">IVB</th><th className="r">HB</th><th className="r">{t("whiff")}</th>
              <th className="r">Stuff+ {t("neutral")}</th><th className="r">{t("bestPark")}</th><th className="r">{t("worstPark")}</th>
            </tr></thead>
            <tbody>
              {data.arsenal.map((a) => (
                <tr key={a.pitch_type}>
                  <td><span style={{ display: "inline-flex", gap: 6, alignItems: "center" }}><span className="dot" style={{ background: PITCH_COLORS[a.pitch_type] }} />{PITCH_NAMES[lang][a.pitch_type]}</span></td>
                  <td className="r num">{fmt(a.usage, 0)}%</td>
                  <td className="r num">{fmt(a.rel_speed)}</td>
                  <td className="r num">{fmt(a.spin_rate, 0)}</td>
                  <td className="r num">{fmt(a.ivb_sea)}</td>
                  <td className="r num">{fmt(a.hb_sea)}</td>
                  <td className="r num">{a.whiff_pct == null ? "–" : `${fmt(a.whiff_pct, 0)}%`}</td>
                  <td className="r num" style={{ color: stuffColor(a.stuff_neutral), fontWeight: 700 }}>{fmt(a.stuff_neutral)}</td>
                  <td className="r num">{fmt(a.stuff_best_park)}</td>
                  <td className="r num">{fmt(a.stuff_worst_park)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="faint tiny">IVB / HB: {t("seaLevel")}, in</p>
        </div>
      </section>

      <div className="stadium-grid">
        <section className="panel">
          <div className="panel-head"><h3>{t("profileByPark")}</h3></div>
          {data.by_park.map((b) => {
            const pct = (v: number) => 50 + ((v - center) / spread) * 48;
            const x100 = 50;
            const xv = pct(b.stuff_plus);
            return (
              <Link to={`/estadio/${b.stadium_id}?p=${p.pitcher_id}`} key={b.stadium_id} className="bar-row">
                <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  <span className="dot" style={{ background: altitudeColor(b.altitude_m), marginRight: 6 }} />{b.team_code} <span className="faint num">{b.altitude_m}m</span>
                </span>
                <div className="bar-track">
                  <div className="bar-fill" style={{ left: `${Math.min(x100, xv)}%`, width: `${Math.abs(xv - x100)}%`, background: b.stuff_plus >= center ? "var(--good)" : "var(--bad)", opacity: 0.8 }} />
                  <div className="bar-mid" style={{ left: `${x100}%` }} />
                </div>
                <span className="num" style={{ textAlign: "right", color: stuffColor(b.stuff_plus) }}>{fmt(b.stuff_plus)}</span>
              </Link>
            );
          })}
        </section>
        <section className="panel">
          <div className="panel-head"><h3>{t("profileWorkload")}</h3></div>
          {data.workload.length === 0 ? <p className="muted small">{t("workloadUnknown")}</p> : (
            <svg viewBox={`0 0 ${data.workload.length * 18} 140`} style={{ width: "100%", height: 180 }} preserveAspectRatio="none" role="img">
              {data.workload.map((w, i) => {
                const h = (w.pitches / maxW) * 110;
                const s = stadiums?.find((x) => x.id === w.stadium_id);
                return (
                  <g key={i}>
                    <rect x={i * 18 + 3} y={120 - h} width={12} height={h} rx={2} fill={s ? altitudeColor(s.altitude_m) : "var(--muted)"}><title>{`${w.date} · ${w.pitches} · ${s?.venue_name ?? ""}`}</title></rect>
                  </g>
                );
              })}
              <line x1="0" x2={data.workload.length * 18} y1="120" y2="120" stroke="var(--line-2)" />
            </svg>
          )}
          {data.workload.length > 0 && <p className="faint tiny">{data.workload[0].date} → {data.workload[data.workload.length - 1].date} · max <span className="num">{maxW}</span></p>}
        </section>
      </div>
    </main>
  );
}
