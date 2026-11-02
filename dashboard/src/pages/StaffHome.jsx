import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import Layout from "../components/Layout";
import StatusBadge from "../components/StatusBadge";
import { SeverityBadge, rid } from "../components/ui";
import { dashboardApi, reportsApi } from "../services/resources";
import { useAuth } from "../context/AuthContext";

function km(a, b) {
  const R = 6371, rad = (d) => (d * Math.PI) / 180;
  const dLat = rad(b.lat - a.lat), dLng = rad(b.lng - a.lng);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

function Section({ title, hint, rows, empty }) {
  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <h2>{title} <span className="muted">({rows.length})</span></h2>
      {hint && <p className="muted">{hint}</p>}
      {rows.length === 0 ? <p className="muted">{empty}</p> : (
        <table>
          <thead><tr><th>Report</th><th>Waste</th><th>Severity</th><th>Priority</th><th>Status</th><th>Village</th><th>Reported</th><th></th></tr></thead>
          <tbody>
            {rows.slice(0, 8).map((r) => (
              <tr key={r.id}>
                <td>{rid(r.id)}</td><td>{r.waste_type || "-"}</td><td><SeverityBadge level={r.severity} /></td>
                <td>{r.priority}{r.priority_score != null ? ` (${Math.round(r.priority_score)})` : ""}</td>
                <td><StatusBadge status={r.status} /></td><td>{r.village || "-"}</td>
                <td>{new Date(r.created_at).toLocaleDateString()}</td>
                <td><Link to={`/reports/${r.id}`}>Open</Link>{r.dist != null ? ` · ${r.dist.toFixed(1)} km` : ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {rows.length > 8 && <p className="muted">+ {rows.length - 8} more &mdash; see Reports for the full list.</p>}
    </div>
  );
}

export default function StaffHome() {
  const { user } = useAuth();
  const [reports, setReports] = useState([]);
  const [cards, setCards] = useState(null);
  const [pos, setPos] = useState(null);
  const [radius, setRadius] = useState(5);
  const [geoMsg, setGeoMsg] = useState("");

  useEffect(() => {
    reportsApi.list({}).then((r) => setReports(r.data)).catch(() => {});
    dashboardApi.cards().then((r) => setCards(r.data)).catch(() => {});
  }, []);

  function locate() {
    if (!navigator.geolocation) { setGeoMsg("This browser cannot provide your location."); return; }
    navigator.geolocation.getCurrentPosition(
      (p) => { setPos({ lat: p.coords.latitude, lng: p.coords.longitude }); setGeoMsg(""); },
      () => setGeoMsg("Location unavailable. Allow location access in your browser and retry."),
      { timeout: 8000 });
  }

  const mine = (r) => r.assignment?.staff_id === user.id;
  const open = (r) => !["CLOSED", "COMPLETED", "REJECTED"].includes(r.status);
  const groups = useMemo(() => ({
    tasks: reports.filter((r) => mine(r) && ["ASSIGNED", "IN_PROGRESS"].includes(r.status)),
    verify: reports.filter((r) => r.status === "CLEANUP_VERIFICATION" && !mine(r)),
    review: reports.filter((r) => ["NEW", "AI_DETECTED", "STAFF_REVIEW"].includes(r.status)),
    critical: reports.filter((r) => open(r) && (r.priority === "CRITICAL" || r.severity === "CRITICAL")),
    high: reports.filter((r) => open(r) && r.priority === "HIGH"),
    nearby: pos ? reports.filter(open).map((r) => ({ ...r, dist: km(pos, { lat: r.latitude, lng: r.longitude }) })).filter((r) => r.dist <= radius).sort((a, b) => a.dist - b.dist) : [],
  }), [reports, pos, radius]);  // eslint-disable-line react-hooks/exhaustive-deps

  const stat = (v, l) => (<div className="stat-card"><div className="value">{v ?? "-"}</div><div className="label">{l}</div></div>);

  return (
    <Layout title={`Staff dashboard — ${user.name}`}>
      <div className="stat-grid" style={{ marginBottom: 16 }}>
        {stat(groups.tasks.length, "My cleanup tasks")}
        {stat(groups.verify.length, "Awaiting my verification")}
        {stat(groups.review.length, "To review")}
        {stat(cards?.critical_reports, "Critical")}
        {stat(cards?.high_priority, "High priority")}
        {stat(cards?.active_hotspots, "Active hotspots")}
      </div>

      <Section title="My cleanup tasks" hint="Assigned to you. Open a task to start cleanup, add the before/after photos and complete it." rows={groups.tasks} empty="Nothing assigned to you right now." />
      <Section title="Verification requests" hint="Cleanups finished by colleagues. Check the before/after evidence, then approve or send back. You cannot verify your own work." rows={groups.verify} empty="No cleanups waiting for you to verify." />
      <Section title="Review queue" hint="New reports waiting for a person to confirm or correct the AI classification." rows={groups.review} empty="The review queue is empty." />
      <Section title="Critical reports" rows={groups.critical} empty="No critical reports." />
      <Section title="High-priority reports" rows={groups.high} empty="No high-priority reports." />

      <div className="card">
        <h2>Nearby reports</h2>
        <div className="filters">
          <button onClick={locate}>{pos ? "Update my location" : "Use my location"}</button>
          <select aria-label="Radius" value={radius} onChange={(e) => setRadius(Number(e.target.value))}>
            {[1, 2, 5, 10, 25].map((k) => <option key={k} value={k}>within {k} km</option>)}
          </select>
          {geoMsg && <span role="alert" style={{ color: "var(--rust)" }}>{geoMsg}</span>}
        </div>
        {!pos ? <p className="muted">Share your location to see open reports around you. It is used only in this browser to sort by distance.</p>
          : groups.nearby.length === 0 ? <p className="muted">No open reports within {radius} km.</p>
          : <Section title="Closest first" rows={groups.nearby} empty="" />}
      </div>
    </Layout>
  );
}
