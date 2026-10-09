"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { authClient } from "@/lib/auth/client";
import { LogOut, User, ChevronDown } from "lucide-react";

/** User button with dropdown - matches NavBar/auth design (rounded-xl, white/10 borders) */
export function UserButton() {
  const { data: session } = authClient.useSession();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const router = useRouter();

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    if (open) document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  if (!session?.user) return null;

  const handleSignOut = async () => {
    setOpen(false);
    await authClient.signOut();
    router.push("/auth/sign-in");
    router.refresh();
  };

  const initials =
    session.user.name
      ?.split(" ")
      .map((n) => n[0])
      .join("")
      .toUpperCase()
      .slice(0, 2) || session.user.email?.[0]?.toUpperCase() || "?";

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white/90 transition hover:bg-white/10 hover:text-white"
      >
        <span
          className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600/80 text-xs font-semibold text-white"
          aria-hidden
        >
          {session.user.image ? (
            <img
              src={session.user.image}
              alt=""
              className="h-8 w-8 rounded-lg object-cover"
            />
          ) : (
            initials
          )}
        </span>
        <span className="hidden sm:inline max-w-[120px] truncate">
          {session.user.name || session.user.email}
        </span>
        <ChevronDown
          className={`h-4 w-4 text-white/60 transition ${open ? "rotate-180" : ""}`}
        />
      </button>

      {open && (
        <div className="absolute right-0 top-full z-50 mt-2 min-w-[180px] rounded-xl border border-white/10 bg-zinc-900/95 py-1 shadow-xl backdrop-blur-md">
          <Link
            href="/account/settings"
            onClick={() => setOpen(false)}
            className="flex items-center gap-2 px-4 py-2.5 text-sm text-white/80 transition hover:bg-white/10 hover:text-white"
          >
            <User className="h-4 w-4" />
            Account
          </Link>
          <button
            type="button"
            onClick={handleSignOut}
            className="flex w-full items-center gap-2 px-4 py-2.5 text-sm text-white/80 transition hover:bg-white/10 hover:text-white"
          >
            <LogOut className="h-4 w-4" />
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}
