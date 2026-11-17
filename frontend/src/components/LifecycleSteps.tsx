import type { ProjectStatus } from "../api/client";
import { PIPELINE, pipelinePosition } from "../lifecycle";

export function LifecycleSteps({
  status,
  failedFrom,
}: {
  status: ProjectStatus;
  failedFrom: ProjectStatus | null;
}) {
  const position = pipelinePosition(status, failedFrom);
  const failed = status === "FAILED";
  return (
    <ol className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3" aria-label="Project lifecycle">
      {PIPELINE.map((stage, index) => {
        const state = index < position ? "done" : index === position ? "current" : "upcoming";
        const tone =
          state === "done"
            ? "border-emerald-200 bg-emerald-50 text-emerald-900"
            : state === "current"
              ? failed
                ? "border-red-300 bg-red-50 text-red-900"
                : "border-indigo-300 bg-indigo-50 text-indigo-900"
              : "border-slate-200 bg-white text-slate-500";
        return (
          <li
            key={stage.status}
            data-state={state}
            aria-current={state === "current" ? "step" : undefined}
            className={`flex items-center gap-2 rounded-md border px-3 py-2 text-sm ${tone}`}
          >
            <span className="font-mono text-xs opacity-70">{index + 1}</span>
            <span>{stage.label}</span>
            {state === "current" && failed && <span className="ml-auto text-xs">failed here</span>}
          </li>
        );
      })}
    </ol>
  );
}
