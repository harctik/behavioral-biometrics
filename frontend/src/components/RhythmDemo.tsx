"use client";

import { useRef, useState } from "react";

type Stroke = { id: number; key: string; hold: number; gap: number };

const MAX_BARS = 36;

/**
 * Landing page illustration that uses real input: bar height is how long a key
 * was held, the space before it is the pause since the previous key.
 * This component keeps its readings in local state only.
 */
export function RhythmDemo() {
  const [strokes, setStrokes] = useState<Stroke[]>([]);
  const downAt = useRef(new Map<string, { time: number; gap: number }>());
  const lastUp = useRef<number | null>(null);
  const nextId = useRef(0);

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.repeat || e.key.length !== 1) return;
    const now = performance.now();
    const gap = lastUp.current === null ? 0 : Math.max(0, now - lastUp.current);
    downAt.current.set(e.code, { time: now, gap });
  };

  const onKeyUp = (e: React.KeyboardEvent) => {
    const down = downAt.current.get(e.code);
    if (!down) return;
    downAt.current.delete(e.code);
    const now = performance.now();
    lastUp.current = now;
    const stroke: Stroke = {
      id: nextId.current++,
      key: e.key === " " ? "␣" : e.key,
      hold: now - down.time,
      gap: down.gap,
    };
    setStrokes((prev) => [...prev, stroke].slice(-MAX_BARS));
  };

  const average = (pick: (s: Stroke) => number) =>
    strokes.length ? Math.round(strokes.reduce((sum, s) => sum + pick(s), 0) / strokes.length) : null;
  const hold = average((s) => s.hold);
  const gap = average((s) => Math.min(s.gap, 1000));

  return (
    <div className="border border-slate-800 rounded-xl bg-surface p-5 sm:p-6">
      <label htmlFor="rhythm-input" className="block text-sm font-semibold">
        Type a sentence to see your own rhythm
      </label>
      <input
        id="rhythm-input"
        type="text"
        autoComplete="off"
        spellCheck={false}
        placeholder="The quick brown fox"
        onKeyDown={onKeyDown}
        onKeyUp={onKeyUp}
        className="mt-3 w-full h-11 rounded-md px-3.5 text-sm placeholder:text-slate-600"
      />

      <div className="mt-5 h-36 flex items-end gap-[3px] overflow-hidden border-b border-slate-700" aria-hidden="true">
        {strokes.map((s) => (
          <div
            key={s.id}
            className="flex-1 min-w-0 max-w-3 bg-fg rounded-t-[2px]"
            style={{
              height: `${Math.max(6, Math.min(100, (s.hold / 220) * 100))}%`,
              marginLeft: `${Math.min(14, s.gap / 40)}px`,
            }}
            title={`${s.key}: held ${Math.round(s.hold)} ms`}
          />
        ))}
      </div>

      <dl className="mt-4 grid grid-cols-3 gap-3 text-sm">
        {[
          ["Keys", strokes.length || "0"],
          ["Avg. hold", hold === null ? "–" : `${hold} ms`],
          ["Avg. gap", gap === null ? "–" : `${gap} ms`],
        ].map(([label, value]) => (
          <div key={label}>
            <dt className="text-xs text-muted">{label}</dt>
            <dd className="mt-1 font-mono text-lg tabular-nums">{value}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-4 text-xs text-slate-500">
        Bar height is key hold time and spacing is the pause before each key. The chart is drawn in your
        browser. When you are signed in, the app also collects typing and pointer timing for your profile.
      </p>
    </div>
  );
}
