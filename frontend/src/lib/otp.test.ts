import { isValidOtp, normalizeOtp } from "@/lib/otp";

describe("otp helpers", () => {
  test("normalizeOtp keeps only digits and max six chars", () => {
    expect(normalizeOtp("12a-34 5678")).toBe("123456");
  });

  test("isValidOtp accepts exactly six digits", () => {
    expect(isValidOtp("123456")).toBe(true);
    expect(isValidOtp("12345")).toBe(false);
    expect(isValidOtp("12345a")).toBe(false);
  });
});
