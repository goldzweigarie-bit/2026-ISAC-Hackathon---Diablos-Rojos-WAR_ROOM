import type { Methodology, Stadium } from "../api";
import { useLang } from "../i18n";
import { altitudeColor, fmt, useApi } from "../state";

function AltitudeChart({ data, stadiums }: { data: Methodology["altitude_study"]; stadiums: Stadium[] }) {
  const { t } = useLang();
  const W = 520, H = 360, P = 48;
  const rows = data.rows;
  const xs = rows.map((r) => r.rho_ratio), ys = rows.map((r) => r.spin_accel_ratio);
  const lo = Math.min(...xs, ...ys) - 0.02, hi = Math.max(...xs, ...ys) + 0.02;
  const sx = (v: number) => P + ((v - lo) / (hi - lo)) * (W - P - 16);
  const sy = (v: number) => H - P - ((v - lo) / (hi - lo)) * (H - P - 16);
  const ticks = Array.from({ length: 5 }, (_, i) => lo + ((hi - lo) * i) / 4);
  const byId = new Map(stadiums.map((s) => [s.id, s]));
  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: "auto" }} role="img" aria-label={t("mAltitude")}>
      {ticks.map((v, i) => (
        <g key={i}>
          <line x1={sx(v)} x2={sx(v)} y1={sy(lo)} y2={sy(hi)} stroke="var(--line)" />
          <line y1={sy(v)} y2={sy(v)} x1={sx(lo)} x2={sx(hi)} stroke="var(--line)" />
          <text x={sx(v)} y={H - P + 18} fontSize="11" textAnchor="middle" fill="var(--faint)" fontFamily="var(--mono)">{v.toFixed(2)}</text>
          <text x={P - 8} y={sy(v) + 4} fontSize="11" textAnchor="end" fill="var(--faint)" fontFamily="var(--mono)">{v.toFixed(2)}</text>
        </g>
      ))}
      <line x1={sx(lo)} y1={sy(lo)} x2={sx(hi)} y2={sy(hi)} stroke="var(--red-2)" strokeDasharray="5 4" strokeWidth="1.5" />
      {rows.map((r) => {
        const s = byId.get(r.group);
        return (
          <g key={r.group}>
            <line x1={sx(r.rho_ratio)} x2={sx(r.rho_ratio)} y1={sy(r.spin_accel_ratio - 2 * r.spin_accel_se)} y2={sy(r.spin_accel_ratio + 2 * r.spin_accel_se)} stroke="var(--muted)" />
            <circle cx={sx(r.rho_ratio)} cy={sy(r.spin_accel_ratio)} r={6} fill={altitudeColor(r.altitude_m)} stroke="#0b0b0d" strokeWidth="1.5"><title>{`${s?.venue_name ?? r.group} · n=${r.n}`}</title></circle>
            <text x={sx(r.rho_ratio) + 8} y={sy(r.spin_accel_ratio) - 6} fontSize="10" fill="var(--muted)" fontFamily="var(--display)">{s?.team_code ?? r.group}</text>
          </g>
        );
      })}
      <text x={W / 2 + 16} y={H - 8} textAnchor="middle" fontSize="12" fill="var(--muted)">{t("densityRatio")}</text>
      <text x={12} y={H / 2} textAnchor="middle" fontSize="12" fill="var(--muted)" transform={`rotate(-90 12 ${H / 2})`}>{t("spinAccelRatio")}</text>
    </svg>
  );
}

