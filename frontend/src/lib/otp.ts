export function normalizeOtp(raw: string): string {
  return raw.replace(/\D/g, "").slice(0, 6);
}

export function isValidOtp(raw: string): boolean {
  return /^\d{6}$/.test(raw);
}
