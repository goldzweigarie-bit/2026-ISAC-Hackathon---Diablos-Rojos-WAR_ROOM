import { useCallback, useState } from "react";
import type { Stadium } from "../api";
import { FreeAgentTable } from "../components/FreeAgentTable";
import { MexicoMap } from "../components/MexicoMap";
import { ScheduleCalendar } from "../components/ScheduleCalendar";
import { SearchBox } from "../components/SearchBox";
import { useLang } from "../i18n";
import { useApi } from "../state";

export default function Home() {
  const { t } = useLang();
  const { data: stadiums } = useApi<Stadium[]>("/stadiums");
  const [highlight, setHighlight] = useState<string | null>(null);
  const onHighlight = useCallback((id: string | null) => setHighlight(id), []);
  const alt = stadiums ? [...stadiums].sort((a, b) => b.altitude_m - a.altitude_m) : [];

  return (
    <main className="page">
      <section className="hero">
        <div>
          <div className="eyebrow">Liga Mexicana de Beisbol · Stuff+</div>
          <h1>{t("mapTitle")}</h1>
          <p>{t("tagline")}</p>
        </div>
        <div style={{ width: "min(460px, 100%)" }}><SearchBox /></div>
      </section>
      <div className="home-grid">
        <section className="panel">
          {stadiums ? <MexicoMap stadiums={stadiums} highlightId={highlight} /> : <div className="empty-state">{t("loading")}</div>}
          {alt.length > 0 && (
            <div className="stats-row" style={{ marginTop: 14, borderTop: "1px solid var(--line)", paddingTop: 14 }}>
              <div className="stat"><span className="v num">{alt[0].altitude_m.toLocaleString()} m</span><span className="l">{alt[0].team_code} · {t("altitude")}</span></div>
              <div className="stat"><span className="v num">{alt[alt.length - 1].altitude_m} m</span><span className="l">{alt[alt.length - 1].team_code} · {t("altitude")}</span></div>
              <div className="stat"><span className="v num" style={{ color: "var(--red-2)" }}>{Math.round(100 - alt[0].movement_retained_pct)}%</span><span className="l">{alt[0].team_code} · {t("movementLost")}</span></div>
            </div>
          )}
        </section>
        <div className="home-side">
          <ScheduleCalendar onHighlight={onHighlight} />
        </div>
        <div className="home-fa"><FreeAgentTable compact /></div>
      </div>
    </main>
  );
}
