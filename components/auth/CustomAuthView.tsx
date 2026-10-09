"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { authClient } from "@/lib/auth/client";
import { Mail, Lock, Loader2, User, Eye, EyeOff } from "lucide-react";

type AuthView = "sign-in" | "sign-up" | "forgot-password" | "reset-password" | "verify-email";

interface CustomAuthViewProps {
  initialView?: AuthView;
  token?: string | null;
  /** Email to verify (from sign-up or query param) */
  verifyEmail?: string | null;
  /** Error message from URL (e.g. OAuth callback block) */
  initialError?: string | null;
}

export function CustomAuthView({
  initialView = "sign-in",
  token,
  verifyEmail: verifyEmailProp,
  initialError: initialErrorProp,
}: CustomAuthViewProps) {
  const router = useRouter();
  const { data: session, isPending: sessionPending } = authClient.useSession();
  const [view, setView] = useState<AuthView>(initialView);

  // Redirect signed-in users away from sign-in/sign-up
  useEffect(() => {
    if (!sessionPending && session?.user && (view === "sign-in" || view === "sign-up")) {
      router.replace("/");
    }
  }, [session, sessionPending, view, router]);
  const [pendingVerifyEmail, setPendingVerifyEmail] = useState<string | null>(
    verifyEmailProp ?? null
  );
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(initialErrorProp ?? null);

  useEffect(() => {
    if (initialErrorProp) setError(initialErrorProp);
  }, [initialErrorProp]);
  const [success, setSuccess] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState(false);

  const clearMessages = () => {
    setError(initialErrorProp ?? null);
    setSuccess(null);
  };

  const handleGoogleSignIn = async () => {
    setIsSubmitting(true);
    setError(null);
    try {
      const result = await authClient.signIn.social({
        provider: "google",
        callbackURL: "/",
      });
      // Handle API errors (e.g. IP block) – auth may return { error } instead of throwing
      const errMsg = (result as { error?: { message?: string } })?.error?.message;
      if (errMsg) {
        setError(errMsg);
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to sign in with Google"
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSignIn = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    clearMessages();
    const form = e.currentTarget;
    const email = (form.elements.namedItem("email") as HTMLInputElement)?.value;
    const password = (form.elements.namedItem("password") as HTMLInputElement)
      ?.value;
    if (!email || !password) {
      setError("Email and password are required.");
      return;
    }
    setIsSubmitting(true);
    setError(null);
    try {
      const { error: signInError } = await authClient.signIn.email({
        email,
        password,
      });
      if (signInError) {
        setError(signInError.message ?? "Invalid email or password.");
        return;
      }
      // Full page navigation so the session cookie is sent (router.push can miss cookies on client-side nav)
      window.location.href = "/";
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to sign in.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSignUp = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    clearMessages();
    const form = e.currentTarget;
    const name = (form.elements.namedItem("name") as HTMLInputElement)?.value;
    const email = (form.elements.namedItem("email") as HTMLInputElement)?.value;
    const password = (form.elements.namedItem("password") as HTMLInputElement)
      ?.value;
    if (!name || !email || !password) {
      setError("Name, email, and password are required.");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    setIsSubmitting(true);
    try {
      const { data: signUpData, error: signUpError } = await authClient.signUp.email({
        name,
        email,
        password,
        callbackURL: "/",
      });
      if (signUpError) {
        setError(signUpError.message ?? "Failed to create account.");
        return;
      }
      // If user needs verification, redirect to verify-email page
      const user = signUpData?.user as { emailVerified?: boolean } | undefined;
      if (user && user.emailVerified === false) {
        // Better Auth sends verification OTP on sign-up - redirect to verify-email page
        setPendingVerifyEmail(email);
        setView("verify-email");
        router.replace(`/auth/verify-email?email=${encodeURIComponent(email)}`);
        return;
      }
      router.push("/");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to sign up.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleForgotPassword = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    clearMessages();
    const form = e.currentTarget;
    const email = (form.elements.namedItem("email") as HTMLInputElement)?.value;
    if (!email) {
      setError("Email is required.");
      return;
    }
    setIsSubmitting(true);
    try {
      const baseUrl =
        typeof window !== "undefined" ? window.location.origin : "";
      await authClient.requestPasswordReset({
        email,
        redirectTo: `${baseUrl}/auth/reset-password`,
      });
      setSuccess("Check your email for a password reset link.");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to send reset email."
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleResetPassword = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!token) {
      setError("Invalid or expired reset link.");
      return;
    }
    clearMessages();
    const form = e.currentTarget;
    const newPassword = (
      form.elements.namedItem("newPassword") as HTMLInputElement
    )?.value;
    const confirmPassword = (
      form.elements.namedItem("confirmPassword") as HTMLInputElement
    )?.value;
    if (!newPassword || !confirmPassword) {
      setError("Please enter and confirm your new password.");
      return;
    }
    if (newPassword.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }
    setIsSubmitting(true);
    try {
      const { error: resetError } = await authClient.resetPassword({
        newPassword,
        token,
      });
      if (resetError) {
        setError(resetError.message ?? "Failed to reset password.");
        return;
      }
      setSuccess("Password reset successfully. Redirecting to sign in...");
      setTimeout(() => {
        setView("sign-in");
        setSuccess(null);
        router.push("/auth/sign-in");
        router.refresh();
      }, 1500);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to reset password."
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleVerifyEmail = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    clearMessages();
    const form = e.currentTarget;
    const email =
      (form.elements.namedItem("email") as HTMLInputElement)?.value ?? pendingVerifyEmail;
    const otp = (form.elements.namedItem("otp") as HTMLInputElement)?.value;
    if (!email || !otp) {
      setError("Email and verification code are required.");
      return;
    }
    setIsSubmitting(true);
    try {
      const { error: verifyError } = await authClient.emailOtp.verifyEmail({
        email,
        otp,
      });
      if (verifyError) {
        setError(verifyError.message ?? "Invalid or expired code. Try resending.");
        return;
      }
      setSuccess("Email verified! Logging you in...");
      // Show success message for 2.5s so user can see it
      await new Promise((r) => setTimeout(r, 2500));
      // Check if verify endpoint set a session (auto-sign-in)
      const { data: sessionData } = await authClient.getSession();
      if (sessionData?.session) {
        router.push("/");
        router.refresh();
      } else {
        // No session - redirect to sign-in with success message
        setSuccess("Email verified! You can now sign in.");
        router.replace("/auth/sign-in");
        router.refresh();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Verification failed.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleResendVerification = async () => {
    const email = pendingVerifyEmail ?? verifyEmailProp;
    if (!email) return;
    clearMessages();
    setIsSubmitting(true);
    try {
      const { error: sendError } = await authClient.emailOtp.sendVerificationOtp({
        email,
        type: "email-verification",
      });
      if (sendError) {
        setError(sendError.message ?? "Failed to resend. Try again later.");
        return;
      }
      setSuccess("Verification email sent! Check your inbox.");
    } catch {
      setError("Failed to resend. Try again later.");
    } finally {
      setIsSubmitting(false);
    }
  };

  /* ── shared input classes (matches TranscriptionForm/Usage theme) ── */
  const inputBase =
    "w-full rounded-xl border border-white/10 bg-black/20 py-3 pl-11 pr-4 text-sm text-white placeholder:text-white/30 focus:outline-none focus:ring-2 focus:ring-blue-500/50 transition disabled:opacity-60";
  const iconClass =
    "absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-white/40";
  const inputBasePassword = inputBase + " pr-12";

  /* ── Google button (shared) ── */
  const googleButton = (label: string) => (
    <button
      type="button"
      onClick={handleGoogleSignIn}
      disabled={isSubmitting}
      className="flex w-full items-center justify-center gap-3 rounded-xl border border-white/10 bg-white/10 px-4 py-3 text-sm font-medium text-white/80 transition hover:bg-white/20 hover:text-white active:scale-[0.98] disabled:opacity-60"
    >
      {isSubmitting ? (
        <Loader2 className="h-5 w-5 animate-spin text-white/40" />
      ) : (
        <>
          {/* Google G logo - official colors */}
          <svg className="h-5 w-5 shrink-0" viewBox="0 0 24 24">
            <path
              fill="#4285F4"
              d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
            />
            <path
              fill="#34A853"
              d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
            />
            <path
              fill="#FBBC05"
              d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
            />
            <path
              fill="#EA4335"
              d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
            />
          </svg>
          {label}
        </>
      )}
    </button>
  );

  const viewTitles: Record<AuthView, { title: string; description: string }> = {
    "sign-in": {
      title: "Sign In",
      description: "Enter your email below to login to your account",
    },
    "sign-up": {
      title: "Sign Up",
      description: "Create an account to get started",
    },
    "forgot-password": {
      title: "Forgot Password?",
      description: "Enter your email and we'll send you a reset link",
    },
    "reset-password": {
      title: "Reset Password",
      description: "Enter your new password below",
    },
    "verify-email": {
      title: "Verify Your Email",
      description: "Enter the code we sent to your email",
    },
  };

  const { title, description } = viewTitles[view];

  // Show loader while checking session (avoids flash before redirect)
  if (sessionPending && (view === "sign-in" || view === "sign-up")) {
    return (
      <div className="flex justify-center py-24">
        <Loader2 className="h-7 w-7 animate-spin text-white/40" />
      </div>
    );
  }

  return (
    <div className="w-full max-w-md mx-auto">
      {/* ── Card (matches TranscriptionForm/Usage) ── */}
      <div className="flex flex-col rounded-2xl bg-white/5 border border-white/10 px-6 py-10 shadow-xl backdrop-blur-sm">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-white/90">{title}</h1>
          <p className="mt-1 text-sm text-white/60">{description}</p>
        </div>

        {/* Messages */}
        {error && (
          <div className="mb-4 rounded-xl bg-red-500/10 border border-red-500/20 px-4 py-3 text-sm text-red-200">
            {error}
          </div>
        )}
        {success && (
          <div className="mb-4 rounded-xl bg-green-500/10 border border-green-500/20 px-4 py-3 text-sm text-green-200">
            {success}
          </div>
        )}

        {/* ────────── Sign In ────────── */}
        {view === "sign-in" && (
          <>
            <form onSubmit={handleSignIn} className="space-y-6">
              <div>
                <label htmlFor="email" className="mb-1.5 block text-sm font-medium text-white/50">
                  Email
                </label>
                <div className="relative">
                  <Mail className={iconClass} />
                  <input
                    id="email"
                    name="email"
                    type="email"
                    placeholder="m@example.com"
                    required
                    disabled={isSubmitting}
                    className={inputBase}
                  />
                </div>
              </div>
              <div>
                <div className="mb-1.5 flex items-center justify-between">
                  <label htmlFor="password" className="block text-sm font-medium text-white/50">
                    Password
                  </label>
                  <button
                    type="button"
                    onClick={() => {
                      clearMessages();
                      setView("forgot-password");
                    }}
                    className="text-sm font-medium text-white/60 hover:text-white/80 transition"
                  >
                    Forgot your password?
                  </button>
                </div>
                <div className="relative">
                  <Lock className={iconClass} />
                  <input
                    id="password"
                    name="password"
                    type={showPassword ? "text" : "password"}
                    placeholder="Password"
                    required
                    disabled={isSubmitting}
                    className={inputBasePassword}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-white/40 hover:text-white/60 transition"
                    aria-label={showPassword ? "Hide password" : "Show password"}
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>
              <button
                type="submit"
                disabled={isSubmitting}
                className="flex w-full items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-blue-500 active:scale-[0.98] disabled:opacity-60"
              >
                {isSubmitting ? (
                  <Loader2 className="h-5 w-5 animate-spin" />
                ) : (
                  "Sign In"
                )}
              </button>
            </form>

            <div className="my-6 flex items-center gap-3">
              <div className="h-px flex-1 bg-white/10" />
              <span className="text-xs font-medium text-white/40 uppercase tracking-wider">
                Or continue with
              </span>
              <div className="h-px flex-1 bg-white/10" />
            </div>

            {googleButton("Sign in with Google")}

            <p className="mt-6 text-center text-sm text-white/60">
              Don&apos;t have an account?{" "}
              <button
                type="button"
                onClick={() => {
                  clearMessages();
                  setView("sign-up");
                }}
                className="font-semibold text-white/80 hover:text-white underline underline-offset-2 transition"
              >
                Sign up for free!
              </button>
            </p>
          </>
        )}

        {/* ────────── Sign Up ────────── */}
        {view === "sign-up" && (
          <>
            <form onSubmit={handleSignUp} className="space-y-6">
              <div className="relative">
                <User className={iconClass} />
                <input
                  name="name"
                  type="text"
                  placeholder="Name"
                  required
                  disabled={isSubmitting}
                  className={inputBase}
                />
              </div>
              <div className="relative">
                <Mail className={iconClass} />
                <input
                  name="email"
                  type="email"
                  placeholder="Email"
                  required
                  disabled={isSubmitting}
                  className={inputBase}
                />
              </div>
              <div className="relative">
                <Lock className={iconClass} />
                <input
                  name="password"
                  type={showPassword ? "text" : "password"}
                  placeholder="Password (min 8 characters)"
                  required
                  minLength={8}
                  disabled={isSubmitting}
                  className={inputBasePassword}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-white/40 hover:text-white/60 transition"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              <button
                type="submit"
                disabled={isSubmitting}
                className="flex w-full items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-blue-500 active:scale-[0.98] disabled:opacity-60"
              >
                {isSubmitting ? (
                  <Loader2 className="h-5 w-5 animate-spin" />
                ) : (
                  "Sign Up"
                )}
              </button>
            </form>

            <div className="my-6 flex items-center gap-3">
              <div className="h-px flex-1 bg-white/10" />
              <span className="text-xs font-medium text-white/40 uppercase tracking-wider">
                Or continue with
              </span>
              <div className="h-px flex-1 bg-white/10" />
            </div>

            {googleButton("Sign up with Google")}

            <p className="mt-6 text-center text-sm text-white/60">
              Already have an account?{" "}
              <button
                type="button"
                onClick={() => {
                  clearMessages();
                  setView("sign-in");
                }}
                className="font-semibold text-white/80 hover:text-white underline underline-offset-2 transition"
              >
                Sign in
              </button>
            </p>
          </>
        )}

        {/* ────────── Forgot Password ────────── */}
        {view === "forgot-password" && (
          <>
            <form onSubmit={handleForgotPassword} className="space-y-6">
              <div className="relative">
                <Mail className={iconClass} />
                <input
                  name="email"
                  type="email"
                  placeholder="Email"
                  required
                  disabled={isSubmitting}
                  className={inputBase}
                />
              </div>
              <button
                type="submit"
                disabled={isSubmitting}
                className="flex w-full items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-blue-500 active:scale-[0.98] disabled:opacity-60"
              >
                {isSubmitting ? (
                  <Loader2 className="h-5 w-5 animate-spin" />
                ) : (
                  "Send Reset Link"
                )}
              </button>
            </form>
            <p className="mt-6 text-center">
              <button
                type="button"
                onClick={() => {
                  clearMessages();
                  setView("sign-in");
                }}
                className="text-sm font-semibold text-white/80 hover:text-white transition"
              >
                ← Back to Sign In
              </button>
            </p>
          </>
        )}

        {/* ────────── Reset Password ────────── */}
        {view === "reset-password" && (
          <>
            {!token ? (
              <>
                <p className="mb-4 text-sm text-white/60">
                  Invalid or expired reset link. Please request a new password
                  reset.
                </p>
                <Link
                  href="/auth/forgot-password"
                  className="inline-block w-full rounded-xl bg-blue-600 px-4 py-3 text-center text-sm font-semibold text-white transition hover:bg-blue-500 active:scale-[0.98]"
                >
                  Request New Reset Link
                </Link>
              </>
            ) : (
              <>
                <p className="mb-4 text-sm text-white/60">
                  Enter your new password below.
                </p>
                <form onSubmit={handleResetPassword} className="space-y-6">
                  <div className="relative">
                    <Lock className={iconClass} />
                    <input
                      name="newPassword"
                      type={showPassword ? "text" : "password"}
                      placeholder="New password (min 8 characters)"
                      required
                      minLength={8}
                      disabled={isSubmitting}
                      className={inputBasePassword}
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-white/40 hover:text-white/60 transition"
                      aria-label={showPassword ? "Hide password" : "Show password"}
                    >
                      {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  </div>
                  <div className="relative">
                    <Lock className={iconClass} />
                    <input
                      name="confirmPassword"
                      type={showPassword ? "text" : "password"}
                      placeholder="Confirm new password"
                      required
                      minLength={8}
                      disabled={isSubmitting}
                      className={inputBasePassword}
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-white/40 hover:text-white/60 transition"
                      aria-label={showPassword ? "Hide password" : "Show password"}
                    >
                      {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  </div>
                  <button
                    type="submit"
                    disabled={isSubmitting}
                    className="flex w-full items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-blue-500 active:scale-[0.98] disabled:opacity-60"
                  >
                    {isSubmitting ? (
                      <Loader2 className="h-5 w-5 animate-spin" />
                    ) : (
                      "Reset Password"
                    )}
                  </button>
                </form>
                <p className="mt-6 text-center">
                  <Link
                    href="/auth/sign-in"
                    className="text-sm font-semibold text-white/80 hover:text-white transition"
                  >
                    ← Back to Sign In
                  </Link>
                </p>
              </>
            )}
          </>
        )}

        {/* ────────── Verify Email ────────── */}
        {view === "verify-email" && (
          <>
            <form onSubmit={handleVerifyEmail} className="space-y-6">
              <div>
                <label htmlFor="verify-email" className="mb-1.5 block text-sm font-medium text-white/50">
                  Email
                </label>
                <div className="relative">
                  <Mail className={iconClass} />
                  <input
                    id="verify-email"
                    name="email"
                    type="email"
                    placeholder="you@example.com"
                    defaultValue={pendingVerifyEmail ?? verifyEmailProp ?? ""}
                    required
                    disabled={isSubmitting}
                    className={inputBase}
                  />
                </div>
              </div>
              <div>
                <label htmlFor="otp" className="mb-1.5 block text-sm font-medium text-white/50">
                  Verification Code
                </label>
                <div className="relative">
                  <input
                    id="otp"
                    name="otp"
                    type="text"
                    placeholder="Enter the 6-digit code from your email"
                    required
                    disabled={isSubmitting}
                    maxLength={32}
                    className={inputBase}
                  />
                </div>
              </div>
              <button
                type="submit"
                disabled={isSubmitting}
                className="flex w-full items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-blue-500 active:scale-[0.98] disabled:opacity-60"
              >
                {isSubmitting ? (
                  <Loader2 className="h-5 w-5 animate-spin" />
                ) : (
                  "Verify Email"
                )}
              </button>
            </form>
            <p className="mt-4 text-center text-sm text-white/60">
              Didn&apos;t receive the code?{" "}
              <button
                type="button"
                onClick={handleResendVerification}
                disabled={isSubmitting}
                className="font-semibold text-white/80 hover:text-white underline underline-offset-2 transition disabled:opacity-60"
              >
                Resend
              </button>
            </p>
            <p className="mt-4 text-center">
              <button
                type="button"
                onClick={() => {
                  clearMessages();
                  setView("sign-in");
                  router.replace("/auth/sign-in");
                }}
                className="text-sm font-semibold text-white/80 hover:text-white transition"
              >
                ← Back to Sign In
              </button>
            </p>
          </>
        )}
      </div>
    </div>
  );
}
