"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { authClient } from "@/lib/auth/client";
import { Lock, Loader2 } from "lucide-react";

/** Account settings view - matches CustomAuthView styling (rounded-xl, white/5 cards) */
export function AccountView({ pathname }: { pathname: string }) {
  const { data: session } = authClient.useSession();
  const path = usePathname() ?? pathname;
  const isSettings = path?.includes("settings") ?? true;
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const handleChangePassword = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    const form = e.currentTarget;
    const currentPassword = (
      form.elements.namedItem("currentPassword") as HTMLInputElement
    )?.value;
    const newPassword = (
      form.elements.namedItem("newPassword") as HTMLInputElement
    )?.value;
    if (!currentPassword || !newPassword) {
      setError("Current and new password are required.");
      return;
    }
    if (newPassword.length < 8) {
      setError("New password must be at least 8 characters.");
      return;
    }
    setIsSubmitting(true);
    try {
      const { error: changeError } = await authClient.changePassword({
        currentPassword,
        newPassword,
      });
      if (changeError) {
        setError(changeError.message ?? "Failed to change password.");
        return;
      }
      setSuccess("Password changed successfully.");
      form.reset();
    } catch {
      setError("Failed to change password.");
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!session?.user) {
    return (
      <div className="rounded-2xl bg-white/5 border border-white/10 px-6 py-10">
        <p className="text-white/60">Sign in to view your account.</p>
        <Link
          href="/auth/sign-in"
          className="mt-4 inline-block rounded-xl bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-500"
        >
          Sign in
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col rounded-2xl bg-white/5 border border-white/10 px-6 py-10 shadow-xl backdrop-blur-sm">
        <h1 className="text-2xl font-bold text-white/90">Account</h1>
        <p className="mt-1 text-sm text-white/60">
          Manage your account settings
        </p>

        <div className="mt-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-white/50">
              Name
            </label>
            <p className="mt-1 text-white/90">
              {session.user.name || "—"}
            </p>
          </div>
          <div>
            <label className="block text-sm font-medium text-white/50">
              Email
            </label>
            <p className="mt-1 text-white/90">{session.user.email}</p>
          </div>
        </div>
      </div>

      {isSettings && (
        <div className="flex flex-col rounded-2xl bg-white/5 border border-white/10 px-6 py-10 shadow-xl backdrop-blur-sm">
          <h2 className="text-lg font-bold text-white/90">Change Password</h2>
          <p className="mt-1 text-sm text-white/60">
            Update your password to keep your account secure
          </p>

          {error && (
            <div className="mt-4 rounded-xl bg-red-500/10 border border-red-500/20 px-4 py-3 text-sm text-red-200">
              {error}
            </div>
          )}
          {success && (
            <div className="mt-4 rounded-xl bg-green-500/10 border border-green-500/20 px-4 py-3 text-sm text-green-200">
              {success}
            </div>
          )}

          <form onSubmit={handleChangePassword} className="mt-6 space-y-4">
            <div>
              <label
                htmlFor="currentPassword"
                className="mb-1.5 block text-sm font-medium text-white/50"
              >
                Current Password
              </label>
              <div className="relative">
                <Lock className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-white/40" />
                <input
                  id="currentPassword"
                  name="currentPassword"
                  type="password"
                  required
                  disabled={isSubmitting}
                  className="w-full rounded-xl border border-white/10 bg-black/20 py-3 pl-11 pr-4 text-sm text-white placeholder:text-white/30 focus:outline-none focus:ring-2 focus:ring-blue-500/50 transition disabled:opacity-60"
                  placeholder="Current password"
                />
              </div>
            </div>
            <div>
              <label
                htmlFor="newPassword"
                className="mb-1.5 block text-sm font-medium text-white/50"
              >
                New Password
              </label>
              <div className="relative">
                <Lock className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-white/40" />
                <input
                  id="newPassword"
                  name="newPassword"
                  type="password"
                  required
                  minLength={8}
                  disabled={isSubmitting}
                  className="w-full rounded-xl border border-white/10 bg-black/20 py-3 pl-11 pr-4 text-sm text-white placeholder:text-white/30 focus:outline-none focus:ring-2 focus:ring-blue-500/50 transition disabled:opacity-60"
                  placeholder="New password (min 8 characters)"
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
                "Change Password"
              )}
            </button>
          </form>
        </div>
      )}
    </div>
  );
}
