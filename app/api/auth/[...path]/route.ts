import { auth } from "@/lib/auth";
import { toNextJsHandler } from "better-auth/next-js";
import { normalizeEmail } from "@/lib/auth/email";
import { checkSignupAllowed, hashClientIp, BLOCK_MESSAGE } from "@/lib/auth/signup-check";

const baseHandlers = toNextJsHandler(auth);

/** Safari ITP fix: rewrite SameSite=Lax → SameSite=None; Secure on auth cookies during OAuth flows so the state cookie survives the Google → app redirect on iPhone Safari. */
function rewriteCookiesForSafari(response: Response): Response {
  const setCookieHeaders = response.headers.getSetCookie?.() ?? [];
  if (setCookieHeaders.length === 0) return response;

  const newHeaders = new Headers();
  response.headers.forEach((value, key) => {
    if (key.toLowerCase() !== "set-cookie") {
      newHeaders.append(key, value);
    }
  });

  for (const cookie of setCookieHeaders) {
    let rewritten = cookie;
    const isAuthCookie =
      cookie.includes("oauth_state") ||
      cookie.includes("session_token") ||
      cookie.includes("session_data") ||
      cookie.includes("better-auth.") ||
      cookie.includes("__Secure-") ||
      cookie.includes("neon_auth") ||
      cookie.includes("_state");

    if (isAuthCookie) {
      rewritten = rewritten.replace(/SameSite=Lax/i, "SameSite=None");
      if (!/SameSite=/i.test(rewritten)) {
        rewritten = rewritten + "; SameSite=None";
      }
      if (!/;\s*Secure/i.test(rewritten)) {
        rewritten = rewritten + "; Secure";
      }
      if (!/;\s*Partitioned/i.test(rewritten)) {
        rewritten = rewritten + "; Partitioned";
      }
    }
    newHeaders.append("Set-Cookie", rewritten);
  }

  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: newHeaders,
  });
}

function logAuth(path: string, method: string, status: number, detail?: string) {
  const msg = `[auth] ${method} /api/auth/${path} -> ${status}`;
  if (status >= 400) {
    console.error(msg, detail ?? "");
  } else {
    console.info(msg);
  }
}

function logAuthRequest(
  path: string,
  method: string,
  request: Request,
  extra?: Record<string, unknown>
) {
  const ua = request.headers.get("user-agent") ?? "unknown";
  const ipHash = hashClientIp(request);
  const ipPrefix = ipHash.slice(0, 10);
  console.info("[auth] request", {
    path: `/api/auth/${path}`,
    method,
    userAgent: ua.slice(0, 120),
    ipHashPrefix: ipPrefix,
    ...extra,
  });
}

async function withLogging(
  path: string,
  method: string,
  fn: () => Promise<Response>
): Promise<Response> {
  try {
    const response = await fn();
    let detail: string | undefined;
    if (!response.ok) {
      try {
        const clone = response.clone();
        const text = await clone.text();
        detail = text.slice(0, 200);
      } catch {
        detail = "(could not read body)";
      }
    }
    logAuth(path, method, response.status, detail);
    return response;
  } catch (err) {
    console.error(`[auth] ${method} /api/auth/${path} -> ERROR`, err);
    throw err;
  }
}

