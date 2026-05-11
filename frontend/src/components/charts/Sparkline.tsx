"use client";

type SparklineProps = {
  values: number[];
  className?: string;
};

export function Sparkline({ values, className = "" }: SparklineProps) {
  const width = 220;
  const height = 64;
  const padding = 6;
  const safeValues = values.length > 0 ? values : [0];
  const min = Math.min(...safeValues);
  const max = Math.max(...safeValues);
  const range = max - min || 1;

  const points = safeValues.map((v, idx) => {
    const x =
      padding +
      (idx / Math.max(1, safeValues.length - 1)) * (width - padding * 2);
    const y =
      height - padding - ((v - min) / range) * (height - padding * 2);
    return `${x},${y}`;
  });

  return (
    <svg
      className={className}
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <polyline
        fill="none"
        stroke="rgba(255,255,255,0.8)"
        strokeWidth="2"
        points={points.join(" ")}
      />
      <polyline
        fill="none"
        stroke="rgba(255,255,255,0.2)"
        strokeWidth="1"
        points={points.join(" ")}
      />
    </svg>
  );
}
