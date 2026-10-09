'use client';

import Link from 'next/link';
import { UserButton } from '@/components/auth/UserButton';
import { authClient } from '@/lib/auth/client';

export function NavBar() {
  const { data: session } = authClient.useSession();

  return (
    <nav className="flex items-center justify-between gap-4 px-4 py-3 border-b border-white/5 bg-zinc-950/95 backdrop-blur-md">
      <div className="flex items-center gap-6">
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
        {session && (
          <Link
            href="/usage"
            className="text-zinc-300 hover:text-white transition-colors font-medium"
          >
            Usage
          </Link>
        )}
      </div>
      <div className="flex items-center gap-4">
        <UserButton />
      </div>
    </nav>
  );
}
