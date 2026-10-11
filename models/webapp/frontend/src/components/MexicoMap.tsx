import { useMemo, useState } from "react";
import { geoMercator, geoPath } from "d3-geo";
import type { FeatureCollection } from "geojson";
import { useNavigate } from "react-router-dom";
import mexico from "../mexico-states.json";
import type { Stadium } from "../api";
import { useLang } from "../i18n";
import { altitudeColor, fmt } from "../state";

const W = 960;
const H = 640;
// label nudges for the crowded Bajío / centre cluster: [dx, dy, anchor]
const LABEL: Record<string, [number, number, "start" | "end" | "middle"]> = {
  "harp-helu": [-11, 16, "end"], "hermanos-serdan": [11, 12, "start"], "conspiradores": [8, -8, "start"],
  "domingo-santana": [-10, -6, "end"], "romo-chavez": [0, -12, "middle"], "panamericano": [-11, 4, "end"],
  "yuva": [10, 12, "start"], "francisco-villa": [-11, 4, "end"], "revolucion": [10, 4, "start"],
  "francisco-madero": [10, 12, "start"], "monterrey": [10, 2, "start"], "monclova": [-10, -6, "end"],
  "beto-avila-veracruz": [10, 4, "start"],
};

export function MexicoMap({ stadiums, highlightId }: { stadiums: Stadium[]; highlightId?: string | null }) {
  const { t } = useLang();
  const navigate = useNavigate();
  const [hover, setHover] = useState<Stadium | null>(null);
  const { path, project } = useMemo(() => {
    const fc = mexico as unknown as FeatureCollection;
    const proj = geoMercator().fitExtent([[10, 10], [W - 10, H - 10]], fc);
    return { path: geoPath(proj), project: (lon: number, lat: number) => proj([lon, lat]) ?? [0, 0] };
  }, []);
  const features = (mexico as unknown as FeatureCollection).features;
  const sorted = [...stadiums].sort((a, b) => a.altitude_m - b.altitude_m);
  const hp = hover ? project(hover.lon, hover.lat) : null;

  return (
    <div className="map-wrap">
      <svg className="map-svg" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={t("mapTitle")}>
        <g>{features.map((f, i) => <path key={i} className="state" d={path(f) ?? ""} />)}</g>
        {sorted.map((s) => {
          const [x, y] = project(s.lon, s.lat);
          const [dx, dy, anchor] = LABEL[s.id] ?? [10, 4, "start"];
          const color = altitudeColor(s.altitude_m);
          return (
            <g key={s.id}>
              {s.is_home && <circle cx={x} cy={y} r={15} fill="none" stroke="var(--red-2)" strokeWidth={2} opacity={0.8}>
                <animate attributeName="r" values="11;19;11" dur="2.4s" repeatCount="indefinite" />
                <animate attributeName="opacity" values="0.9;0.1;0.9" dur="2.4s" repeatCount="indefinite" />
              </circle>}
              {highlightId === s.id && !s.is_home && <circle cx={x} cy={y} r={14} fill="none" stroke="var(--chalk)" strokeWidth={1.5} strokeDasharray="3 3" />}
              <circle
                className={`stadium ${hover?.id === s.id || highlightId === s.id ? "hl" : ""}`}
                cx={x} cy={y} r={s.is_home ? 9 : 7} fill={color} stroke="#0b0b0d" strokeWidth={2}
                tabIndex={0} role="link" aria-label={`${s.venue_name}, ${s.altitude_m} m`}
                onMouseEnter={() => setHover(s)} onMouseLeave={() => setHover(null)}
                onFocus={() => setHover(s)} onBlur={() => setHover(null)}
                onClick={() => navigate(`/estadio/${s.id}`)}
                onKeyDown={(e) => { if (e.key === "Enter") navigate(`/estadio/${s.id}`); }}
              />
              <text className={`label ${s.is_home || hover?.id === s.id ? "strong" : ""}`} x={x + dx} y={y + dy} textAnchor={anchor}>{s.team_code}</text>
            </g>
          );
        })}
      </svg>
      {hover && hp && (
        <div className="map-tip" style={{ left: `${(hp[0] / W) * 100}%`, top: `${(hp[1] / H) * 100}%`, transform: `translate(${hp[0] > W * 0.6 ? "-105%" : "14px"}, -50%)` }}>
          <div className="eyebrow">{hover.team_name}</div>
          <div style={{ fontFamily: "var(--display)", fontWeight: 700, fontSize: 19, lineHeight: 1.1, textTransform: "uppercase" }}>{hover.venue_name}</div>
          <div className="muted small">{hover.city}</div>
          <div className="stats-row" style={{ marginTop: 8, gap: 18 }}>
            <div className="stat"><span className="v num" style={{ fontSize: 20, color: altitudeColor(hover.altitude_m) }}>{hover.altitude_m.toLocaleString()} m</span><span className="l">{t("altitude")}</span></div>
            <div className="stat"><span className="v num" style={{ fontSize: 20 }}>{fmt(hover.movement_retained_pct, 0)}%</span><span className="l">{t("movementRetained")}</span></div>
          </div>
        </div>
      )}
      <div className="legend" style={{ marginTop: 6 }}>
        <span>0 m</span><span className="bar" /><span>2,232 m</span>
        <span style={{ marginLeft: "auto" }} className="faint">{t("mapHint")}</span>
      </div>
    </div>
  );
}
