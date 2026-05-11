export type TypingStats = {
  chars: number;
  wpm: number;
  accuracy: number;
  progress: number;
  elapsedSeconds: number;
};

export function computeTypingStats(params: {
  typed: string;
  passage: string;
  startedAtMs: number | null;
  nowMs: number;
}): TypingStats {
  const { typed, passage, startedAtMs, nowMs } = params;
  const elapsedSeconds =
    startedAtMs !== null && nowMs > startedAtMs ? (nowMs - startedAtMs) / 1000 : 0;
  const chars = typed.length;

  const wpm = elapsedSeconds > 0 ? (chars / 5) / (elapsedSeconds / 60) : 0;

  let correct = 0;
  for (let i = 0; i < typed.length; i++) {
    if (typed[i] === passage[i]) correct++;
  }
  const accuracy = typed.length > 0 ? (correct / typed.length) * 100 : 100;

  const progress = passage.length > 0 ? Math.min(100, (chars / passage.length) * 100) : 0;

  return { chars, wpm, accuracy, progress, elapsedSeconds };
}
