import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { Skeleton } from "./components/ui";
import { useAuth } from "./context/AppContext";
import AppLayout from "./layouts/AppLayout";
const Analytics = lazy(() => import("./pages/Analytics"));
const Cameras = lazy(() => import("./pages/Cameras"));
const LiveMonitoring = lazy(() => import("./pages/LiveMonitoring"));
import Login from "./pages/Login";
const Overview = lazy(() => import("./pages/Overview"));
const Reports = lazy(() => import("./pages/Reports"));
const SettingsPage = lazy(() => import("./pages/Settings"));
const TrafficMap = lazy(() => import("./pages/TrafficMap"));
const VideoAnalysis = lazy(() => import("./pages/VideoAnalysis"));
const Violations = lazy(() => import("./pages/Violations"));

export default function App() {
  const { user, loading } = useAuth();
  if (loading) return <div className="p-10"><Skeleton className="h-10 w-64" /></div>;
  if (!user) return <Routes><Route path="*" element={<Login />} /></Routes>;
  return (
    <Suspense fallback={<div className="p-8"><Skeleton className="h-10 w-64" /></div>}>
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<Overview />} />
        <Route path="live" element={<LiveMonitoring />} />
        <Route path="video" element={<VideoAnalysis />} />
        <Route path="cameras" element={<Cameras />} />
        <Route path="analytics" element={<Analytics />} />
        <Route path="violations" element={<Violations />} />
        <Route path="map" element={<TrafficMap />} />
        <Route path="reports" element={<Reports />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
    </Suspense>
  );
}