async function wrappedPost(
  request: Request,
  context: { params: Promise<{ path: string[] }> }
) {
  const params = await context.params;
  const path = params.path?.join("/") ?? "";

  // sign-in/social: allow all – returning users must be able to sign in.
  // New-account creation from IPs that already have a signup is blocked in the OAuth callback.

  if (path === "sign-up/email" && request.method === "POST") {
    let body: { email?: string; password?: string; name?: string };
    try {
      body = await request.json();
    } catch {
      logAuth(path, "POST", 400, "Invalid request body");
      return Response.json(
        { message: "Invalid request body" },
        { status: 400 }
      );
    }

    const email = body?.email;
    if (!email || typeof email !== "string") {
      logAuth(path, "POST", 400, "Email is required");
      return Response.json(
        { message: "Email is required" },
        { status: 400 }
      );
    }

    const ipHash = hashClientIp(request);
    const check = await checkSignupAllowed(email, ipHash);
    if (!check.allowed) {
      logAuth(path, "POST", 400, check.message ?? BLOCK_MESSAGE);
      return Response.json(
        { message: check.message ?? BLOCK_MESSAGE },
        { status: 400 }
      );
    }

    // Normalize email before sending to Better Auth (so user+1@ and user@ are same)
    const normalized = normalizeEmail(email);
    const modifiedBody = { ...body, email: normalized };
    const modifiedRequest = new Request(request.url, {
      method: "POST",
      headers: request.headers,
      body: JSON.stringify(modifiedBody),
    });

    const response = await baseHandlers.POST(modifiedRequest);

    // Log full response body for sign-up debugging (email verification, etc.)
    let responseBody: string;
    try {
      const clone = response.clone();
      responseBody = await clone.text();
    } catch {
      responseBody = "(could not read body)";
    }
    console.info("[auth] sign-up/email response", {
      status: response.status,
      ok: response.ok,
      email: normalized,
      bodyPreview: responseBody.slice(0, 500),
    });
    if (response.ok) {
      try {
        const parsed = JSON.parse(responseBody) as Record<string, unknown>;
        const user = parsed?.user as Record<string, unknown> | undefined;
        console.info("[auth] sign-up user state", {
          emailVerified: user?.emailVerified,
          needsVerification: user && user.emailVerified === false,
        });
      } catch {
        // ignore parse errors
      }
    }

    logAuth(path, "POST", response.status, response.ok ? undefined : responseBody.slice(0, 200));
    return new Response(responseBody, {
      status: response.status,
      statusText: response.statusText,
      headers: response.headers,
    });
  }

  return withLogging(path, "POST", () => baseHandlers.POST(request));
}

async function wrappedGet(
  request: Request,
  context: { params: Promise<{ path: string[] }> }
) {
  const params = await context.params;
  const path = params.path?.join("/") ?? "";

  // OAuth initiation (sign-in/social) – rewrite cookies so state cookie survives Safari ITP
  if (path === "sign-in/social") {
    logAuthRequest(path, "GET", request, { social: true });

    const response = await baseHandlers.GET(request);

    const setCookies = response.headers.getSetCookie?.() ?? [];
    console.info("[auth] sign-in/social cookies", {
      status: response.status,
      cookieCount: setCookies.length,
      cookieNames: setCookies.map((c) => c.split("=")[0]).join(", "),
    });

    const patched = rewriteCookiesForSafari(response);
    logAuth(path, "GET", patched.status);
    return patched;
  }

  // OAuth callback (e.g. callback/google) – Safari cookie rewrite only (no IP block)
  const isOAuthCallback = path.startsWith("callback/");
  if (isOAuthCallback) {
    const incomingCookies = request.headers.get("cookie") ?? "";
    const hasStateCookie =
      incomingCookies.includes("oauth_state") || incomingCookies.includes("_state");

    logAuthRequest(path, "GET", request, {
      callback: true,
      hasStateCookie,
      cookiePreview: incomingCookies.slice(0, 200),
    });

    const response = await baseHandlers.GET(request);
    const patched = rewriteCookiesForSafari(response);

    logAuth(path, "GET", patched.status);
    return patched;
  }

  return withLogging(path, "GET", () => baseHandlers.GET(request));
}

async function wrappedPut(
  request: Request,
  context: { params: Promise<{ path: string[] }> }
) {
  const params = await context.params;
  const path = params.path?.join("/") ?? "";
  return withLogging(path, "PUT", () => baseHandlers.PUT(request));
}

async function wrappedDelete(
  request: Request,
  context: { params: Promise<{ path: string[] }> }
) {
  const params = await context.params;
  const path = params.path?.join("/") ?? "";
  return withLogging(path, "DELETE", () => baseHandlers.DELETE(request));
}

async function wrappedPatch(
  request: Request,
  context: { params: Promise<{ path: string[] }> }
) {
  const params = await context.params;
  const path = params.path?.join("/") ?? "";
  return withLogging(path, "PATCH", () => baseHandlers.PATCH(request));
}

export const GET = wrappedGet;
export const POST = wrappedPost;
export const PUT = wrappedPut;
export const DELETE = wrappedDelete;
export const PATCH = wrappedPatch;
