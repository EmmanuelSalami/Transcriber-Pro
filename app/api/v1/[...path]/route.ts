/**
 * Proxy for /api/v1/* to Python backend.
 * Forwards X-Forwarded-For so the backend gets the real client IP for ip_hash (credits cap, etc).
 */
import { NextRequest, NextResponse } from "next/server";

// Allow large file uploads (up to 500MB) and longer timeouts for transcription
export const maxDuration = 300; // 5 minutes max for serverless function
export const dynamic = "force-dynamic";

function getClientIp(request: NextRequest): string {
  const forwarded = request.headers.get("x-forwarded-for");
  if (forwarded) {
    return forwarded.split(",")[0]?.trim() ?? "unknown";
  }
  const realIp = request.headers.get("x-real-ip");
  if (realIp) return realIp;
  return "unknown";
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return proxyRequest(request, params, "GET");
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return proxyRequest(request, params, "POST");
}

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return proxyRequest(request, params, "PUT");
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return proxyRequest(request, params, "PATCH");
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return proxyRequest(request, params, "DELETE");
}

async function proxyRequest(
  request: NextRequest,
  params: Promise<{ path: string[] }>,
  method: string
) {
  const { path } = await params;
  const backendUrl = process.env.BACKEND_URL || "http://localhost:8000";
  const pathStr = path?.length ? path.join("/") : "";
  const url = new URL(request.url);
  const backendPath = `/v1/${pathStr}${url.search}`;
  const target = `${backendUrl}${backendPath}`;

  const clientIp = getClientIp(request);

  const headers = new Headers(request.headers);
  headers.set("X-Forwarded-For", clientIp);

  let body: BodyInit | undefined;
  if (method !== "GET" && method !== "HEAD") {
    try {
      body = await request.arrayBuffer();
    } catch {
      // ignore
    }
  }

  let res: Response;
  try {
    res = await fetch(target, {
      method,
      headers,
      body,
    });
  } catch (err) {
    const error = err as Error;
    console.error("[Proxy] Backend error:", target, error);
    
    // Provide helpful error messages based on the error type
    let message = "Backend service unavailable. Please try again.";
    let code = "BACKEND_UNAVAILABLE";
    
    if (error.message?.includes("socket hang up") || error.message?.includes("ECONNRESET")) {
      message = "The server connection was interrupted. This may happen with very large files. Please try a smaller file or try again.";
      code = "CONNECTION_RESET";
    } else if (error.message?.includes("ETIMEDOUT") || error.message?.includes("timeout")) {
      message = "The request timed out. Please try again with a smaller file.";
      code = "TIMEOUT";
    }
    
    return new NextResponse(
      JSON.stringify({
        code,
        message,
        detail: message,
      }),
      { status: 503, headers: { "Content-Type": "application/json" } }
    );
  }

  const resHeaders = new Headers(res.headers);
  resHeaders.delete("transfer-encoding");
  resHeaders.delete("content-encoding");

  return new NextResponse(res.body, {
    status: res.status,
    statusText: res.statusText,
    headers: resHeaders,
  });
}
