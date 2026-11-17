/**
 * The demo manifest (ARCHITECTURE §9). M1 scaffolds the contract and the panel registry;
 * panel types and their rendering are built with the first reference prototype in M4A.
 */
export interface PanelSpec {
  type: string;
  title?: string;
  [option: string]: unknown;
}

export interface DemoManifest {
  title: string;
  problem: string;
  /** Always shown: what is synthetic, simulated or extractive, and that the demo is independent. */
  disclosures: string[];
  panels: PanelSpec[];
}

export class ManifestError extends Error {}

export function parseManifest(value: unknown): DemoManifest {
  if (typeof value !== "object" || value === null) throw new ManifestError("manifest must be an object");
  const candidate = value as Record<string, unknown>;
  const text = (key: string): string => {
    const field = candidate[key];
    if (typeof field !== "string" || !field.trim()) throw new ManifestError(`"${key}" is required`);
    return field;
  };
  const disclosures = candidate.disclosures;
  if (
    !Array.isArray(disclosures) ||
    disclosures.length === 0 ||
    !disclosures.every((item): item is string => typeof item === "string" && item.trim() !== "")
  ) {
    // A demo without disclosures is refused rather than rendered.
    throw new ManifestError("at least one disclosure is required");
  }
  const panels = candidate.panels;
  if (!Array.isArray(panels)) throw new ManifestError('"panels" must be a list');
  for (const panel of panels) {
    if (typeof panel !== "object" || panel === null || typeof (panel as PanelSpec).type !== "string") {
      throw new ManifestError("every panel needs a type");
    }
  }
  return { title: text("title"), problem: text("problem"), disclosures, panels: panels as PanelSpec[] };
}
