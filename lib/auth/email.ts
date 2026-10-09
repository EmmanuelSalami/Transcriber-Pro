/**
 * Normalizes an email address for uniqueness checks.
 * Strips plus-addressing (e.g. user+1@gmail.com → user@gmail.com)
 * so that user+1@ and user+2@ are treated as the same account.
 */
export function normalizeEmail(email: string): string {
  if (!email || typeof email !== "string") return "";
  const trimmed = email.trim().toLowerCase();
  const atIndex = trimmed.lastIndexOf("@");
  if (atIndex <= 0) return trimmed;
  const local = trimmed.slice(0, atIndex);
  const domain = trimmed.slice(atIndex);
  const plusIndex = local.indexOf("+");
  const normalizedLocal = plusIndex >= 0 ? local.slice(0, plusIndex) : local;
  return normalizedLocal + domain;
}
