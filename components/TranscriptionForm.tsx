'use client';

import { useState } from 'react';
import { Loader2, AlertCircle, FileText } from 'lucide-react';
import { authClient } from '@/lib/auth/client';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

interface TranscriptionResult {
  status: 'completed' | 'queued' | 'processing' | 'failed';
  jobId?: string;
  source?: 'youtube_captions' | 'asr';
  language?: string;
  confidence?: number;
  transcript?: string;
  content?: string;  // text/srt/vtt from async jobs
  segments?: any[];
  warnings?: string[];
  error?: string;
}

export function cn(...inputs: (string | undefined | null | false)[]) {
  return twMerge(clsx(inputs));
}

/** Extract user-facing error message from API response (ErrorResponse, FastAPI detail, or job error). */
function extractErrorMessage(data: unknown, fallback = 'Failed to transcribe'): string {
  if (!data || typeof data !== 'object') return fallback;
  const d = data as Record<string, unknown>;
  if (typeof d.message === 'string' && d.message.trim()) return d.message.trim();
  if (typeof d.error === 'string' && d.error.trim()) return d.error.trim();
  const detail = d.detail;
  if (typeof detail === 'string' && detail.trim()) return detail.trim();
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0];
    if (first && typeof first === 'object' && 'msg' in first && typeof (first as { msg: unknown }).msg === 'string') {
      return ((first as { msg: string }).msg).trim();
    }
  }
  return fallback;
}

