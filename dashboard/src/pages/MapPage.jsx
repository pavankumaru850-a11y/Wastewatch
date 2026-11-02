import { useEffect, useMemo, useState } from "react";
import { MapContainer, TileLayer, CircleMarker, Popup } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import Layout from "../components/Layout";
import ClusterLayer, { esc } from "../components/ClusterLayer";
import { SEV_COLOR, rid, resultLabel } from "../components/ui";
import { hotspotsApi, reportsApi } from "../services/resources";

const LAYERS = [
  ["all", "All reports", () => true],
  ["assigned", "Assigned tasks", (r) => ["ASSIGNED", "IN_PROGRESS"].includes(r.status)],
  ["critical", "Critical locations", (r) => (r.severity === "CRITICAL" || r.priority === "CRITICAL") && !["CLOSED", "COMPLETED", "REJECTED"].includes(r.status)],
  ["completed", "Completed cleanups", (r) => ["CLEANED", "CLEANUP_VERIFICATION", "CLOSED", "COMPLETED"].includes(r.status)],
];

function popup(r) {
  return `<strong>${esc(rid(r.id))}</strong><br/>AI result: ${esc(resultLabel(r))}<br/>` +
    `Severity: ${esc(r.severity)}<br/>Priority: ${esc(r.priority)}${r.priority_score != null ? ` (${Math.round(r.priority_score)})` : ""}<br/>` +
    `Status: ${esc(String(r.status).replaceAll("_", " "))}<br/>Date: ${esc(new Date(r.created_at).toLocaleDateString())}<br/>` +
    `<a href="/reports/${Number(r.id)}">Open report</a>`;
}

export default function MapPage() {
  const [reports, setReports] = useState([]);
  const [hotspots, setHotspots] = useState([]);
  const [active, setActive] = useState({ all: true });
  const [showHotspots, setShowHotspots] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    reportsApi.list({}).then((r) => setReports(r.data)).catch(() => setError("Could not load reports."));
    hotspotsApi.list().then((r) => setHotspots(r.data)).catch(() => {});
  }, []);

  const items = useMemo(() => {
    const on = LAYERS.filter(([k]) => active[k]);
    return reports
      .filter((r) => on.some(([, , f]) => f(r)))
      .map((r) => ({ id: r.id, lat: r.latitude, lng: r.longitude, color: SEV_COLOR[r.severity] || "#6b7280", popupHtml: popup(r) }));
  }, [reports, active]);

  const first = items[0] || hotspots[0];
  const center = first ? [first.lat ?? first.latitude, first.lng ?? first.longitude] : [20.5937, 78.9629];

  return (
    <Layout title="Map">
      {error && <div className="card" role="alert" style={{ marginBottom: 12 }}>{error}</div>}
      <div className="card" style={{ marginBottom: 12, display: "flex", gap: 18, flexWrap: "wrap", alignItems: "center" }}>
        <strong>Layers:</strong>
        {LAYERS.map(([k, label]) => (
          <label key={k}><input type="checkbox" checked={!!active[k]} onChange={(e) => setActive({ ...active, [k]: e.target.checked })} /> {label}</label>
        ))}
        <label><input type="checkbox" checked={showHotspots} onChange={(e) => setShowHotspots(e.target.checked)} /> Hotspots</label>
        <span className="muted">
          {Object.entries(SEV_COLOR).map(([k, c]) => <span key={k} style={{ marginRight: 10 }}><span style={{ display: "inline-block", width: 10, height: 10, borderRadius: 5, background: c, marginRight: 3 }} />{k}</span>)}
        </span>
      </div>
      <div className="card" style={{ padding: 0, overflow: "hidden" }}>
        <MapContainer center={center} zoom={items.length || hotspots.length ? 12 : 5} style={{ height: "70vh", width: "100%" }} key={`${items.length}-${hotspots.length}`}>
          <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution="&copy; OpenStreetMap contributors" />
          <ClusterLayer items={items} />
          {showHotspots && hotspots.map((h) => (
            <CircleMarker key={h.id} center={[h.latitude, h.longitude]} radius={Math.min(16 + h.total_reports * 2, 40)}
              pathOptions={{ color: SEV_COLOR[h.severity], fillColor: SEV_COLOR[h.severity], fillOpacity: 0.18, weight: 3, dashArray: "6 4" }}>
              <Popup><strong>Hotspot #{h.id}</strong><br />{h.total_reports} reports &middot; {h.severity}<br />Priority {Math.round(h.priority_score)}/100<br />Status: {h.current_status}</Popup>
            </CircleMarker>
          ))}
        </MapContainer>
      </div>
      <p className="muted" style={{ marginTop: 8 }}>{items.length} report(s) shown from stored GPS coordinates (latest 500). Zoom in to split clusters.</p>
    </Layout>
  );
}
