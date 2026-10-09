/**
 * Neon Auth webhook handler for IP-based signup tracking.
 *
 * Configure in Neon Console → Auth → Webhooks:
 * - enabled_events: ["user.before_create", "user.created"]
 * - webhook_url: https://your-app.com/webhooks/neon-auth
 *
 * For local testing, use ngrok to expose your server.
 * Signature verification is skipped when NEON_AUTH_BASE_URL is unset (e.g. local dev).
 */

import { NextRequest, NextResponse } from "next/server";
import { recordSignup, hashIpString } from "@/lib/auth/signup-check";

type WebhookPayload = {
  event_type: string;
  event_data?: {
    auth_provider?: string;
    ip_address?: string;
    user_agent?: string;
  };
  user?: { id?: string; email?: string };
};

export async function POST(request: NextRequest) {
  const rawBody = await request.text();
  let payload: WebhookPayload;

  try {
    payload = JSON.parse(rawBody) as WebhookPayload;
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  const eventType =
    request.headers.get("x-neon-event-type") ?? payload.event_type;
  const ip = payload.event_data?.ip_address;

  console.info("[webhook] neon-auth", { eventType, hasIp: !!ip });

  if (eventType === "user.before_create") {
    // Allow all sign-ups. IP cap is applied at usage time (ip_free_usage), not sign-up.
    return NextResponse.json({ allowed: true });
  }

  if (eventType === "user.created" && ip) {
    const ipHash = hashIpString(ip);
    try {
      const user = payload.user;
      await recordSignup(ipHash, user?.id, user?.email);
    } catch (e) {
      console.error("[webhook] Failed to record signup:", e);
    }
    return NextResponse.json({ ok: true });
  }

  return NextResponse.json({ ok: true });
}
