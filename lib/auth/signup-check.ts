import { neon } from "@neondatabase/serverless";
import { normalizeEmail } from "./email";
import { BLOCK_MESSAGE, IP_BLOCK_ERROR_CODE } from "./constants";

export { BLOCK_MESSAGE, IP_BLOCK_ERROR_CODE };

function hashIp(ip: string): string {
  let h = 0;
  const s = ip + (process.env.SIGNUP_IP_SALT ?? "transcriber-signup");
  for (let i = 0; i < s.length; i++) {
    h = (h << 5) - h + s.charCodeAt(i);
    h |= 0;
  }
  return `h_${Math.abs(h).toString(16)}`;
}

/** Hash a raw IP string (e.g. from webhook payload). */
export function hashIpString(ip: string): string {
  return hashIp(ip);
}

export async function checkSignupAllowed(
  email: string,
  _ipHash: string
): Promise<{ allowed: boolean; message?: string }> {
  const dbUrl = process.env.DATABASE_URL;
  if (!dbUrl) return { allowed: true };

  const normalized = normalizeEmail(email);
  if (!normalized) return { allowed: true };

  const sql = neon(dbUrl);

  // Check if normalized email already exists (user+1@ and user@ are same)
  // Better Auth uses "user" table in public schema
  const emailRows = await sql`
    SELECT 1 FROM public."user"
    WHERE LOWER(
      REGEXP_REPLACE(SPLIT_PART(email, '@', 1), '\\+.*$', '') || '@' || SPLIT_PART(email, '@', 2)
    ) = ${normalized}
    LIMIT 1
  `;
  if (emailRows.length > 0) {
    return { allowed: false, message: BLOCK_MESSAGE };
  }

  // IP-based signup block removed (Option 2: cap free minutes per IP instead)
  return { allowed: true };
}

/** Get the email associated with an IP's signup (if stored). */
export async function getSignupEmailForIp(ipHash: string): Promise<string | null> {
  const dbUrl = process.env.DATABASE_URL;
  if (!dbUrl) return null;

  const sql = neon(dbUrl);
  const rows = await sql`
    SELECT user_email FROM public.signup_tracking WHERE ip_hash = ${ipHash} LIMIT 1
  `;
  return (rows[0] as { user_email: string | null } | undefined)?.user_email ?? null;
}

export async function recordSignup(
  ipHash: string,
  userId?: string,
  email?: string
): Promise<void> {
  const dbUrl = process.env.DATABASE_URL;
  if (!dbUrl) return;

  const sql = neon(dbUrl);
  const inserted = await sql`
    INSERT INTO public.signup_tracking (ip_hash, user_id, user_email)
    SELECT ${ipHash}, ${userId ?? null}, ${email ?? null}
    WHERE NOT EXISTS (SELECT 1 FROM public.signup_tracking WHERE ip_hash = ${ipHash})
    RETURNING 1
  `;
  if (inserted.length === 0 && (userId ?? email)) {
    await sql`
      UPDATE public.signup_tracking
      SET user_id = COALESCE(${userId ?? null}, user_id),
          user_email = COALESCE(${email ?? null}, user_email)
      WHERE ip_hash = ${ipHash} AND (user_email IS NULL OR user_id IS NULL)
    `;
  }
}

/** Check if IP already has a signup (for OAuth callback - no email available). */
export async function ipHasSignup(ipHash: string): Promise<boolean> {
  const dbUrl = process.env.DATABASE_URL;
  if (!dbUrl) return false;

  const sql = neon(dbUrl);
  const rows = await sql`
    SELECT 1 FROM public.signup_tracking WHERE ip_hash = ${ipHash} LIMIT 1
  `;
  return rows.length > 0;
}

/** Get the most recently created user (within last 5 seconds). For OAuth new-user detection. */
export async function getNewestUserCreatedWithinSeconds(): Promise<{
  id: string;
  email: string;
} | null> {
  const dbUrl = process.env.DATABASE_URL;
  if (!dbUrl) return null;

  const sql = neon(dbUrl);
  const rows = await sql`
    SELECT id, email FROM public."user"
    WHERE "createdAt" > NOW() - INTERVAL '5 seconds'
    ORDER BY "createdAt" DESC
    LIMIT 1
  `;
  if (rows.length === 0) return null;
  const r = rows[0] as { id: string; email: string };
  return { id: r.id, email: r.email };
}

/** Delete a user and all related data (for rolling back OAuth sign-up that violated IP rule). */
export async function deleteUserAndRelatedData(userId: string): Promise<void> {
  const dbUrl = process.env.DATABASE_URL;
  if (!dbUrl) return;

  const sql = neon(dbUrl);
  await sql`DELETE FROM public.user_credits WHERE user_id = ${userId}`;
  await sql`DELETE FROM public.session WHERE "userId" = ${userId}`;
  await sql`DELETE FROM public.account WHERE "userId" = ${userId}`;
  await sql`DELETE FROM public."user" WHERE id = ${userId}`;
}

export function getClientIp(request: Request): string {
  const forwarded = request.headers.get("x-forwarded-for");
  if (forwarded) {
    return forwarded.split(",")[0]?.trim() ?? "unknown";
  }
  const realIp = request.headers.get("x-real-ip");
  if (realIp) return realIp;
  return "unknown";
}

export function hashClientIp(request: Request): string {
  return hashIp(getClientIp(request));
}
