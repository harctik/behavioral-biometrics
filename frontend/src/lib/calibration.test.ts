import { computeTypingStats } from "@/lib/calibration";

describe("computeTypingStats", () => {
  test("returns sane defaults when not started", () => {
    const stats = computeTypingStats({
      typed: "",
      passage: "abc",
      startedAtMs: null,
      nowMs: 1000,
    });
    expect(stats.elapsedSeconds).toBe(0);
    expect(stats.wpm).toBe(0);
    expect(stats.accuracy).toBe(100);
    expect(stats.progress).toBe(0);
  });

  test("computes wpm/accuracy/progress", () => {
    const stats = computeTypingStats({
      typed: "abX",
      passage: "abc",
      startedAtMs: 0,
      nowMs: 60000, // 60s
    });
    expect(stats.chars).toBe(3);
    // 3 chars => 0.6 words in 1 minute
    expect(stats.wpm).toBeCloseTo(0.6, 4);
    // 2/3 correct
    expect(stats.accuracy).toBeCloseTo((2 / 3) * 100, 4);
    // 3/3 passage length
    expect(stats.progress).toBe(100);
  });
});
