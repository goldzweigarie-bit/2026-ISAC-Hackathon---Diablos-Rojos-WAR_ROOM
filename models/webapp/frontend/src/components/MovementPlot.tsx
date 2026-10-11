import type { ProjectedPitch } from "../api";
import { PITCH_COLORS } from "../state";

const W = 360;
const H = 340;
const PAD = 34;
const R = 26; // inches shown in each direction
const sx = (v: number) => PAD + ((v + R) / (2 * R)) * (W - 2 * PAD);
const sy = (v: number) => H - PAD - ((v + R) / (2 * R)) * (H - 2 * PAD);

export function MovementPlot({ pitches, visible, xLabel, yLabel }: { pitches: ProjectedPitch[]; visible: Set<string>; xLabel: string; yLabel: string }) {
  const ticks = [-20, -10, 0, 10, 20];
  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: "auto", display: "block" }} role="img">
      <defs>
        <marker id="mv-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M0 0 L10 5 L0 10 z" fill="var(--chalk)" />
        </marker>
      </defs>
      {ticks.map((v) => (
        <g key={v}>
          <line x1={sx(v)} x2={sx(v)} y1={sy(-R)} y2={sy(R)} stroke={v === 0 ? "var(--line-2)" : "var(--line)"} />
          <line y1={sy(v)} y2={sy(v)} x1={sx(-R)} x2={sx(R)} stroke={v === 0 ? "var(--line-2)" : "var(--line)"} />
          <text x={sx(v)} y={H - PAD + 16} textAnchor="middle" fontSize="11" fill="var(--faint)" fontFamily="var(--mono)">{v}</text>
          <text x={PAD - 8} y={sy(v) + 4} textAnchor="end" fontSize="11" fill="var(--faint)" fontFamily="var(--mono)">{v}</text>
        </g>
      ))}
      <text x={W / 2} y={H - 4} textAnchor="middle" fontSize="12" fill="var(--muted)">{xLabel} (in)</text>
      <text x={10} y={H / 2} textAnchor="middle" fontSize="12" fill="var(--muted)" transform={`rotate(-90 10 ${H / 2})`}>{yLabel} (in)</text>
      {pitches.filter((p) => visible.has(p.pitch_type)).map((p) => {
        const c = PITCH_COLORS[p.pitch_type];
        const x0 = sx(p.sea.hb), y0 = sy(p.sea.ivb), x1 = sx(p.here.hb), y1 = sy(p.here.ivb);
        return (
          <g key={p.pitch_type}>
            <circle cx={x0} cy={y0} r={7} fill="none" stroke={c} strokeDasharray="3 2" strokeWidth="1.6" />
            {Math.hypot(x1 - x0, y1 - y0) > 10 && <line x1={x0} y1={y0} x2={x1} y2={y1} stroke="var(--chalk)" strokeWidth="1.2" markerEnd="url(#mv-arrow)" opacity="0.8" />}
            <circle cx={x1} cy={y1} r={7} fill={c} stroke="#0b0b0d" strokeWidth="1.5" />
          </g>
        );
      })}
    </svg>
  );
}
