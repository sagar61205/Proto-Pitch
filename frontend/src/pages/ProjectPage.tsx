import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { api, type ActionPlan, type ApiError, type OwnerAction } from "../api/client";
import { useLoad } from "../api/hooks";
import { JobPanel } from "../components/JobPanel";
import { LifecycleSteps } from "../components/LifecycleSteps";
import { Button, Card, ErrorNotice, formatTime, StatusBadge } from "../components/ui";

const ACTION_LABELS: Record<OwnerAction, string> = {
  archive: "Archive",
  unarchive: "Restore from archive",
  resume: "Resume from where it failed",
};

function DeleteProject({ projectId }: { projectId: string }) {
  const navigate = useNavigate();
  const [plan, setPlan] = useState<ActionPlan | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  async function run(action: () => Promise<void>) {
    setError(null);
    try {
      await action();
    } catch (reason) {
      setError(reason as ApiError);
    }
  }

  return (
    <Card title="Delete project">
      {!plan && (
        <Button onClick={() => run(async () => setPlan(await api.deletePlan(projectId)))}>
          Review deletion…
        </Button>
      )}
      {plan && (
        <div className="space-y-3 text-sm">
          <p className="font-medium">{plan.summary}</p>
          <ul className="list-disc pl-5 text-slate-700">
            {plan.consequences.map((consequence) => (
              <li key={consequence}>{consequence}</li>
            ))}
          </ul>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(event) => setConfirmed(event.target.checked)}
            />
            I approve exactly this deletion.
          </label>
          <div className="flex gap-2">
            <Button
              variant="danger"
              disabled={!confirmed}
              onClick={() =>
                run(async () => {
                  await api.approveAndDelete(projectId, plan);
                  navigate("/");
                })
              }
            >
              Approve and delete
            </Button>
            <Button onClick={() => setPlan(null)}>Cancel</Button>
          </div>
        </div>
      )}
      {error && (
        <div className="mt-3">
          <ErrorNotice error={error} />
        </div>
      )}
    </Card>
  );
}

export function ProjectPage() {
  const { projectId = "" } = useParams();
  const project = useLoad(() => api.getProject(projectId), 4000);
  const [actionError, setActionError] = useState<ApiError | null>(null);

  async function act(action: OwnerAction) {
    setActionError(null);
    try {
      await api.transition(projectId, action);
      project.reload();
    } catch (reason) {
      setActionError(reason as ApiError);
    }
  }

  if (project.error && !project.data) {
    return (
      <div className="space-y-4">
        <ErrorNotice error={project.error} />
        <Link className="text-sm text-indigo-700 hover:underline" to="/">
          Back to projects
        </Link>
      </div>
    );
  }
  if (!project.data) return <p className="text-sm text-slate-500">Loading…</p>;
  const data = project.data;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm text-slate-500">{data.company}</p>
          <h1 className="text-2xl font-semibold tracking-tight">{data.role}</h1>
          <div className="mt-2 flex items-center gap-3 text-sm text-slate-500">
            <span data-testid="project-status">
              <StatusBadge status={data.status} />
            </span>
            <span>Version {data.active_version}</span>
            <span>Created {formatTime(data.created_at)}</span>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {data.owner_actions.map((action) => (
            <Button
              key={action}
              variant={action === "resume" ? "primary" : "secondary"}
              onClick={() => act(action)}
            >
              {ACTION_LABELS[action]}
            </Button>
          ))}
        </div>
      </div>

      {actionError && <ErrorNotice error={actionError} />}

      {data.status === "FAILED" && data.failure && (
        <div role="alert" className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-900">
          <p className="font-medium">
            This project failed during “{String(data.failure.step ?? "an unknown step")}”.
          </p>
          <p className="mt-1">{String(data.failure.message ?? "")}</p>
          <p className="mt-1">
            Completed work is kept. Fix the cause, then resume to continue from that step.
          </p>
        </div>
      )}

      <Card title="Lifecycle">
        <LifecycleSteps status={data.status} failedFrom={data.failed_from ?? null} />
        <p className="mt-3 text-xs text-slate-500">
          Analysis, research, architecture review, generation and outreach are added by later
          milestones; this page shows only what exists today.
        </p>
      </Card>

      <Card title="Jobs">
        {data.jobs.length === 0 && <p className="text-sm text-slate-600">No jobs yet.</p>}
        <div className="space-y-4">
          {data.jobs.map((job) => (
            <JobPanel key={job.id} job={job} onFinished={project.reload} />
          ))}
        </div>
      </Card>

      <Card title="Job description">
        {data.jd.url && (
          <p className="mb-2 break-all text-sm">
            Source:{" "}
            <a
              className="text-indigo-700 hover:underline"
              href={data.jd.url}
              target="_blank"
              rel="noreferrer noopener"
            >
              {data.jd.url}
            </a>
          </p>
        )}
        <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded-md bg-slate-50 p-4 text-sm">
          {data.jd.text}
        </pre>
        <p className="mt-2 font-mono text-xs text-slate-500">sha256 {data.jd.content_hash}</p>
        {data.context && (
          <div className="mt-4">
            <h3 className="text-sm font-semibold">Additional context</h3>
            <p className="mt-1 whitespace-pre-wrap text-sm text-slate-700">{data.context}</p>
          </div>
        )}
      </Card>

      <DeleteProject projectId={data.id} />
    </div>
  );
}
