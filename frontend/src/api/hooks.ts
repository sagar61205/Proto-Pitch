import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "./client";

export interface Loaded<T> {
  data: T | null;
  error: ApiError | null;
  loading: boolean;
  reload: () => void;
}

/** Load data, optionally re-polling while `pollMs` is set. */
export function useLoad<T>(load: () => Promise<T>, pollMs: number | null = null): Loaded<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);
  const loader = useRef(load);
  loader.current = load;

  const reload = useCallback(() => {
    loader
      .current()
      .then((value) => {
        setData(value);
        setError(null);
      })
      .catch((reason: unknown) => {
        setError(
          reason instanceof ApiError ? reason : new ApiError(0, "unexpected", String(reason), []),
        );
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    reload();
    if (pollMs === null) return;
    const timer = window.setInterval(reload, pollMs);
    return () => window.clearInterval(timer);
  }, [reload, pollMs]);

  return { data, error, loading, reload };
}

export interface LogLine {
  id: number;
  step: string | null;
  level: string;
  message: string;
  created_at: string;
}

/** Follow a job's log over server-sent events. Calls `onEnd` when the job has finished. */
export function useJobLog(jobId: string, onEnd?: () => void): LogLine[] {
  const [lines, setLines] = useState<LogLine[]>([]);
  const end = useRef(onEnd);
  end.current = onEnd;

  useEffect(() => {
    setLines([]);
    const source = new EventSource(`/api/jobs/${jobId}/events`);
    source.addEventListener("log", (event) => {
      const line = JSON.parse((event as MessageEvent<string>).data) as LogLine;
      setLines((current) => (current.some((l) => l.id === line.id) ? current : [...current, line]));
    });
    source.addEventListener("end", () => {
      source.close();
      end.current?.();
    });
    return () => source.close();
  }, [jobId]);

  return lines;
}
