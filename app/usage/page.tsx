'use client';

import { Suspense, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { authClient } from '@/lib/auth/client';
import { Loader2, CreditCard, History, AlertCircle, Copy, Check, Key } from 'lucide-react';

interface Credits {
  balanceMinutes: number;
  freePlanAsrMinutesUsed: number;
  /** Effective free ASR used (IP-capped). Use for display instead of freePlanAsrMinutesUsed. */
  freePlanAsrMinutesEffectiveUsed?: number;
  freePlanYoutubeUsed: number;
  remainingAsrMinutes: number;
  isUnlimited?: boolean;
}

interface HistoryJob {
  jobId: string;
  source: string;
  status: string;
  durationMinutes: number | null;
  minutesCharged: number;
  errorMessage: string | null;
  createdAt: string | null;
  completedAt: string | null;
  sourceUrl?: string | null;
  transcript?: string | null;
}

function UsagePageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { data: session } = authClient.useSession();
  const [credits, setCredits] = useState<Credits | null>(null);
  const [history, setHistory] = useState<HistoryJob[]>([]);
  const [historyPage, setHistoryPage] = useState(1);
  const [historyTotal, setHistoryTotal] = useState(0);
  const [historyTotalPages, setHistoryTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [topUpLoading, setTopUpLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<'usage' | 'history' | 'api'>('usage');
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [topUpAmount, setTopUpAmount] = useState<string>('5');
  const [topUpError, setTopUpError] = useState<string | null>(null);
  const [apiKeyPrefix, setApiKeyPrefix] = useState<string | null>(null);
  const [apiKeyPlain, setApiKeyPlain] = useState<string | null>(null);
  const [apiKeyLoading, setApiKeyLoading] = useState(false);
  const [apiKeyCopied, setApiKeyCopied] = useState(false);
  const topupSuccess = searchParams.get('topup') === 'success';

  const TOP_UP_PRESETS = [5, 10, 20, 50];
  const MIN_TOP_UP = 5;
  const MAX_TOP_UP = 5000;

  const copyTranscript = async (jobId: string, transcript: string) => {
    try {
      await navigator.clipboard.writeText(transcript);
      setCopiedId(jobId);
      setTimeout(() => setCopiedId(null), 2000);
    } catch {
      // ignore
    }
  };

  const fetchApiKey = async () => {
    if (!session?.user?.id) return;
    setApiKeyLoading(true);
    try {
      const res = await fetch('/api/v1/credits/api-key', { headers: getAuthHeaders() });
      const data = await res.json();
      if (data.keyPrefix) setApiKeyPrefix(data.keyPrefix);
      if (data.plainKey) setApiKeyPlain(data.plainKey);
    } finally {
      setApiKeyLoading(false);
    }
  };

  const regenerateApiKey = async () => {
    if (!session?.user?.id) return;
    setApiKeyLoading(true);
    setApiKeyPlain(null);
    try {
      const headers = getAuthHeaders();
      (headers as Record<string, string>)['Content-Type'] = 'application/json';
      const res = await fetch('/api/v1/credits/api-key/regenerate', {
        method: 'POST',
        headers,
      });
      const data = await res.json();
      if (data.plainKey) {
        setApiKeyPlain(data.plainKey);
        setApiKeyPrefix(data.keyPrefix ?? data.plainKey.slice(0, 12) + '...');
      }
    } finally {
      setApiKeyLoading(false);
    }
  };

  const copyApiKey = async () => {
    const toCopy = apiKeyPlain ?? '';
    if (!toCopy) return;
    try {
      await navigator.clipboard.writeText(toCopy);
      setApiKeyCopied(true);
      setTimeout(() => setApiKeyCopied(false), 2000);
    } catch {
      // ignore
    }
  };

  const getAuthHeaders = (): HeadersInit => {
    const key = process.env.NEXT_PUBLIC_API_KEY;
    const headers: HeadersInit = key ? { Authorization: `Bearer ${key}` } : {};
    if (session?.user?.id) {
      (headers as Record<string, string>)['X-User-Id'] = session.user.id;
    }
    return headers;
  };

  const HISTORY_PAGE_SIZE = 5;

  useEffect(() => {
    if (!session?.user?.id) {
      router.replace('/');
      return;
    }
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      try {
        const [credRes, histRes] = await Promise.all([
          fetch('/api/v1/credits', { headers: getAuthHeaders() }),
          fetch(
            `/api/v1/credits/history?page=${historyPage}&limit=${HISTORY_PAGE_SIZE}`,
            { headers: getAuthHeaders() }
          ),
        ]);
        if (credRes.ok) {
          const data = await credRes.json();
          setCredits(data);
        } else {
          let msg = 'Could not load credits';
          try {
            const errBody = await credRes.json();
            const d = errBody?.detail ?? errBody?.message ?? errBody?.error;
            if (typeof d === 'string') msg = `${msg}: ${d}`;
            else if (Array.isArray(d)) msg = `${msg}: ${d.map((e: { msg?: string }) => e?.msg).filter(Boolean).join(', ')}`;
          } catch {
            // ignore
          }
          setError(`${msg} (${credRes.status})`);
        }
        if (histRes.ok) {
          const data = await histRes.json();
          setHistory(data.jobs ?? []);
          setHistoryTotal(data.total ?? 0);
          setHistoryTotalPages(data.totalPages ?? 1);
        }
      } catch {
        setError('Failed to load data');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [session?.user?.id, router, historyPage]);

  const parseTopUpAmount = (): number | null => {
    const trimmed = topUpAmount.trim();
    if (!trimmed) return null;
    const num = parseFloat(trimmed);
    if (Number.isNaN(num)) return null;
    if (num < MIN_TOP_UP) return null;
    if (num > MAX_TOP_UP) return null;
    return num;
  };

  const handleTopUp = async () => {
    if (!session?.user?.id) return;
    setTopUpError(null);
    setError(null);
    const amountPounds = parseTopUpAmount();
    if (amountPounds === null) {
      setTopUpError(
        `Enter a valid amount between £${MIN_TOP_UP} and £${MAX_TOP_UP}`
      );
      return;
    }
    const amountPence = Math.round(amountPounds * 100);
    if (amountPence < 500) {
      setTopUpError('Minimum top-up is £5');
      return;
    }
    setTopUpLoading(true);
    try {
      const headers = getAuthHeaders();
      (headers as Record<string, string>)['Content-Type'] = 'application/json';
      const res = await fetch('/api/v1/credits/checkout', {
        method: 'POST',
        headers,
        body: JSON.stringify({
          success_url: `${window.location.origin}/usage?topup=success`,
          cancel_url: `${window.location.origin}/usage`,
          amount_pence: amountPence,
        }),
      });
      const data = await res.json();
      if (data.url) {
        window.location.href = data.url;
      } else {
        setError(data.detail || 'Failed to create checkout');
        setTopUpLoading(false);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create checkout');
      setTopUpLoading(false);
    }
  };

  const formatDate = (iso: string | null) => {
    if (!iso) return '—';
    const d = new Date(iso);
    return d.toLocaleString();
  };

  if (!session) {
    return null;
  }

  return (
    <main className="min-h-screen bg-[#0a0a0a] bg-[radial-gradient(ellipse_80%_80%_at_50%_-20%,rgba(120,119,198,0.3),rgba(255,255,255,0))] p-4">
      <div className="max-w-2xl mx-auto space-y-6">
        <h1 className="text-2xl font-bold text-white/90">Usage & Credits</h1>

        {topupSuccess && (
          <div className="bg-green-500/10 border border-green-500/20 text-green-200 p-4 rounded-xl">
            Top-up successful. Your credits will appear shortly.
          </div>
        )}

        {error && (
          <div className="bg-red-500/10 border border-red-500/20 text-red-200 p-4 rounded-xl flex items-start gap-3">
            <AlertCircle className="w-5 h-5 mt-0.5 shrink-0" />
            <p>{error}</p>
          </div>
        )}

        <div className="flex gap-2 p-1 bg-black/20 rounded-xl">
          <button
            onClick={() => setTab('usage')}
            className={`flex-1 py-2 px-4 rounded-lg text-sm font-medium transition-all flex items-center justify-center gap-2 ${
              tab === 'usage' ? 'bg-blue-600 text-white' : 'text-white/40 hover:text-white/60'
            }`}
          >
            <CreditCard className="w-4 h-4" /> Usage
          </button>
          <button
            onClick={() => setTab('history')}
            className={`flex-1 py-2 px-4 rounded-lg text-sm font-medium transition-all flex items-center justify-center gap-2 ${
              tab === 'history' ? 'bg-blue-600 text-white' : 'text-white/40 hover:text-white/60'
            }`}
          >
            <History className="w-4 h-4" /> History
          </button>
          <button
            onClick={() => {
              setTab('api');
              fetchApiKey();
            }}
            className={`flex-1 py-2 px-4 rounded-lg text-sm font-medium transition-all flex items-center justify-center gap-2 ${
              tab === 'api' ? 'bg-blue-600 text-white' : 'text-white/40 hover:text-white/60'
            }`}
          >
            <Key className="w-4 h-4" /> API
          </button>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-white/40" />
          </div>
        ) : tab === 'api' ? (
          <div className="bg-white/5 border border-white/10 rounded-2xl p-6 space-y-6">
            <h2 className="text-lg font-semibold text-white/80">API Access</h2>
            <p className="text-sm text-white/60">
              Use your personal API key for programmatic access (e.g. Apple Shortcuts, curl, scripts).
              Credits are deducted from your account.
            </p>
            {apiKeyLoading ? (
              <div className="flex items-center gap-2 text-white/60">
                <Loader2 className="w-5 h-5 animate-spin" />
                Loading...
              </div>
            ) : (
              <div className="space-y-4">
                <div className="flex flex-wrap items-center gap-3">
                  <code className="px-3 py-2 rounded-lg bg-black/30 text-white/90 font-mono text-sm">
                    {apiKeyPrefix ?? 'No key yet'}
                  </code>
                  {apiKeyPlain ? (
                    <button
                      onClick={copyApiKey}
                      className="flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium transition-colors"
                    >
                      {apiKeyCopied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                      {apiKeyCopied ? 'Copied' : 'Copy key'}
                    </button>
                  ) : apiKeyPrefix ? (
                    <button
                      onClick={regenerateApiKey}
                      className="px-4 py-2 rounded-lg bg-white/10 text-white/80 hover:bg-white/20 text-sm font-medium transition-colors"
                    >
                      Regenerate
                    </button>
                  ) : (
                    <button
                      onClick={fetchApiKey}
                      className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium transition-colors"
                    >
                      Generate API key
                    </button>
                  )}
                </div>
                {apiKeyPlain && (
                  <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-200 text-sm">
                    Copy your key now. It won&apos;t be shown again.
                  </div>
                )}
                <div className="text-xs text-white/40 space-y-1">
                  <p>Example (curl):</p>
                  <pre className="mt-1 p-3 rounded-lg bg-black/30 overflow-x-auto text-white/70">
{`curl -X POST "http://your-domain.com/v1/transcriptions/transcribe" \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  -F "url=https://www.youtube.com/watch?v=VIDEO_ID" \\
  -F "format=json"`}
                  </pre>
                </div>
              </div>
            )}
          </div>
        ) : tab === 'usage' ? (
          <div className="bg-white/5 border border-white/10 rounded-2xl p-6 space-y-6">
            {credits?.isUnlimited ? (
              <div className="p-4 rounded-xl bg-green-500/10 border border-green-500/20">
                <h2 className="text-lg font-semibold text-green-200">Unlimited (owner account)</h2>
                <p className="text-sm text-white/60 mt-1">
                  No credit deductions. Transcribe as much as you need.
                </p>
              </div>
            ) : (
              <>
            <div>
              <h2 className="text-sm text-white/50 mb-1">Minutes remaining</h2>
              <p className="text-4xl font-bold text-white/90">
                {credits ? Math.round(credits.remainingAsrMinutes) : '—'}
              </p>
              <p className="text-sm text-white/40 mt-1">
                Free plan: {credits ? (credits.freePlanAsrMinutesEffectiveUsed ?? credits.freePlanAsrMinutesUsed).toFixed(1) : 0}/10 mins used •{' '}
                {credits?.freePlanYoutubeUsed ?? 0}/5 YouTube used
              </p>
            </div>
            <div>
              <h2 className="text-sm text-white/50 mb-1">Paid balance</h2>
              <p className="text-xl font-semibold text-white/80">
                {credits?.balanceMinutes ?? 0} minutes
              </p>
            </div>
            <div>
              <p className="text-sm text-white/50 mb-3">
                Top up any amount. Minimum £5.
              </p>
              <div className="flex flex-wrap gap-2 mb-3">
                {TOP_UP_PRESETS.map((preset) => (
                  <button
                    key={preset}
                    type="button"
                    onClick={() => {
                      setTopUpAmount(String(preset));
                      setTopUpError(null);
                    }}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                      topUpAmount === String(preset)
                        ? 'bg-blue-600 text-white'
                        : 'bg-white/10 text-white/80 hover:bg-white/20'
                    }`}
                  >
                    £{preset}
                  </button>
                ))}
              </div>
              <div className="flex flex-wrap items-end gap-2 mb-3">
                <div>
                  <label htmlFor="topup-amount" className="block text-xs text-white/50 mb-1">
                    Or enter amount (£)
                  </label>
                  <input
                    id="topup-amount"
                    type="number"
                    min={MIN_TOP_UP}
                    max={MAX_TOP_UP}
                    step="0.01"
                    value={topUpAmount}
                    onChange={(e) => {
                      setTopUpAmount(e.target.value);
                      setTopUpError(null);
                    }}
                    onBlur={() => {
                      const parsed = parseTopUpAmount();
                      if (parsed !== null) setTopUpAmount(String(parsed));
                    }}
                    placeholder="e.g. 15"
                    className="w-28 px-3 py-2 rounded-lg bg-black/30 border border-white/20 text-white placeholder-white/40 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                </div>
                <button
                  onClick={handleTopUp}
                  disabled={topUpLoading}
                  className="bg-blue-600 hover:bg-blue-500 text-white font-medium px-6 py-2.5 rounded-xl disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
                >
                  {topUpLoading ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin" />
                      Redirecting...
                    </>
                  ) : (
                    <>
                      <CreditCard className="w-5 h-5" />
                      Top up
                    </>
                  )}
                </button>
              </div>
              {topUpError && (
                <p className="text-sm text-red-400/90">{topUpError}</p>
              )}
              {(() => {
                const amt = parseTopUpAmount();
                return amt !== null ? (
                  <p className="text-xs text-white/40 mt-1">
                    £{amt} = {Math.floor((amt * 100) / 2)} minutes
                  </p>
                ) : null;
              })()}
            </div>
              </>
            )}
          </div>
        ) : (
          <div className="bg-white/5 border border-white/10 rounded-2xl p-6">
            <h2 className="text-lg font-semibold text-white/80 mb-4">Transcription history</h2>
            {history.length === 0 ? (
              <p className="text-white/50">No transcriptions yet.</p>
            ) : (
              <>
              <div className="space-y-4">
                {history.map((job) => (
                  <div
                    key={job.jobId}
                    className="p-4 bg-black/20 rounded-xl space-y-3"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-3">
                        <span
                          className={`text-xs font-medium px-2 py-1 rounded ${
                            job.status === 'completed'
                              ? 'bg-green-500/20 text-green-200'
                              : job.status === 'failed'
                            ? 'bg-red-500/20 text-red-200'
                            : 'bg-white/10 text-white/60'
                          }`}
                        >
                          {job.status}
                        </span>
                        <span className="text-white/60 text-sm">{job.source}</span>
                        {job.durationMinutes != null && (
                          <span className="text-white/40 text-xs">
                            {job.durationMinutes.toFixed(1)} min
                          </span>
                        )}
                      </div>
                      <div className="text-right text-sm">
                        {job.status === 'completed' && job.minutesCharged > 0 && (
                          <span className="text-white/60">{job.minutesCharged.toFixed(1)} min used</span>
                        )}
                        {job.status === 'failed' && (
                          <span className="text-red-400/80 text-xs">You were not charged</span>
                        )}
                      </div>
                    </div>
                    {job.sourceUrl && (
                      <div className="text-xs">
                        <span className="text-white/40">
                          {job.sourceUrl.startsWith('upload:') ? 'Source: ' : 'URL: '}
                        </span>
                        {job.sourceUrl.startsWith('http') ? (
                          <a
                            href={job.sourceUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-400 hover:text-blue-300 break-all"
                          >
                            {job.sourceUrl}
                          </a>
                        ) : (
                          <span className="text-white/70">{job.sourceUrl}</span>
                        )}
                      </div>
                    )}
                    {job.transcript && job.status === 'completed' && (
                      <div className="space-y-1">
                        <div className="flex items-center justify-between">
                          <span className="text-xs text-white/40">Transcript</span>
                          <button
                            onClick={() => copyTranscript(job.jobId, job.transcript!)}
                            className="flex items-center gap-1 text-xs text-white/60 hover:text-white/90 transition-colors"
                          >
                            {copiedId === job.jobId ? (
                              <>
                                <Check className="w-3.5 h-3.5" /> Copied
                              </>
                            ) : (
                              <>
                                <Copy className="w-3.5 h-3.5" /> Copy
                              </>
                            )}
                          </button>
                        </div>
                        <pre className="text-sm text-white/80 bg-black/30 p-3 rounded-lg overflow-x-auto max-h-40 overflow-y-auto whitespace-pre-wrap break-words">
                          {job.transcript}
                        </pre>
                      </div>
                    )}
                    {job.errorMessage && (
                      <div className="mt-2 bg-red-500/10 border border-red-500/20 rounded-lg p-3 flex items-start gap-2">
                        <AlertCircle className="w-4 h-4 text-red-400 mt-0.5 shrink-0" />
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-medium text-red-300">Error</div>
                          <div className="text-sm text-red-200/80 break-words">{job.errorMessage}</div>
                        </div>
                      </div>
                    )}
                    <div className="text-xs text-white/40">{formatDate(job.createdAt)}</div>
                  </div>
                ))}
              </div>
              {historyTotalPages > 1 && (
                <div className="mt-4 flex items-center justify-between">
                  <button
                    onClick={() => setHistoryPage((p) => Math.max(1, p - 1))}
                    disabled={historyPage <= 1}
                    className="px-4 py-2 rounded-lg bg-white/10 text-white/80 hover:bg-white/20 disabled:opacity-40 disabled:cursor-not-allowed transition-colors text-sm"
                  >
                    Previous
                  </button>
                  <span className="text-sm text-white/60">
                    Page {historyPage} of {historyTotalPages} ({historyTotal} total)
                  </span>
                  <button
                    onClick={() => setHistoryPage((p) => Math.min(historyTotalPages, p + 1))}
                    disabled={historyPage >= historyTotalPages}
                    className="px-4 py-2 rounded-lg bg-white/10 text-white/80 hover:bg-white/20 disabled:opacity-40 disabled:cursor-not-allowed transition-colors text-sm"
                  >
                    Next
                  </button>
                </div>
              )}
              </>
            )}
          </div>
        )}

        <Link href="/" className="inline-block text-white/60 hover:text-white/90 transition-colors">
          ← Back to Transcribe
        </Link>
      </div>
    </main>
  );
}

export default function UsagePage() {
  return (
    <Suspense fallback={
      <main className="min-h-screen bg-[#0a0a0a] bg-[radial-gradient(ellipse_80%_80%_at_50%_-20%,rgba(120,119,198,0.3),rgba(255,255,255,0))] p-4 flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-white/40" />
      </main>
    }>
      <UsagePageContent />
    </Suspense>
  );
}
