import type { ProjectStatus } from "./api/client";

/** The pipeline stages in order, as defined by the platform's lifecycle. */
export const PIPELINE: { status: ProjectStatus; label: string }[] = [
  { status: "CREATED", label: "Created" },
  { status: "JD_ANALYZED", label: "JD analysed" },
  { status: "RESEARCHED", label: "Company researched" },
  { status: "OPPORTUNITIES_IDENTIFIED", label: "Opportunities identified" },
  { status: "ARCHITECTURE_PROPOSED", label: "Architecture proposed" },
  { status: "AWAITING_APPROVAL", label: "Awaiting your approval" },
  { status: "APPROVED", label: "Approved" },
  { status: "GENERATING", label: "Generating" },
  { status: "TESTING", label: "Testing" },
  { status: "READY_FOR_REVIEW", label: "Ready for review" },
  { status: "DEPLOYMENT_PENDING", label: "Deployment pending" },
  { status: "DEPLOYED", label: "Deployed" },
  { status: "OUTREACH_READY", label: "Outreach ready" },
];

const LABELS: Record<ProjectStatus, string> = {
  ...(Object.fromEntries(PIPELINE.map((s) => [s.status, s.label])) as Record<
    ProjectStatus,
    string
  >),
  FAILED: "Failed",
  ARCHIVED: "Archived",
};

export function statusLabel(status: ProjectStatus): string {
  return LABELS[status];
}

export type Tone = "neutral" | "progress" | "attention" | "success" | "danger" | "muted";

export function statusTone(status: ProjectStatus): Tone {
  switch (status) {
    case "FAILED":
      return "danger";
    case "ARCHIVED":
      return "muted";
    case "AWAITING_APPROVAL":
    case "DEPLOYMENT_PENDING":
      return "attention";
    case "READY_FOR_REVIEW":
    case "DEPLOYED":
    case "OUTREACH_READY":
      return "success";
    case "CREATED":
      return "neutral";
    default:
      return "progress";
  }
}

/** Where a project stands in the pipeline; a failed project stands where it failed. */
export function pipelinePosition(status: ProjectStatus, failedFrom: ProjectStatus | null): number {
  const effective = status === "FAILED" && failedFrom ? failedFrom : status;
  return PIPELINE.findIndex((stage) => stage.status === effective);
}