export default function TranscriptionForm() {
  const { data: session } = authClient.useSession();
  const [url, setUrl] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [inputType, setInputType] = useState<'youtube' | 'url' | 'upload'>('youtube');
  const [format, setFormat] = useState('json');
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [result, setResult] = useState<TranscriptionResult | null>(null);
  const [rawText, setRawText] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const getAuthHeaders = (): HeadersInit => {
    const key = process.env.NEXT_PUBLIC_API_KEY;
    const headers: HeadersInit = key ? { Authorization: `Bearer ${key}` } : {};
    if (session?.user?.id) {
      (headers as Record<string, string>)['X-User-Id'] = session.user.id;
    }
    return headers;
  };

  const pollJob = async (jobId: string) => {
    setStatus('Processing...');
    const startTime = Date.now();
    const timeout = 480000; // 8 minutes max

    while (Date.now() - startTime < timeout) {
      try {
        const res = await fetch(`/api/v1/jobs/${jobId}`, { headers: getAuthHeaders() });
        if (!res.ok) throw new Error('Failed to poll job');
        const data = await res.json();

        if (data.status === 'completed') {
          // Python job response nests transcript in data.result; flatten for display
          const resultData: TranscriptionResult = data.result
            ? { ...data.result, status: 'completed', jobId: data.jobId }
            : data;
          setResult(resultData);
          setStatus(null);
          setLoading(false);
          return;
        }

        if (data.status === 'failed') {
          throw new Error(extractErrorMessage(data, 'Job failed'));
        }

        // Wait 2 seconds before polling again
        await new Promise(resolve => setTimeout(resolve, 2000));
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Polling failed');
        setLoading(false);
        return;
      }
    }
    setError('Job timed out');
    setLoading(false);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);
    setRawText(null);
    setStatus('Starting...');

    try {
      // Python backend expects FormData for all endpoints (proxied to /api/v1/*)
      let endpoint: string;
      const formData = new FormData();

      if (inputType === 'upload') {
        if (!file) throw new Error('Please select a file');
        endpoint = '/api/v1/transcriptions/media';
        formData.append('file', file);
        formData.append('format', format);
      } else {
        // YouTube + URL: use universal transcribe endpoint (handles both)
        endpoint = '/api/v1/transcriptions/transcribe';
        formData.append('url', url);
        formData.append('format', format);
      }

      const res = await fetch(endpoint, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: formData,
      });
      const contentType = res.headers.get('content-type');
      
      if (contentType && contentType.includes('application/json')) {
        const data = await res.json();
        if (!res.ok) throw new Error(extractErrorMessage(data));

        if (data.jobId && (data.status === 'queued' || data.status === 'processing')) {
          // Async flow - poll until completed
          await pollJob(data.jobId);
        } else {
          // Legacy sync flow (YouTube)
          setResult(data);
          setLoading(false);
        }
      } else {
        const text = await res.text();
        if (!res.ok) {
          let errMsg = 'Failed to transcribe';
          try {
            const parsed = JSON.parse(text);
            errMsg = extractErrorMessage(parsed);
          } catch {
            if (text.trim()) errMsg = text.trim();
          }
          throw new Error(errMsg);
        }
        setRawText(text);
        setLoading(false);
      }
      
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to transcribe');
      setLoading(false);
    }
  };

  const renderContent = () => {
    if (result && result.segments && result.segments.length > 0) {
        return (
            <div className="space-y-2">
                {result.segments.map((seg: any, i: number) => (
                    <div key={i} className="flex gap-4 hover:bg-white/5 p-2 rounded transition-colors">
                        <span className="text-white/40 text-xs w-16 shrink-0">{formatTime(seg.start)}</span>
                        <span>{seg.text}</span>
                    </div>
                ))}
            </div>
        );
    }
    
    if (result?.transcript) {
      return (
        <div className="whitespace-pre-wrap">{result.transcript}</div>
      );
    }

    // Text/SRT/VTT formats from async jobs return content + format
    if (result?.content) {
      return (
        <div className="whitespace-pre-wrap font-mono text-sm">{result.content}</div>
      );
    }

    if (rawText) {
        return (
             <div className="whitespace-pre-wrap">{rawText}</div>
        );
    }

    return null;
  };

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="w-full max-w-3xl mx-auto space-y-8 p-4">
      <div className="text-center space-y-2">
        <h1 className="text-4xl font-bold tracking-tight text-white/90">Transcriber Pro</h1>
        <p className="text-white/60">Transcribe YouTube videos, remote media, or local files.</p>
      </div>

      <div className="bg-white/5 border border-white/10 rounded-2xl p-6 shadow-xl backdrop-blur-sm">
        <div className="flex gap-4 mb-6 p-1 bg-black/20 rounded-xl">
          {(['youtube', 'url', 'upload'] as const).map((type) => (
            <button
              key={type}
              onClick={() => {
                setInputType(type);
                setResult(null);
                setError(null);
              }}
              className={cn(
                "flex-1 py-2 px-4 rounded-lg text-sm font-medium transition-all capitalize",
                inputType === type ? "bg-blue-600 text-white" : "text-white/40 hover:text-white/60"
              )}
            >
              {type}
            </button>
          ))}
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="flex flex-col md:flex-row gap-4">
            {inputType !== 'upload' ? (
              <input
                type="text"
                placeholder={inputType === 'youtube' ? "Paste YouTube URL here..." : "Paste Media URL here (mp3, mp4...)"}
                className="flex-1 bg-black/20 border border-white/10 rounded-xl px-4 py-3 text-white placeholder:text-white/30 focus:outline-none focus:ring-2 focus:ring-blue-500/50 transition-all"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                required
              />
            ) : (
              <div className="flex-1">
                <input
                  type="file"
                  id="file-upload"
                  className="hidden"
                  onChange={(e) => setFile(e.target.files?.[0] || null)}
                  accept=".mp3,.wav,.m4a,.mp4,.mkv"
                />
                <label
                  htmlFor="file-upload"
                  className="flex items-center justify-between bg-black/20 border border-white/10 rounded-xl px-4 py-3 text-white/50 cursor-pointer hover:border-white/20 transition-all"
                >
                  <span>{file ? file.name : "Select audio/video file..."}</span>
                  <FileText className="w-5 h-5" />
                </label>
              </div>
            )}
            
            <select
                value={format}
                onChange={(e) => setFormat(e.target.value)}
                className="bg-black/20 border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50 transition-all cursor-pointer"
              >
                <option value="json">JSON</option>
                <option value="text">Text</option>
                <option value="srt">SRT</option>
                <option value="vtt">VTT</option>
              </select>

            <button
              type="submit"
              disabled={loading}
              className="bg-blue-600 hover:bg-blue-500 text-white font-medium px-6 py-3 rounded-xl disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center min-w-[140px]"
            >
              {loading ? (
                <>
                  <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                  {status || 'Processing'}
                </>
              ) : (
                'Transcribe'
              )}
            </button>
          </div>
          {inputType === 'upload' && (
            <p className="text-xs text-white/30 px-1">Max file size: 500MB. Supported: mp3, wav, m4a, mp4, mkv</p>
          )}
        </form>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/20 text-red-200 p-4 rounded-xl flex items-start gap-3">
          <AlertCircle className="w-5 h-5 mt-0.5 shrink-0" />
          <p>{error}</p>
        </div>
      )}

      {(result || rawText) && (
        <div className="space-y-4 animate-in fade-in slide-in-from-bottom-4 duration-500">
          <div className="flex items-center justify-between px-2">
            <h2 className="text-xl font-semibold text-white/80">Result ({format.toUpperCase()})</h2>
             <button 
                onClick={() => {
                    const content = rawText || (result?.content ?? JSON.stringify(result, null, 2));
                    navigator.clipboard.writeText(content);
                }}
                className="text-xs flex items-center gap-2 text-white/60 hover:text-white transition-colors"
             >
                 <FileText className="w-4 h-4" /> Copy
             </button>
          </div>
          
          <div className="bg-black/30 border border-white/5 rounded-2xl p-6 min-h-[200px] max-h-[600px] overflow-y-auto font-mono text-sm leading-relaxed text-white/80">
            {renderContent()}
          </div>
        </div>
      )}
    </div>
  );
}
