import { useRef } from "react";
import type { ProjectedPitch } from "../api";
import { PITCH_COLORS } from "../state";

// Perspective camera a few feet behind the plate, looking toward the mound (catcher's view).
const CAM_Y = -8;
const CAM_Z = 2.5;
const PLATE_Y = 17 / 12;
const S = 108; // px per foot at the plate
const F = S * (PLATE_Y - CAM_Y);
const W = 440;
const H = 500;
const CX = W / 2;
const CY = 210;
const BALL_R = (1.45 / 12) * S;

function proj(x: number, y: number, z: number): [number, number] {
  const d = y - CAM_Y;
  return [CX + (x * F) / d, CY - ((z - CAM_Z) * F) / d];
}

type Props = {
  pitches: ProjectedPitch[];
  visible: Set<string>;
  aim: { x: number; z: number };
  onAim: (x: number, z: number) => void;
  labels: { sea: string; here: string };
};

export function StrikeZone({ pitches, visible, aim, onAim, labels }: Props) {
  const ref = useRef<SVGSVGElement>(null);
  const click = (e: React.MouseEvent<SVGSVGElement>) => {
    const svg = ref.current;
    if (!svg) return;
    const pt = svg.createSVGPoint();
    pt.x = e.clientX;
    pt.y = e.clientY;
    const p = pt.matrixTransform(svg.getScreenCTM()!.inverse());
    const x = Math.max(-1.6, Math.min(1.6, (p.x - CX) / S));
    const z = Math.max(0.6, Math.min(4.4, CAM_Z - (p.y - CY) / S));
    onAim(Math.round(x * 100) / 100, Math.round(z * 100) / 100);
  };
  const [zl, zt] = proj(-0.708, PLATE_Y, 3.5);
  const [zr, zb] = proj(0.708, PLATE_Y, 1.5);
  const [ax, az] = proj(aim.x, PLATE_Y, aim.z);
  const plate = [[-0.708, 0], [0.708, 0], [0.708, 0.708], [0, PLATE_Y], [-0.708, 0.708]]
    .map(([x, dy]) => proj(x, PLATE_Y - dy, 0)).map((p) => p.join(",")).join(" ");
  const shown = pitches.filter((p) => visible.has(p.pitch_type));

  return (
    <>
    <svg ref={ref} className="zone-svg" viewBox={`0 0 ${W} ${H}`} onClick={click} role="img">
      <defs>
        <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M0 0 L10 5 L0 10 z" fill="var(--chalk)" />
        </marker>
        <linearGradient id="dirt" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor="#20150f" stopOpacity="0" />
          <stop offset="1" stopColor="#3a2416" stopOpacity="0.55" />
        </linearGradient>
      </defs>
      <rect x="0" y={proj(0, PLATE_Y, 0)[1] - 40} width={W} height={H} fill="url(#dirt)" />
      <polygon points={plate} fill="#e9e3d6" opacity="0.85" />
      {/* zone grid */}
      <rect x={zl} y={zt} width={zr - zl} height={zb - zt} fill="rgba(239,233,220,0.03)" stroke="var(--chalk)" strokeWidth="2" />
      {[1, 2].map((i) => (
        <g key={i} stroke="var(--chalk)" strokeOpacity="0.18">
          <line x1={zl + ((zr - zl) * i) / 3} x2={zl + ((zr - zl) * i) / 3} y1={zt} y2={zb} />
          <line y1={zt + ((zb - zt) * i) / 3} y2={zt + ((zb - zt) * i) / 3} x1={zl} x2={zr} />
        </g>
      ))}
      {/* flight paths (faint) */}
      {shown.map((p) => (
        <g key={`path-${p.pitch_type}`} fill="none" stroke={PITCH_COLORS[p.pitch_type]} strokeLinecap="round">
          <polyline points={p.sea.path.map((q) => proj(q.x, q.y, q.z).join(",")).join(" ")} strokeOpacity="0.18" strokeWidth="2" strokeDasharray="4 4" />
          <polyline points={p.here.path.map((q) => proj(q.x, q.y, q.z).join(",")).join(" ")} strokeOpacity="0.45" strokeWidth="2.5" />
        </g>
      ))}
      {/* aim */}
      <g stroke="var(--muted)" strokeWidth="1.2" opacity="0.8">
        <circle cx={ax} cy={az} r={BALL_R + 4} fill="none" strokeDasharray="2 3" />
        <line x1={ax - 16} x2={ax - 7} y1={az} y2={az} /><line x1={ax + 7} x2={ax + 16} y1={az} y2={az} />
        <line y1={az - 16} y2={az - 7} x1={ax} x2={ax} /><line y1={az + 7} y2={az + 16} x1={ax} x2={ax} />
      </g>
      {/* crossings: sea level (ghost) -> here (solid) */}
      {shown.map((p) => {
        const [sx, sy] = proj(p.sea.px, PLATE_Y, p.sea.pz);
        const [hx, hy] = proj(p.here.px, PLATE_Y, p.here.pz);
        const c = PITCH_COLORS[p.pitch_type];
        const long = Math.hypot(hx - sx, hy - sy) > BALL_R * 1.2;
        return (
          <g key={p.pitch_type}>
            <circle cx={sx} cy={sy} r={BALL_R} fill="none" stroke={c} strokeWidth="1.6" strokeDasharray="3 2" opacity="0.8" />
            {long && <line x1={sx} y1={sy} x2={hx} y2={hy} stroke="var(--chalk)" strokeWidth="1.3" markerEnd="url(#arrow)" opacity="0.8" />}
            <circle cx={hx} cy={hy} r={BALL_R} fill={c} stroke="#0b0b0d" strokeWidth="1.5" />
          </g>
        );
      })}
    </svg>
    <div className="muted small" style={{ display: "flex", gap: 18, justifyContent: "center" }}>
      <span><span className="dot" style={{ border: "1.5px dashed var(--muted)", background: "none" }} /> {labels.sea}</span>
      <span><span className="dot" style={{ background: "var(--muted)" }} /> {labels.here}</span>
    </div>
    </>
  );
}
