import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import TodayPage from "./pages/Today";
import ProjectsPage from "./pages/Projects";
import RewardsPage from "./pages/Rewards";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Navigate to="/today" replace />} />
          <Route path="/today" element={<TodayPage />} />
          <Route path="/projects" element={<ProjectsPage />} />
          <Route path="/rewards" element={<RewardsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
