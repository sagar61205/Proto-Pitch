import type { DemoManifest } from "./manifest";
import { resolvePanel } from "./registry";

export function Shell({ manifest }: { manifest: DemoManifest }) {
  return (
    <main>
      <header>
        <h1>{manifest.title}</h1>
        <p>{manifest.problem}</p>
        <ul aria-label="Disclosures">
          {manifest.disclosures.map((disclosure) => (
            <li key={disclosure}>{disclosure}</li>
          ))}
        </ul>
      </header>
      {manifest.panels.map((spec, index) => {
        const Panel = resolvePanel(spec.type);
        return (
          <section key={`${spec.type}-${index}`} aria-label={spec.title ?? spec.type}>
            {Panel ? (
              <Panel spec={spec} />
            ) : (
              <p role="alert">This demo uses a panel type the shell does not support: {spec.type}</p>
            )}
          </section>
        );
      })}
    </main>
  );
}
