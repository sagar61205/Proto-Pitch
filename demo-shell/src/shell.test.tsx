import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { ManifestError, parseManifest } from "./manifest";
import { registerPanel, registeredPanelTypes } from "./registry";
import { Shell } from "./Shell";

afterEach(cleanup);

const valid = {
  title: "Demo",
  problem: "A problem.",
  disclosures: ["Synthetic data", "Independent demonstration"],
  panels: [{ type: "echo", title: "Echo" }, { type: "missing" }],
};

describe("manifest", () => {
  it("accepts a complete manifest", () => {
    expect(parseManifest(valid).panels).toHaveLength(2);
  });

  it("refuses a manifest without disclosures", () => {
    expect(() => parseManifest({ ...valid, disclosures: [] })).toThrow(ManifestError);
    expect(() => parseManifest({ ...valid, disclosures: undefined })).toThrow(ManifestError);
  });

  it("refuses malformed manifests", () => {
    expect(() => parseManifest(null)).toThrow(ManifestError);
    expect(() => parseManifest({ ...valid, title: " " })).toThrow(ManifestError);
    expect(() => parseManifest({ ...valid, panels: [{}] })).toThrow(ManifestError);
  });
});

describe("shell", () => {
  it("always shows disclosures, renders registered panels and flags unknown ones", () => {
    registerPanel("echo", ({ spec }) => <p>panel {spec.title}</p>);
    expect(registeredPanelTypes()).toEqual(["echo"]);
    expect(() => registerPanel("echo", () => null)).toThrow();
    render(<Shell manifest={parseManifest(valid)} />);
    expect(screen.getByText("Synthetic data")).toBeTruthy();
    expect(screen.getByText("Independent demonstration")).toBeTruthy();
    expect(screen.getByText("panel Echo")).toBeTruthy();
    expect(screen.getByRole("alert").textContent).toContain("missing");
  });
});
