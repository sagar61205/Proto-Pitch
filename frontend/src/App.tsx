import { Route, Routes } from "react-router-dom";

import { Layout } from "./components/Layout";
import { Dashboard } from "./pages/Dashboard";
import { NewProject } from "./pages/NewProject";
import { ProjectPage } from "./pages/ProjectPage";

export function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/projects/new" element={<NewProject />} />
        <Route path="/projects/:projectId" element={<ProjectPage />} />
        <Route path="*" element={<p className="text-slate-600">This page does not exist.</p>} />
      </Routes>
    </Layout>
  );
}
