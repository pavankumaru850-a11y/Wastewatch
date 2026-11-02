import { useEffect, useState } from "react";
import { MapContainer, TileLayer, CircleMarker, Popup } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import Layout from "../components/Layout";
import { SeverityBadge, SEV_COLOR, rid } from "../components/ui";
import { dashboardApi, hotspotsApi } from "../services/resources";

export default function Hotspots() {
  const [hotspots, setHotspots] = useState([]);
  const [selected, setSelected] = useState(null);
  const [timeline, setTimeline] = useState([]);
  const [cleanliness, setCleanliness] = useState([]);
  const [by, setBy] = useState("village");

  useEffect(() => { hotspotsApi.list().then((r) => setHotspots(r.data)); }, []);
  useEffect(() => { dashboardApi.cleanlinessScore(by).then((r) => setCleanliness(r.data)); }, [by]);
  useEffect(() => {
    if (!selected) return;
    hotspotsApi.history(selected.id).then((r) => setTimeline(r.data.timeline));
  }, [selected]);

  const center = hotspots.length ? [hotspots[0].latitude, hotspots[0].longitude] : [20.5937, 78.9629];

  return (
    <Layout title="Hotspots">
      <div className="card" style={{ marginBottom: 12 }}>
        <span style={{ marginRight: 16 }}>Legend:</span>
        {Object.entries(SEV_COLOR).map(([k, c]) => (
          <span key={k} style={{ marginRight: 14 }}><span style={{ display: "inline-block", width: 12, height: 12, borderRadius: 6, background: c, marginRight: 4 }} />{k}</span>
        ))}
      </div>
      <div className="card" style={{ marginBottom: 16, padding: 0, overflow: "hidden" }}>
        <MapContainer center={center} zoom={hotspots.length ? 13 : 5} style={{ height: "50vh", width: "100%" }} key={hotspots.length}>
          <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution="&copy; OpenStreetMap contributors" />
          {hotspots.map((h) => (
            <CircleMarker key={h.id} center={[h.latitude, h.longitude]} radius={Math.min(10 + h.total_reports * 2, 34)}
              pathOptions={{ color: SEV_COLOR[h.severity], fillColor: SEV_COLOR[h.severity], fillOpacity: 0.55 }}
              eventHandlers={{ click: () => setSelected(h) }}>
              <Popup>
                <strong>Hotspot #{h.id}</strong><br />{h.total_reports} reports &middot; {h.severity}<br />
                Priority {Math.round(h.priority_score)}/100<br />{h.dominant_waste_type || "Mixed"}<br />Status: {h.current_status}
              </Popup>
            </CircleMarker>
          ))}
        </MapContainer>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <h2>Active and past hotspots</h2>
        <p className="muted">A hotspot forms when repeated reports occur within the configured radius (Settings &rarr; System). Click a row for its history.</p>
        <table>
          <thead><tr><th>ID</th><th>Reports</th><th>Dominant type</th><th>Severity</th><th>Priority</th><th>Cleanups</th><th>Last report</th><th>Status</th></tr></thead>
          <tbody>
            {hotspots.map((h) => (
              <tr key={h.id} onClick={() => setSelected(h)} style={{ cursor: "pointer", background: selected?.id === h.id ? "#eef6f0" : undefined }}>
                <td>#{h.id}</td><td>{h.total_reports}</td><td>{h.dominant_waste_type || "-"}</td>
                <td><SeverityBadge level={h.severity} /></td><td>{Math.round(h.priority_score)}</td>
                <td>{h.cleanup_count}</td><td>{h.last_report_at ? new Date(h.last_report_at).toLocaleDateString() : "-"}</td><td>{h.current_status}</td>
              </tr>
            ))}
            {hotspots.length === 0 && <tr><td colSpan={8} className="muted">No hotspots yet.</td></tr>}
          </tbody>
        </table>
      </div>

      {selected && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h2>Hotspot #{selected.id} history</h2>
          <p className="muted">First report {selected.first_report_at ? new Date(selected.first_report_at).toLocaleString() : "-"} &middot; {selected.total_reports} total &middot; {selected.cleanup_count} cleaned</p>
          {timeline.map((e, i) => (
            <div key={i} style={{ padding: "6px 0 6px 12px", borderLeft: `3px solid ${e.type === "REPORT" ? "var(--brand)" : "#9aa5b1"}`, marginBottom: 4 }}>
              <strong>{e.type === "REPORT" ? "New report" : "Status"}</strong> {rid(e.report_id)} &mdash; {e.detail}
              <span className="muted"> &middot; {new Date(e.at).toLocaleString()}</span>
            </div>
          ))}
        </div>
      )}

      <div className="card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2>Area cleanliness score</h2>
          <select aria-label="Group by" value={by} onChange={(e) => setBy(e.target.value)}>
            <option value="village">By village</option><option value="district">By district</option>
          </select>
        </div>
        <p className="muted">Share of non-rejected reports in the area that have been fully completed.</p>
        <table>
          <thead><tr><th>{by === "village" ? "Village" : "District"}</th><th>Score</th><th>Completed</th><th>Total</th></tr></thead>
          <tbody>
            {cleanliness.map((c) => (<tr key={c.area}><td>{c.area}</td><td>{c.score != null ? `${c.score}%` : "-"}</td><td>{c.completed}</td><td>{c.total_reports}</td></tr>))}
            {cleanliness.length === 0 && <tr><td colSpan={4} className="muted">No data yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </Layout>
  );
}
