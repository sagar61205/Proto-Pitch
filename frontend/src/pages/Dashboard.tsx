import { useState } from "react";
import { Link } from "react-router-dom";

import { api, type ApiError, type Job } from "../api/client";
import { useLoad } from "../api/hooks";
import { JobPanel } from "../components/JobPanel";
import { Button, Card, ErrorNotice, formatTime, StatusBadge } from "../components/ui";

function SystemCard() {
  const status = useLoad(api.status);
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<ApiError | null>(null);

  async function runSelfTest() {
    setError(null);
    try {
      setJob(await api.sandboxSelftest());
    } catch (reason) {
      setError(reason as ApiError);
    }
  }

  async function refreshJob() {
    if (job) setJob(await api.getJob(job.id));
  }

  if (!status.data) return status.error ? <ErrorNotice error={status.error} /> : null;
  const { sandbox } = status.data;
  const core = sandbox.profiles.find((profile) => profile.profile === "core");
  return (
    <Card title="This installation">
      <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-[auto_1fr]">
        <dt className="text-slate-500">Prototype generation</dt>
        <dd data-testid="generation-status">
          {sandbox.available ? "Available" : `Unavailable — ${sandbox.reason}`}
        </dd>
        <dt className="text-slate-500">Sandbox image</dt>
        <dd className="font-mono text-xs">
          {core?.present ? `${core.image} (${core.image_digest?.slice(0, 19)}…)` : "not built"}
        </dd>
        <dt className="text-slate-500">Model providers</dt>
        <dd>
          {status.data.model_providers_configured.length === 0
            ? "None configured — not needed; the platform runs without any model or API key."
            : status.data.model_providers_configured.join(", ")}
        </dd>
      </dl>
      <div className="mt-4 space-y-3">
        <Button onClick={runSelfTest}>Run sandbox self-test</Button>
        {error && <ErrorNotice error={error} />}
        {job && <JobPanel job={job} onFinished={refreshJob} />}
      </div>
    </Card>
  );
}

export function Dashboard() {
  const [includeArchived, setIncludeArchived] = useState(false);
  const projects = useLoad(() => api.listProjects(includeArchived), 5000);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">Projects</h1>
        <Link
          to="/projects/new"
          className="rounded-md bg-indigo-600 px-3.5 py-2 text-sm font-medium text-white shadow-sm hover:bg-indigo-500"
        >
          New project
        </Link>
      </div>

      {projects.error && <ErrorNotice error={projects.error} />}

      <Card>
        <label className="mb-3 flex items-center gap-2 text-sm text-slate-600">
          <input
            type="checkbox"
            checked={includeArchived}
            onChange={(event) => {
              setIncludeArchived(event.target.checked);
              window.setTimeout(projects.reload, 0);
            }}
          />
          Show archived projects
        </label>
        {projects.data && projects.data.length === 0 && (
          <p className="py-6 text-center text-sm text-slate-600">
            No projects yet. Create one by pasting a job description.
          </p>
        )}
        {projects.data && projects.data.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-slate-200 text-xs uppercase text-slate-500">
                <tr>
                  <th className="py-2 pr-4 font-medium">Company</th>
                  <th className="py-2 pr-4 font-medium">Role</th>
                  <th className="py-2 pr-4 font-medium">Status</th>
                  <th className="py-2 font-medium">Updated</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {projects.data.map((project) => (
                  <tr key={project.id}>
                    <td className="py-2 pr-4 font-medium">
                      <Link className="text-indigo-700 hover:underline" to={`/projects/${project.id}`}>
                        {project.company}
                      </Link>
                    </td>
                    <td className="py-2 pr-4">{project.role}</td>
                    <td className="py-2 pr-4">
                      <StatusBadge status={project.status} />
                    </td>
                    <td className="py-2 text-slate-500">{formatTime(project.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <SystemCard />
    </div>
  );
}
