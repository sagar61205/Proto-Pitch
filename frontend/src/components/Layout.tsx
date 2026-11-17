import type { ReactNode } from "react";
import { Link, NavLink } from "react-router-dom";

import { api } from "../api/client";
import { useLoad } from "../api/hooks";

const link = ({ isActive }: { isActive: boolean }) =>
  `rounded-md px-3 py-2 text-sm font-medium ${
    isActive ? "bg-indigo-50 text-indigo-800" : "text-slate-600 hover:bg-slate-100"
  }`;

export function Layout({ children }: { children: ReactNode }) {
  const status = useLoad(api.status, 10_000);
  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
          <Link to="/" className="text-lg font-semibold tracking-tight text-slate-900">
            ProtoPitch
          </Link>
          <nav className="flex gap-1" aria-label="Main">
            <NavLink to="/" end className={link}>
              Dashboard
            </NavLink>
            <NavLink to="/projects/new" className={link}>
              New project
            </NavLink>
          </nav>
        </div>
      </header>
      {status.data && !status.data.worker_online && (
        <div className="border-b border-amber-200 bg-amber-50" data-testid="worker-notice">
          <p className="mx-auto max-w-6xl px-4 py-2 text-sm text-amber-900">
            <span className="font-medium">No worker is running.</span> New jobs will wait in the
            queue until one starts (`make start` runs one automatically).
          </p>
        </div>
      )}
      {status.data && status.data.worker_online && !status.data.generation_available && (
        <div className="border-b border-amber-200 bg-amber-50" data-testid="generation-notice">
          <p className="mx-auto max-w-6xl px-4 py-2 text-sm text-amber-900">
            <span className="font-medium">Prototype generation is unavailable.</span>{" "}
            {status.data.sandbox.reason} Projects, job descriptions and reviews work normally.
          </p>
        </div>
      )}
      <main className="mx-auto max-w-6xl px-4 py-8">{children}</main>
    </div>
  );
}
