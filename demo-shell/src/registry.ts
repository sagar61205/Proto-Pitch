import type { ComponentType } from "react";

import type { PanelSpec } from "./manifest";

export type PanelComponent = ComponentType<{ spec: PanelSpec }>;

/** Panel types are registered, not hard-coded: recipes add their own (decision A4). */
const panels = new Map<string, PanelComponent>();

export function registerPanel(type: string, component: PanelComponent): void {
  if (panels.has(type)) throw new Error(`panel type already registered: ${type}`);
  panels.set(type, component);
}

export function resolvePanel(type: string): PanelComponent | undefined {
  return panels.get(type);
}

export function registeredPanelTypes(): string[] {
  return [...panels.keys()].sort();
}
