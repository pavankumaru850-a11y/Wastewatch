import { lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import ProtectedRoute from "./components/ProtectedRoute";
import Login from "./pages/Login";
import DashboardHome from "./pages/DashboardHome";
import Reports from "./pages/Reports";
import ReportDetails from "./pages/ReportDetails";
const MapPage = lazy(() => import("./pages/MapPage"));
import Users from "./pages/Users";
import Training from "./pages/Training";
const Analytics = lazy(() => import("./pages/Analytics"));
import NotWaste from "./pages/NotWaste";
import Settings from "./pages/Settings";
const Hotspots = lazy(() => import("./pages/Hotspots"));
import AuditLog from "./pages/AuditLog";
import Duplicates from "./pages/Duplicates";
import SystemSettings from "./pages/SystemSettings";
import Notifications from "./pages/Notifications";
import StaffHome from "./pages/StaffHome";
import { useAuth } from "./context/AuthContext";

function Home() {
  const { user } = useAuth();
  return user?.role === "STAFF" ? <StaffHome /> : <DashboardHome />;
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Suspense fallback={<div style={{ padding: 40 }}>Loading...</div>}>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<ProtectedRoute><Home /></ProtectedRoute>} />
          <Route path="/reports" element={<ProtectedRoute><Reports /></ProtectedRoute>} />
          <Route path="/reports/:id" element={<ProtectedRoute><ReportDetails /></ProtectedRoute>} />
          <Route path="/map" element={<ProtectedRoute><MapPage /></ProtectedRoute>} />
          <Route path="/hotspots" element={<ProtectedRoute><Hotspots /></ProtectedRoute>} />
          <Route path="/users" element={<ProtectedRoute adminOnly><Users /></ProtectedRoute>} />
          <Route path="/not-waste" element={<ProtectedRoute adminOnly><NotWaste /></ProtectedRoute>} />
          <Route path="/training" element={<ProtectedRoute adminOnly><Training /></ProtectedRoute>} />
          <Route path="/analytics" element={<ProtectedRoute adminOnly><Analytics /></ProtectedRoute>} />
          <Route path="/audit-log" element={<ProtectedRoute adminOnly><AuditLog /></ProtectedRoute>} />
          <Route path="/duplicates" element={<ProtectedRoute><Duplicates /></ProtectedRoute>} />
          <Route path="/notifications" element={<ProtectedRoute><Notifications /></ProtectedRoute>} />
          <Route path="/system" element={<ProtectedRoute adminOnly><SystemSettings /></ProtectedRoute>} />
          <Route path="/settings" element={<ProtectedRoute><Settings /></ProtectedRoute>} />
        </Routes>
        </Suspense>
      </AuthProvider>
    </BrowserRouter>
  );
}
