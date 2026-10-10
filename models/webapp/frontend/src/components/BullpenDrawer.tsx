import { Link } from "react-router-dom";
import type { Bullpen, Reliever } from "../api";
import { useLang, type Key } from "../i18n";
import { altitudeColor, fmt, signed, stuffColor, useApi, useAppState } from "../state";
import { Diablo } from "./Diablo";

const SLOT_ORDER = ["closer", "setup", "middle", "long", "depth"] as const;

export function BullpenDrawer({ onClose }: { onClose: () => void }) {
  const { t } = useLang();
  const { selectedDate, setSelectedDate } = useAppState();
  const { data, loading, error } = useApi<Bullpen>("/bullpen", { on: selectedDate ?? undefined });

  return (
    <>
      <div className="drawer-scrim" onClick={onClose} />
      <aside className="drawer" role="dialog" aria-label={t("bullpenTitle")}>
        <button className="drawer-close" onClick={onClose} aria-label="close">✕</button>
        <div style={{ display: "flex", gap: 14, alignItems: "center" }}>
          <Diablo size={56} still />
          <div>
            <div className="eyebrow">{t("bullpenTitle")}</div>
            <h2 style={{ fontSize: 26 }}>{data?.available ? `${data.games[0]?.home ? t("vs") : "@"} ${data.opponent_name}` : "…"}</h2>
          </div>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center", margin: "14px 0 4px", flexWrap: "wrap" }}>
          <label className="muted small">{t("forDate")}{" "}
            <input type="date" className="sel" value={selectedDate ?? ""} onChange={(e) => setSelectedDate(e.target.value || null)} />
          </label>
          {data?.available && data.games.map((g, i) => <span key={i} className="chip num">{g.date.slice(5)}</span>)}
        </div>
        {loading && <p className="muted">{t("loading")}</p>}
        {error && <p className="muted">{t("error")}</p>}
        {data?.available && (
          <>
            <Link to={`/estadio/${data.stadium.id}`} onClick={onClose} className="panel" style={{ display: "flex", gap: 18, padding: 12, marginTop: 10, alignItems: "center" }}>
              <span className="dot" style={{ width: 14, height: 14, background: altitudeColor(data.stadium.altitude_m) }} />
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600 }}>{data.stadium.venue_name}</div>
                <div className="muted small"><span className="num">{data.stadium.altitude_m.toLocaleString()} m</span> · {t("movementRetained")} <span className="num">{fmt(data.stadium.movement_retained_pct, 0)}%</span></div>
              </div>
              {data.opponent_lhb_share != null && <div className="stat" style={{ textAlign: "right" }}><span className="v num" style={{ fontSize: 20 }}>{fmt(data.opponent_lhb_share, 0)}%</span><span className="l">{t("opponentLhb")}</span></div>}
            </Link>
            {!data.workload_known && <p className="chip gold" style={{ marginTop: 10 }}>{t("workloadUnknown")}</p>}
            {data.relievers.length === 0 && data.starters.length === 0 && <p className="muted" style={{ marginTop: 14 }}>{t("noStaff")}</p>}
            {SLOT_ORDER.map((slot) => {
              const rows = data.relievers.filter((r) => r.slot === slot);
              if (!rows.length) return null;
              return (
                <div className="slot" key={slot}>
                  <div className="slot-title">{t(slot as Key)}</div>
                  {rows.map((r) => <RelieverCard key={r.pitcher_id} r={r} slot={slot} onNavigate={onClose} />)}
                </div>
              );
            })}
            {data.relievers.some((r) => r.slot === "rest") && (
              <div className="slot">
                <div className="slot-title">{t("unavailable")}</div>
                {data.relievers.filter((r) => r.slot === "rest").map((r) => <RelieverCard key={r.pitcher_id} r={r} slot="rest" onNavigate={onClose} />)}
              </div>
            )}
          </>
        )}
      </aside>
    </>
  );
}

function RelieverCard({ r, slot, onNavigate }: { r: Reliever; slot: string; onNavigate: () => void }) {
  const { t } = useLang();
  return (
    <div className={`rp-card ${slot === "closer" ? "closer" : ""}`} style={slot === "rest" ? { opacity: 0.65 } : undefined}>
      <div>
        <Link to={`/lanzador/${r.pitcher_id}`} onClick={onNavigate} className="num" style={{ fontWeight: 600 }}>{r.name}</Link>{" "}
        <span className="chip">{r.throws === "Right" ? "R" : "L"}HP</span>{" "}
        {r.status === "limited" && <span className="chip gold">{t("limited")}</span>}
      </div>
      <div style={{ textAlign: "right" }}>
        <span className="num" style={{ fontWeight: 700, color: stuffColor(r.stuff_here), fontSize: 18 }}>{fmt(r.stuff_here)}</span>
        <span className="muted tiny"> {t("stuffHere")}</span>
      </div>
      <div className="muted tiny">
        {t("platoon")} <span className="num">{signed(r.platoon_edge)}</span> · <span className="num">{r.pitches_last_3d}</span> {t("pitches3d")}
      </div>
      <div />
      {r.reasons.length > 0 && (
        <div className="reasons">
          {r.reasons.map((x, i) => {
            const good = x.code.endsWith("_plus");
            const bad = x.code.endsWith("_minus") || ["back_to_back", "heavy_yesterday", "heavy_3d", "starter_in_rotation"].includes(x.code);
            return <span key={i} className={`chip ${good ? "good" : bad ? "bad" : "gold"}`}>{t(`r_${x.code}` as Key, x.value)}</span>;
          })}
        </div>
      )}
    </div>
  );
}
