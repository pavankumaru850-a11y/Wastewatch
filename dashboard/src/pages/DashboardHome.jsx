import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import Layout from "../components/Layout";
import StatusBadge from "../components/StatusBadge";
import { dashboardApi, reportsApi } from "../services/resources";
import { API_URL } from "../services/api";
import { useAuth } from "../context/AuthContext";
import { resultLabel } from "../components/ui";

const CARDS = [
  ["total_reports", "Total Reports"],
  ["todays_reports", "Today's Reports"],
  ["pending_verification", "Pending Verification"],
  ["high_priority", "High Priority"],
  ["critical_reports", "Critical Reports"],
  ["active_hotspots", "Active Hotspots"],
  ["completed_cleanups", "Completed Cleanups"],
  ["awaiting_cleanup_verification", "Awaiting Cleanup Check"],
  ["possible_duplicates", "Possible Duplicates"],
  ["avg_resolution_hours", "Avg Resolution (hours)"],
  ["not_waste_reports", "Not Waste (saved separately)"],
];

export default function DashboardHome() {
  const { user } = useAuth();
  const [stats, setStats] = useState(null);
  const [reports, setReports] = useState([]);
  const [notice, setNotice] = useState("");

  async function load() {
    const [s, r] = await Promise.all([dashboardApi.cards(), reportsApi.list({})]);
    setStats(s.data);
    setReports(r.data.slice(0, 8));
  }

  useEffect(() => {
    load();
    // Polling every 5s for new reports, as the spec explicitly allows
    // for a first implementation instead of a WebSocket.
    let lastCheck = new Date().toISOString();
    const interval = setInterval(async () => {
      try {
        const res = await dashboardApi.recent(lastCheck);
        if (res.data.count > 0) {
          setNotice(`${res.data.count} new report${res.data.count > 1 ? "s" : ""} received.`);
          load();
        }
        lastCheck = res.data.server_time;
      } catch {
        /* ignore transient polling errors */
      }
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <Layout title={user?.role === "ADMIN" ? "Dashboard" : "My Dashboard"}>
      {notice && (
        <div className="card" style={{ marginBottom: 16, borderColor: "var(--brand)", background: "#eef6f0" }}>
          {notice}
        </div>
      )}
      {stats && (
        <div className="stat-grid">
          {CARDS.map(([key, label]) => (
            <div className="stat-card" key={key}>
              <div className="value">{stats[key] ?? "-"}</div>
              <div className="label">{label}</div>
            </div>
          ))}
        </div>
      )}

      <div className="card">
        <h2>Recent reports</h2>
        <table>
          <thead>
            <tr>
              <th>Image</th><th>ID</th><th>AI Result</th><th>Village</th><th>Status</th><th>Severity</th><th>Priority</th><th></th>
            </tr>
          </thead>
          <tbody>
            {reports.map((r) => (
              <tr key={r.id}>
                <td><img className="badge-thumb" src={`${API_URL}/${r.image_path}`} alt="" /></td>
                <td>WW-{String(r.id).padStart(6, "0")}</td>
                <td>{resultLabel(r)}</td>
                <td>{r.village || "-"}</td>
                <td><StatusBadge status={r.status} /></td>
                <td>{r.severity || "-"}</td>
                <td>{r.priority}{r.priority_score != null ? ` (${Math.round(r.priority_score)})` : ""}</td>
                <td><Link to={`/reports/${r.id}`}>View</Link></td>
              </tr>
            ))}
            {reports.length === 0 && (
              <tr><td colSpan={8} className="muted">No reports yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </Layout>
  );
}
