import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ApiError, toApiError } from "../api/client";
import { LifecycleSteps } from "./LifecycleSteps";
import { ErrorNotice } from "./ui";

describe("LifecycleSteps", () => {
  it("marks earlier stages done and the current stage current", () => {
    render(<LifecycleSteps status="RESEARCHED" failedFrom={null} />);
    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(13);
    expect(items[0]).toHaveAttribute("data-state", "done");
    expect(items[2]).toHaveAttribute("aria-current", "step");
    expect(items[3]).toHaveAttribute("data-state", "upcoming");
  });

  it("shows where a failed project stopped", () => {
    render(<LifecycleSteps status="FAILED" failedFrom="GENERATING" />);
    expect(screen.getByText("failed here").closest("li")).toHaveTextContent("Generating");
  });
});

describe("errors", () => {
  it("shows the platform's message and next actions", () => {
    render(<ErrorNotice error={new ApiError(409, "illegal_transition", "Not allowed.", ["Try X."])} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Not allowed.");
    expect(screen.getByText("Try X.")).toBeInTheDocument();
  });

  it("renders untrusted text as text, never as markup", () => {
    const hostile = '<img src=x onerror="alert(1)">';
    const { container } = render(<ErrorNotice error={new ApiError(400, "x", hostile, [])} />);
    expect(container.querySelector("img")).toBeNull();
    expect(screen.getByRole("alert")).toHaveTextContent(hostile);
  });

  it("parses the API error envelope", async () => {
    const response = new Response(
      JSON.stringify({ error: { code: "not_found", message: "Missing.", next_actions: ["Go back."] } }),
      { status: 404 },
    );
    const error = await toApiError(response);
    expect([error.status, error.code, error.message, error.nextActions]).toEqual([
      404, "not_found", "Missing.", ["Go back."],
    ]);
  });

  it("survives a response that is not JSON", async () => {
    const error = await toApiError(new Response("<html>bad gateway</html>", { status: 502 }));
    expect(error.code).toBe("unexpected");
  });
});
