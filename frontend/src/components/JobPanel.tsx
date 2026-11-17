import { useEffect, useRef } from "react";

import type { Job } from "../api/client";
import { useJobLog } from "../api/hooks";
import { formatTime, RunBadge } from "./ui";

const TITLES: Record<string, string> = {
  "project.bootstrap": "Project set-up",
  "sandbox.selftest": "Sandbox isolation self-test",
};

/** A job with its steps and a live log. All text from the server is rendered as text. */
export function JobPanel({ job, onFinished }: { job: Job; onFinished?: () => void }) {
  const lines = useJobLog(job.id, onFinished);
  const logEnd = useRef<HTMLDivElement>(null);
  useEffect(() => {
    logEnd.current?.scrollIntoView?.({ block: "nearest" });
  }, [lines.length]);

  return (
    <article className="rounded-md border border-slate-200" data-testid={`job-${job.type}`}>
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 bg-slate-50 px-4 py-2">
        <h3 className="text-sm font-semibold">{TITLES[job.type] ?? job.type}</h3>
        <div className="flex items-center gap-3 text-xs text-slate-500">
          <span>{formatTime(job.created_at)}</span>
          <span data-testid="job-status">
            <RunBadge status={job.status} />
          </span>
        </div>
      </header>
      <ol className="divide-y divide-slate-100">
        {job.steps.map((step) => (
          <li key={step.index} className="flex items-center justify-between px-4 py-2 text-sm">
            <span className="font-mono text-slate-700">{step.name}</span>
            <span className="flex items-center gap-2 text-xs text-slate-500">
              {step.attempt > 1 && <span>attempt {step.attempt}</span>}
              <RunBadge status={step.status} />
            </span>
          </li>
        ))}
      </ol>
      {job.error && (
        <p role="alert" className="border-t border-red-200 bg-red-50 px-4 py-2 text-sm text-red-900">
          {String(job.error.message ?? "The job failed.")}
        </p>
      )}
      <div
        className="max-h-48 overflow-y-auto border-t border-slate-200 bg-slate-900 px-4 py-2 font-mono text-xs text-slate-100"
        aria-label="Job log"
        role="log"
      >
        {lines.length === 0 && <p className="text-slate-400">Waiting for log output…</p>}
        {lines.map((line) => (
          <p key={line.id} className={line.level === "error" ? "text-red-300" : undefined}>
            {line.message}
          </p>
        ))}
        <div ref={logEnd} />
      </div>
    </article>
  );
}