export default function MethodologyPage() {
  const { t, d } = useLang();
  const { data } = useApi<Methodology>("/methodology");
  const { data: stadiums } = useApi<Stadium[]>("/stadiums");
  if (!data) return <main className="page"><div className="empty-state">{t("loading")}</div></main>;
  const v = data.validation;

  return (
    <main className="page">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", gap: 16, flexWrap: "wrap" }}>
        <div>
          <div className="eyebrow">Stuff+ · LMB</div>
          <h1>{t("methodTitle")}</h1>
        </div>
        {data.paper_url
          ? <a className="btn primary" href={data.paper_url} target="_blank" rel="noreferrer">{t("readPaper")} ↗</a>
          : <button className="btn" disabled>{t("paperSoon")}</button>}
      </div>

      <div className="method-grid" style={{ marginTop: 18 }}>
        <section className="panel">
          <h2>{t("mPipeline")}</h2>
          <p className="muted">{t("mPipelineText")}</p>
          <svg viewBox="0 0 520 230" style={{ width: "100%", height: "auto" }} role="img" aria-label={t("mPipeline")}>
            {d.mSubmodels.map((name, i) => (
              <g key={name}>
                <rect x="10" y={12 + i * 52} width="170" height="40" rx="9" fill="var(--panel-2)" stroke="var(--line-2)" />
                <text x="95" y={37 + i * 52} textAnchor="middle" fill="var(--text)" fontSize="14" fontFamily="var(--display)" fontWeight="700">{name.toUpperCase()}</text>
                <path d={`M180 ${32 + i * 52} C 240 ${32 + i * 52}, 240 115, 290 115`} fill="none" stroke="var(--line-2)" strokeWidth="1.5" />
              </g>
            ))}
            <rect x="290" y="90" width="110" height="50" rx="10" fill="var(--panel-2)" stroke="var(--muted)" />
            <text x="345" y="112" textAnchor="middle" fill="var(--text)" fontSize="13" fontFamily="var(--display)" fontWeight="700">{t("pitchValue")}</text>
            <text x="345" y="129" textAnchor="middle" fill="var(--muted)" fontSize="11">Σ w·p</text>
            <line x1="400" y1="115" x2="420" y2="115" stroke="var(--muted)" strokeWidth="1.5" />
            <rect x="420" y="84" width="92" height="62" rx="10" fill="var(--red)" />
            <text x="466" y="112" textAnchor="middle" fill="white" fontSize="20" fontFamily="var(--display)" fontWeight="800">STUFF+</text>
            <text x="466" y="131" textAnchor="middle" fill="white" fontSize="11">100 + 10·z</text>
          </svg>
          <p className="chip red" style={{ whiteSpace: "normal" }}>{t("mNoLocation")}</p>
        </section>

        <section className="panel">
          <h2>{t("mAltitude")}</h2>
          <p className="muted">{t("mAltitudeText")}</p>
          {data.altitude_study.rows.length > 0 && stadiums && <AltitudeChart data={data.altitude_study} stadiums={stadiums} />}
          {data.altitude_study.elasticity_spin_vs_density != null && (
            <div className="stat" style={{ marginTop: 8 }}>
              <span className="v num">{fmt(data.altitude_study.elasticity_spin_vs_density, 2)}</span>
              <span className="l">{t("mElasticity")}</span>
            </div>
          )}
        </section>

        <section className="panel">
          <h2>{t("mValidation")}</h2>
          <p className="muted">{t("mValidationPlan")}</p>
          {!v && <p className="chip gold" style={{ whiteSpace: "normal" }}>{t("mValidationPending")}</p>}
          {v?.metrics && (
            <table className="data"><tbody>
              {v.metrics.map((m, i) => <tr key={i}><td>{m.name}</td><td className="muted">{m.split ?? ""}</td><td className="r num">{m.value}</td></tr>)}
            </tbody></table>
          )}
          {v?.submodels && (
            <table className="data" style={{ marginTop: 10 }}><tbody>
              {v.submodels.map((m, i) => <tr key={i}><td>{m.name}</td><td className="muted">{m.target}</td><td>{m.metric}</td><td className="r num">{m.value}</td></tr>)}
            </tbody></table>
          )}
          {v?.notes && <p className="muted small">{v.notes}</p>}
        </section>

        <section className="panel">
          <h2>{t("mData")}</h2>
          <div className="stats-row" style={{ marginTop: 10 }}>
            <div className="stat"><span className="v num">{data.data.rows?.toLocaleString()}</span><span className="l">{t("mDataRows")}</span></div>
            <div className="stat"><span className="v num">{data.data.seasons?.join(", ")}</span><span className="l">{t("season")}</span></div>
          </div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 12 }}>
            {Object.entries(data.data.capabilities ?? {}).map(([k, ok]) => <span key={k} className={`chip ${ok ? "good" : "bad"}`}>{ok ? "✓" : "✗"} {k.replace("has_", "")}</span>)}
            {data.data.synthetic && <span className="chip gold">synthetic</span>}
            <span className="chip">model: {data.model}</span>
          </div>
        </section>
      </div>
    </main>
  );
}
