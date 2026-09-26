import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import type { Game, Schedule } from "../api";
import { useLang } from "../i18n";
import { useApi, useAppState } from "../state";
import { Diablo } from "./Diablo";

const MONTHS = {
  es: ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"],
  en: ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
};
const DOW = { es: ["L", "M", "M", "J", "V", "S", "D"], en: ["M", "T", "W", "T", "F", "S", "S"] };

export function ScheduleCalendar({ onHighlight }: { onHighlight?: (stadiumId: string | null) => void }) {
  const { t, lang } = useLang();
  const { selectedDate, setSelectedDate, setBullpenOpen } = useAppState();
  const { data } = useApi<Schedule>("/schedule");
  const byDate = useMemo(() => {
    const m = new Map<string, Game[]>();
    for (const g of data?.games ?? []) m.set(g.date, [...(m.get(g.date) ?? []), g]);
    return m;
  }, [data]);
  const months = useMemo(() => {
    const set = new Set((data?.games ?? []).map((g) => g.date.slice(0, 7)));
    return [...set].sort();
  }, [data]);
  const [month, setMonth] = useState<string | null>(null);

  useEffect(() => {
    if (!data || month) return;
    const today = new Date().toISOString().slice(0, 10);
    const games = data.games;
    const inSeason = games.length && today >= games[0].date && today <= games[games.length - 1].date;
    const start = selectedDate ?? (inSeason ? today : games[games.length - 1]?.date);
    if (start) setMonth(start.slice(0, 7));
    if (!selectedDate && games.length) setSelectedDate(inSeason ? today : games[games.length - 1].date);
  }, [data, month, selectedDate, setSelectedDate]);

  const selGames = selectedDate ? byDate.get(selectedDate) ?? [] : [];
  const selStadium = selGames[0]?.stadium_id ?? null;
  useEffect(() => { onHighlight?.(selStadium); }, [selStadium, onHighlight]);

  if (!data) return <div className="panel"><div className="muted">{t("loading")}</div></div>;
  if (!month) return null;
  const [y, m] = month.split("-").map(Number);
  const first = new Date(y, m - 1, 1);
  const offset = (first.getDay() + 6) % 7;
  const days = new Date(y, m, 0).getDate();
  const idx = months.indexOf(month);
  const cells = [...Array(offset).fill(null), ...Array.from({ length: days }, (_, i) => i + 1)];

  return (
    <div className="panel">
      <div className="panel-head">
        <div>
          <div className="eyebrow">{t("calendarTitle")} {data.season}</div>
          {data.record && <div className="muted small">{t("record")} <span className="num">{data.record.w}-{data.record.l}</span></div>}
        </div>
        <div className="cal-head" style={{ gap: 6, margin: 0 }}>
          <button className="btn" style={{ padding: "4px 10px" }} disabled={idx <= 0} onClick={() => setMonth(months[idx - 1])} aria-label="prev">‹</button>
          <h3 style={{ minWidth: 110, textAlign: "center" }}>{MONTHS[lang][m - 1]}</h3>
          <button className="btn" style={{ padding: "4px 10px" }} disabled={idx >= months.length - 1} onClick={() => setMonth(months[idx + 1])} aria-label="next">›</button>
        </div>
      </div>
      <div className="cal-grid">
        {DOW[lang].map((d, i) => <div key={i} className="cal-dow">{d}</div>)}
        {cells.map((d, i) => {
          if (d === null) return <div key={i} className="cal-day empty" />;
          const date = `${month}-${String(d).padStart(2, "0")}`;
          const gs = byDate.get(date);
          if (!gs) return <div key={i} className="cal-day"><span className="d">{d}</span></div>;
          const g = gs[0];
          const played = gs.filter((x) => x.result);
          return (
            <button key={i} className={`cal-day game ${g.home ? "home" : ""} ${selectedDate === date ? "sel" : ""}`} onClick={() => setSelectedDate(date)}
              title={`${g.home ? t("vs") : "@"} ${g.opponent_name}`}>
              <span className="d">{d}</span>
              <span className="opp">{g.home ? "" : "@"}{g.opponent_code}{gs.length > 1 ? " ×2" : ""}</span>
              {played.map((x, k) => <span key={k} className={`res ${x.result} num`}>{x.result} {x.runs_for}-{x.runs_against}</span>)}
              {played.length === 0 && g.status.toLowerCase() === "postponed" && <span className="faint">PPD</span>}
            </button>
          );
        })}
      </div>
      <div className="cal-detail">
        {selGames.length === 0 ? <span className="muted small">{selectedDate} · {t("noGame")}</span> : (
          <div>
            <div style={{ fontWeight: 600 }}>{selGames[0].home ? `${t("vs")} ` : `@ `}{selGames[0].opponent_name}</div>
            <div className="muted small">
              <Link to={`/estadio/${selGames[0].stadium_id}`} style={{ textDecoration: "underline" }}>{selGames[0].venue_name}</Link> · <span className="num">{selGames[0].altitude_m.toLocaleString()} m</span>
              {selGames.map((g, k) => g.result && <span key={k} className="num"> · {g.result} {g.runs_for}-{g.runs_against}</span>)}
            </div>
          </div>
        )}
        <button className="btn primary" onClick={() => setBullpenOpen(true)}><Diablo size={18} still /> {t("bullpenTitle")}</button>
      </div>
    </div>
  );
}
