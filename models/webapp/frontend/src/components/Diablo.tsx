/** Original cartoon mascot for the bullpen helper (not the club's logo). */
export function Diablo({ size = 80, still = false }: { size?: number; still?: boolean }) {
  return (
    <svg viewBox="0 0 100 112" width={size} height={size * 1.12} aria-hidden="true" style={still ? { animation: "none" } : undefined}>
      <defs>
        <radialGradient id="dg-head" cx="40%" cy="35%" r="70%">
          <stop offset="0%" stopColor="#ff4a5c" />
          <stop offset="70%" stopColor="#d5102f" />
          <stop offset="100%" stopColor="#8a0a1e" />
        </radialGradient>
      </defs>
      {/* pitchfork */}
      <g stroke="#2a2a30" strokeWidth="3.2" strokeLinecap="round" fill="none">
        <line x1="84" y1="104" x2="84" y2="44" />
        <path d="M76 44 Q76 36 84 36 Q92 36 92 44" />
        <line x1="84" y1="36" x2="84" y2="28" />
        <line x1="76" y1="44" x2="76" y2="38" />
        <line x1="92" y1="44" x2="92" y2="38" />
      </g>
      {/* tail */}
      <path d="M20 96 Q4 92 8 78 Q10 70 16 74" stroke="#b30d27" strokeWidth="3.5" fill="none" strokeLinecap="round" />
      <path d="M14 70 L20 76 L12 78 Z" fill="#b30d27" />
      {/* body */}
      <path d="M26 110 Q24 84 44 80 Q64 84 62 110 Z" fill="#a50c23" />
      {/* horns */}
      <path d="M22 34 Q10 14 20 4 Q22 20 34 26 Z" fill="#f2efe9" />
      <path d="M66 34 Q78 14 68 4 Q66 20 54 26 Z" fill="#f2efe9" />
      {/* head */}
      <circle cx="44" cy="50" r="31" fill="url(#dg-head)" />
      {/* brows */}
      <path d="M26 38 L40 43" stroke="#2a0509" strokeWidth="3.5" strokeLinecap="round" />
      <path d="M62 38 L48 43" stroke="#2a0509" strokeWidth="3.5" strokeLinecap="round" />
      {/* eyes */}
      <ellipse cx="34" cy="49" rx="6" ry="7" fill="#fff" />
      <ellipse cx="54" cy="49" rx="6" ry="7" fill="#fff" />
      <circle cx="35.5" cy="50" r="3" fill="#111" />
      <circle cx="55.5" cy="50" r="3" fill="#111" />
      {/* grin */}
      <path d="M28 61 Q44 78 60 61 Q44 68 28 61 Z" fill="#2a0509" />
      <path d="M33 63 L36 68 L39 64 Z M49 64 L52 68 L55 63 Z" fill="#fff" />
      {/* baseball */}
      <g transform="translate(6 86)">
        <circle cx="10" cy="10" r="9.5" fill="#f7f3ea" stroke="#d9d2c3" />
        <path d="M4 3 Q8 10 4 17 M16 3 Q12 10 16 17" stroke="#d5102f" strokeWidth="1.4" fill="none" />
      </g>
    </svg>
  );
}
