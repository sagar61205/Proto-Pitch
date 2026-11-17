import type { ButtonHTMLAttributes, ReactNode } from "react";

import type { ApiError, ProjectStatus } from "../api/client";
import { statusLabel, statusTone, type Tone } from "../lifecycle";

const TONES: Record<Tone, string> = {
  neutral: "bg-slate-100 text-slate-700 ring-slate-300",
  progress: "bg-indigo-50 text-indigo-800 ring-indigo-200",
  attention: "bg-amber-50 text-amber-900 ring-amber-300",
  success: "bg-emerald-50 text-emerald-800 ring-emerald-300",
  danger: "bg-red-50 text-red-800 ring-red-300",
  muted: "bg-slate-50 text-slate-500 ring-slate-200",
};

export function Badge({ tone, children }: { tone: Tone; children: ReactNode }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${TONES[tone]}`}
    >
      {children}
    </span>
  );
}

export function StatusBadge({ status }: { status: ProjectStatus }) {
  return <Badge tone={statusTone(status)}>{statusLabel(status)}</Badge>;
}

const JOB_TONES: Record<string, Tone> = {
  queued: "neutral",
  pending: "neutral",
  running: "progress",
  succeeded: "success",
  failed: "danger",
};

export function RunBadge({ status }: { status: string }) {
  return <Badge tone={JOB_TONES[status] ?? "neutral"}>{status}</Badge>;
}

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "danger";
};

const VARIANTS = {
  primary: "bg-indigo-600 text-white hover:bg-indigo-500 disabled:bg-indigo-300",
  secondary:
    "bg-white text-slate-800 ring-1 ring-inset ring-slate-300 hover:bg-slate-50 disabled:text-slate-400",
  danger: "bg-red-600 text-white hover:bg-red-500 disabled:bg-red-300",
};

export function Button({ variant = "secondary", className = "", ...props }: ButtonProps) {
  return (
    <button
      type="button"
      {...props}
      className={`rounded-md px-3.5 py-2 text-sm font-medium shadow-sm disabled:cursor-not-allowed ${VARIANTS[variant]} ${className}`}
    />
  );
}

export function Card({ title, children }: { title?: string; children: ReactNode }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      {title && <h2 className="mb-3 text-base font-semibold text-slate-900">{title}</h2>}
      {children}
    </section>
  );
}

export function ErrorNotice({ error }: { error: ApiError }) {
  return (
    <div role="alert" className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-900">
      <p className="font-medium">{error.message}</p>
      {error.nextActions.length > 0 && (
        <ul className="mt-2 list-disc pl-5">
          {error.nextActions.map((action) => (
            <li key={action}>{action}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function formatTime(iso: string | null | undefined): string {
  if (!iso) return "";
  return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}
