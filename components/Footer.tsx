import Link from "next/link";

export function Footer() {
  return (
    <footer className="border-t border-white/5 bg-zinc-950/95 px-4 py-4 mt-auto">
      <div className="max-w-4xl mx-auto flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-sm text-white/50">
        <Link href="/privacy" className="hover:text-white/80 transition-colors">
          Privacy Policy
        </Link>
        <Link href="/terms" className="hover:text-white/80 transition-colors">
          Terms of Service
        </Link>
        <span>© {new Date().getFullYear()} Transcriber Pro</span>
      </div>
    </footer>
  );
}
