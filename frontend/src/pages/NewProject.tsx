import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { api, type ApiError } from "../api/client";
import { Button, Card, ErrorNotice } from "../components/ui";

const field =
  "mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm";

export function NewProject() {
  const navigate = useNavigate();
  const [company, setCompany] = useState("");
  const [role, setRole] = useState("");
  const [jdUrl, setJdUrl] = useState("");
  const [jdText, setJdText] = useState("");
  const [context, setContext] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const project = await api.createProject({
        company,
        role,
        jd_text: jdText,
        jd_url: jdUrl.trim() || null,
        context: context.trim() || null,
      });
      navigate(`/projects/${project.id}`);
    } catch (reason) {
      setError(reason as ApiError);
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">New project</h1>
      <Card>
        <form className="space-y-4" onSubmit={submit}>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block text-sm font-medium">
              Company
              <input
                className={field}
                value={company}
                onChange={(event) => setCompany(event.target.value)}
                required
                maxLength={200}
              />
            </label>
            <label className="block text-sm font-medium">
              Role
              <input
                className={field}
                value={role}
                onChange={(event) => setRole(event.target.value)}
                required
                maxLength={200}
              />
            </label>
          </div>
          <label className="block text-sm font-medium">
            Job posting URL <span className="font-normal text-slate-500">(optional)</span>
            <input
              className={field}
              type="url"
              value={jdUrl}
              onChange={(event) => setJdUrl(event.target.value)}
              placeholder="https://"
            />
          </label>
          <label className="block text-sm font-medium">
            Job description
            <textarea
              className={`${field} h-64 font-mono`}
              value={jdText}
              onChange={(event) => setJdText(event.target.value)}
              required
              placeholder="Paste the full job description here."
            />
            <span className="mt-1 block text-xs font-normal text-slate-500">
              Stored exactly as pasted and never changed afterwards.
            </span>
          </label>
          <label className="block text-sm font-medium">
            Additional context <span className="font-normal text-slate-500">(optional)</span>
            <textarea
              className={`${field} h-24`}
              value={context}
              onChange={(event) => setContext(event.target.value)}
              placeholder="Anything you already know about the team, product or role."
            />
          </label>
          {error && <ErrorNotice error={error} />}
          <div className="flex justify-end">
            <Button type="submit" variant="primary" disabled={busy}>
              {busy ? "Creating…" : "Create project"}
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
