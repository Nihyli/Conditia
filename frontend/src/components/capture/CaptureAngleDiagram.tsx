const HI = "var(--brand)";

export function CaptureAngleDiagram({ angle }: { angle: string }) {
  const isWhole = angle === "top" || angle === "undercarriage";

  return (
    <svg
      viewBox="0 0 160 248"
      className="angle-diagram"
      role="img"
      aria-label={`Filming angle: ${angle}`}
    >
      {/* truck body (top-down, front at top) */}
      <rect
        x={46}
        y={26}
        width={68}
        height={196}
        rx={16}
        fill={isWhole ? "var(--brand-soft)" : "rgba(255,255,255,0.12)"}
        stroke={isWhole ? HI : "rgba(255,255,255,0.85)"}
        strokeWidth={isWhole ? 4 : 2.5}
        strokeDasharray={angle === "undercarriage" ? "7 6" : undefined}
      />
      {/* cab band near front */}
      <line x1={52} y1={58} x2={108} y2={58} stroke="rgba(255,255,255,0.7)" strokeWidth={2} />
      {/* axles */}
      {[150, 188].map((y) => (
        <g key={y}>
          <rect x={38} y={y} width={8} height={18} rx={3} fill="rgba(255,255,255,0.7)" />
          <rect x={114} y={y} width={8} height={18} rx={3} fill="rgba(255,255,255,0.7)" />
        </g>
      ))}

      {/* highlighted edge + camera position */}
      {angle === "front" && (
        <>
          <line x1={54} y1={26} x2={106} y2={26} stroke={HI} strokeWidth={6} strokeLinecap="round" />
          <circle cx={80} cy={12} r={6} fill={HI} />
        </>
      )}
      {angle === "rear" && (
        <>
          <line x1={54} y1={222} x2={106} y2={222} stroke={HI} strokeWidth={6} strokeLinecap="round" />
          <circle cx={80} cy={236} r={6} fill={HI} />
        </>
      )}
      {angle === "driver_side" && (
        <>
          <line x1={46} y1={44} x2={46} y2={204} stroke={HI} strokeWidth={6} strokeLinecap="round" />
          <circle cx={26} cy={124} r={6} fill={HI} />
        </>
      )}
      {angle === "passenger_side" && (
        <>
          <line x1={114} y1={44} x2={114} y2={204} stroke={HI} strokeWidth={6} strokeLinecap="round" />
          <circle cx={134} cy={124} r={6} fill={HI} />
        </>
      )}
    </svg>
  );
}
