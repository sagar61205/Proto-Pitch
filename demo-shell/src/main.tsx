import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { ManifestError, parseManifest } from "./manifest";
import { Shell } from "./Shell";

const root = createRoot(document.getElementById("root")!);

fetch("./demo.manifest.json")
  .then((response) => {
    if (!response.ok) throw new ManifestError(`manifest not found (${response.status})`);
    return response.json();
  })
  .then((raw) => {
    const manifest = parseManifest(raw);
    document.title = manifest.title;
    root.render(
      <StrictMode>
        <Shell manifest={manifest} />
      </StrictMode>,
    );
  })
  .catch((error: unknown) => {
    root.render(<p role="alert">This demo cannot be shown: {String(error)}</p>);
  });
