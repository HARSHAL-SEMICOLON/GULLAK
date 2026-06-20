"use client";

interface ScoreRingProps {
  score: number;
  label: string;
  icon: string;
  size?: number;
}

export function ScoreRing({ score, label, icon, size = 76 }: ScoreRingProps) {
  const r = (size - 12) / 2;
  const circ = 2 * Math.PI * r;
  const offset = circ - (score / 100) * circ;
  const color = score >= 75 ? "#10b981" : score >= 50 ? "#a78bfa" : "#f43f5e";
  const glow  = score >= 75
    ? "0 0 16px rgba(16,185,129,0.3)"
    : score >= 50
    ? "0 0 16px rgba(167,139,250,0.3)"
    : "0 0 16px rgba(244,63,94,0.3)";

  return (
    <div className="flex-shrink-0 flex flex-col items-center gap-1.5">
      <div className="relative" style={{ width: size, height: size }}>
        <svg
          width={size} height={size}
          viewBox={`0 0 ${size} ${size}`}
          className="-rotate-90"
          style={{ filter: `drop-shadow(${glow})` }}
        >
          <circle
            cx={size / 2} cy={size / 2} r={r}
            fill="rgba(255,255,255,0.04)"
            stroke="rgba(255,255,255,0.06)"
            strokeWidth={6}
          />
          <circle
            cx={size / 2} cy={size / 2} r={r}
            fill="none"
            stroke={color}
            strokeWidth={6}
            strokeLinecap="round"
            strokeDasharray={circ}
            strokeDashoffset={offset}
            className="score-ring"
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-0.5">
          <span className="text-sm leading-none">{icon}</span>
          <span className="text-xs font-bold leading-none" style={{ color }}>{score}</span>
        </div>
      </div>
      <span className="text-[9px] text-slate-600 font-medium tracking-wide uppercase text-center leading-tight">
        {label}
      </span>
    </div>
  );
}
