"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { CustomAuthView } from "@/components/auth/CustomAuthView";
import { authClient } from "@/lib/auth/client";
import { Loader2 } from "lucide-react";
import { IP_BLOCK_ERROR_CODE, BLOCK_MESSAGE } from "@/lib/auth/constants";

function SignOutView() {
  const router = useRouter();
  const signingOut = useRef(false);

  useEffect(() => {
    if (signingOut.current) return;
    signingOut.current = true;

    authClient.signOut().finally(() => {
      router.replace("/auth/sign-in");
    });
  }, [router]);

  return (
    <div className="flex flex-col items-center justify-center gap-4 py-12">
      <Loader2 className="h-8 w-8 animate-spin text-white/60" />
      <p className="text-sm text-white/60">Signing out...</p>
    </div>
  );
}

function AuthContent() {
  const params = useParams();
  const searchParams = useSearchParams();
  const path = (params?.path as string) ?? "sign-in";
  const token = searchParams.get("token");
  const rawError = searchParams.get("error");
  const hint = searchParams.get("hint");
  const error =
    rawError === IP_BLOCK_ERROR_CODE
      ? BLOCK_MESSAGE + (hint ? ` The account linked to this network is: ${hint}` : "")
      : rawError;

  if (path === "sign-out") {
    return <SignOutView />;
  }

  const view =
    path === "sign-up"
      ? "sign-up"
      : path === "forgot-password"
        ? "forgot-password"
        : path === "reset-password"
          ? "reset-password"
          : path === "verify-email"
            ? "verify-email"
            : "sign-in";

  const verifyEmail = searchParams.get("email");

  return (
    <CustomAuthView
      initialView={view}
      token={error === "INVALID_TOKEN" ? null : token}
      verifyEmail={verifyEmail}
      initialError={error && error !== "INVALID_TOKEN" ? error : null}
    />
  );
}

export default function AuthPage() {
  return (
    <div className="relative flex min-h-screen flex-col bg-[#0a0a0a] bg-[radial-gradient(ellipse_80%_80%_at_50%_-20%,rgba(120,119,198,0.3),rgba(255,255,255,0))]" data-auth-page>
      {/* Header - matches NavBar when signed in */}
      <header className="flex shrink-0 items-center gap-2 border-b border-white/5 bg-zinc-950/95 backdrop-blur-md px-4 py-3">
        <Link
          href="/"
          className="flex items-center gap-2 text-white font-semibold hover:text-white/90 transition-colors"
        >
          <img
            src="/logo.svg"
            alt="Transcriber Pro"
            width={36}
            height={36}
            className="h-9 w-9 object-contain"
          />
          Transcriber Pro
        </Link>
      </header>

      {/* Main content - same bg as home/usage when signed in */}
      <div className="relative flex flex-1 items-center justify-center overflow-hidden px-4 py-12">
        <div className="relative z-10 w-full max-w-md">
          <Suspense
            fallback={
              <div className="flex items-center justify-center py-24">
                <Loader2 className="h-7 w-7 animate-spin text-white/40" />
              </div>
            }
          >
            <AuthContent />
          </Suspense>
        </div>
      </div>
    </div>
  );
}
