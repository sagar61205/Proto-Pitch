import type { components } from "./schema";

type Schemas = components["schemas"];
export type Project = Schemas["ProjectOut"];
export type ProjectDetail = Schemas["ProjectDetail"];
export type ProjectCreate = Schemas["ProjectCreate"];
export type Job = Schemas["JobOut"];
export type Step = Schemas["StepOut"];
export type SystemStatus = Schemas["SystemStatus"];
export type ActionPlan = Schemas["ActionPlan"];
export type ProjectStatus = Schemas["ProjectStatus"];
export type OwnerAction = Project["owner_actions"][number];

export class ApiError extends Error {
  readonly code: string;
  readonly nextActions: string[];
  readonly status: number;

  constructor(status: number, code: string, message: string, nextActions: string[]) {
    super(message);
    this.status = status;
    this.code = code;
    this.nextActions = nextActions;
  }
}

/** Turn any failed response into an ApiError with the platform's code, message and advice. */
export async function toApiError(response: Response): Promise<ApiError> {
  try {
    const body = (await response.json()) as { error?: Schemas["ErrorBody"] };
    if (body.error) {
      return new ApiError(
        response.status,
        body.error.code,
        body.error.message,
        body.error.next_actions ?? [],
      );
    }
  } catch {
    // fall through to the generic error
  }
  return new ApiError(response.status, "unexpected", `The server answered ${response.status}.`, []);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      ...init,
      headers: init?.body ? { "Content-Type": "application/json" } : undefined,
    });
  } catch {
    throw new ApiError(0, "unreachable", "ProtoPitch is not reachable. Is the server running?", [
      "Start it with `make start` and reload this page.",
    ]);
  }
  if (!response.ok) throw await toApiError(response);
  return response.status === 204 ? (undefined as T) : ((await response.json()) as T);
}

const json = (method: string, body: unknown): RequestInit => ({
  method,
  body: JSON.stringify(body),
});

export const api = {
  status: () => request<SystemStatus>("/system/status"),
  sandboxSelftest: () => request<Job>("/system/sandbox-selftest", { method: "POST" }),
  listProjects: (includeArchived: boolean) =>
    request<Project[]>(`/projects?include_archived=${includeArchived}`),
  getProject: (id: string) => request<ProjectDetail>(`/projects/${id}`),
  createProject: (body: ProjectCreate) => request<ProjectDetail>("/projects", json("POST", body)),
  transition: (id: string, action: OwnerAction) =>
    request<ProjectDetail>(`/projects/${id}/transitions`, json("POST", { action })),
  getJob: (id: string) => request<Job>(`/jobs/${id}`),
  deletePlan: (id: string) => request<ActionPlan>(`/projects/${id}/delete-plan`),
  /** Record the owner's approval for exactly this plan, then carry out the deletion. */
  approveAndDelete: async (id: string, plan: ActionPlan) => {
    await request(
      "/approvals",
      json("POST", {
        kind: plan.kind,
        payload_hash: plan.payload_hash,
        decision: "approved",
        project_id: id,
      }),
    );
    await request<void>(`/projects/${id}`, { method: "DELETE" });
  },
};
