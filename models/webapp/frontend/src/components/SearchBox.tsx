import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type SearchResult } from "../api";
import { useLang } from "../i18n";

type Props = { pitchersOnly?: boolean; onPickPitcher?: (id: string) => void; placeholder?: string; autoFocus?: boolean };

export function SearchBox({ pitchersOnly, onPickPitcher, placeholder, autoFocus }: Props) {
  const { t } = useLang();
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [res, setRes] = useState<SearchResult | null>(null);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!q.trim()) { setRes(null); return; }
    const id = setTimeout(() => { api<SearchResult>("/search", { q, limit: 8 }).then(setRes).catch(() => setRes(null)); }, 150);
    return () => clearTimeout(id);
  }, [q]);
  useEffect(() => {
    const onDoc = (e: MouseEvent) => { if (!boxRef.current?.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const items: { kind: "p" | "s"; id: string }[] = [
    ...(res?.pitchers ?? []).map((p) => ({ kind: "p" as const, id: p.pitcher_id })),
    ...(pitchersOnly ? [] : (res?.stadiums ?? []).map((s) => ({ kind: "s" as const, id: s.id }))),
  ];
  const pick = (kind: "p" | "s", id: string) => {
    setOpen(false);
    setQ("");
    if (kind === "p") (onPickPitcher ? onPickPitcher(id) : navigate(`/lanzador/${id}`));
    else navigate(`/estadio/${id}`);
  };
  const statusLabel = (s: string) => (s === "FA" ? t("freeAgent") : s);

  return (
    <div className="search" ref={boxRef}>
      <label className="search-box">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5" /><path d="m20 20-4.8-4.8" strokeLinecap="round" /></svg>
        <input
          value={q} autoFocus={autoFocus} placeholder={placeholder ?? t("searchPlaceholder")} aria-label={placeholder ?? t("searchPlaceholder")}
          onChange={(e) => { setQ(e.target.value); setOpen(true); setActive(0); }}
          onFocus={() => setOpen(true)}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") { setActive((a) => Math.min(a + 1, items.length - 1)); e.preventDefault(); }
            if (e.key === "ArrowUp") { setActive((a) => Math.max(a - 1, 0)); e.preventDefault(); }
            if (e.key === "Enter" && items[active]) pick(items[active].kind, items[active].id);
            if (e.key === "Escape") setOpen(false);
          }}
        />
      </label>
      {open && q.trim() && res && (
        <div className="search-results">
          {items.length === 0 && <div className="muted small" style={{ padding: 8 }}>{t("noResults")}</div>}
          {res.pitchers.length > 0 && <div className="grp">{t("searchPitchers")}</div>}
          {res.pitchers.map((p, i) => (
            <button key={p.pitcher_id} className={`item ${active === i ? "active" : ""}`} onClick={() => pick("p", p.pitcher_id)}>
              <span className="num">{p.name}</span>
              <span className="chip">{p.role === "SP" ? t("sp") : t("rp")} · {p.throws === "Right" ? "R" : "L"}</span>
              <span className={`chip ${p.status === "FA" ? "gold" : ""}`} style={{ marginLeft: "auto" }}>{statusLabel(p.status)}</span>
            </button>
          ))}
          {!pitchersOnly && res.stadiums.length > 0 && <div className="grp">{t("searchStadiums")}</div>}
          {!pitchersOnly && res.stadiums.map((s, j) => (
            <button key={s.id} className={`item ${active === res.pitchers.length + j ? "active" : ""}`} onClick={() => pick("s", s.id)}>
              <span>{s.venue_name}</span>
              <span className="muted small">{s.city}</span>
              <span className="chip num" style={{ marginLeft: "auto" }}>{s.altitude_m.toLocaleString()} m</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
