import { describe, expect, it } from "vitest";

import { PIPELINE, pipelinePosition, statusLabel, statusTone } from "./lifecycle";

describe("lifecycle presentation", () => {
  it("lists the thirteen pipeline stages in order", () => {
    expect(PIPELINE.map((stage) => stage.status)).toEqual([
      "CREATED", "JD_ANALYZED", "RESEARCHED", "OPPORTUNITIES_IDENTIFIED",
      "ARCHITECTURE_PROPOSED", "AWAITING_APPROVAL", "APPROVED", "GENERATING", "TESTING",
      "READY_FOR_REVIEW", "DEPLOYMENT_PENDING", "DEPLOYED", "OUTREACH_READY",
    ]);
  });

  it("labels every status, including failed and archived", () => {
    expect(statusLabel("AWAITING_APPROVAL")).toBe("Awaiting your approval");
    expect(statusLabel("FAILED")).toBe("Failed");
    expect(statusLabel("ARCHIVED")).toBe("Archived");
  });

  it("draws attention to states that wait for the owner and to failures", () => {
    expect(statusTone("AWAITING_APPROVAL")).toBe("attention");
    expect(statusTone("FAILED")).toBe("danger");
    expect(statusTone("READY_FOR_REVIEW")).toBe("success");
  });

  it("places a failed project at the stage where it failed", () => {
    expect(pipelinePosition("TESTING", null)).toBe(8);
    expect(pipelinePosition("FAILED", "GENERATING")).toBe(7);
  });
});
