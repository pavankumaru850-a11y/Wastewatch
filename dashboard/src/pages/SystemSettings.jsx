import { useEffect, useState } from "react";
import Layout from "../components/Layout";
import { errText } from "../components/ui";
import { adminApi } from "../services/resources";

const LABELS = {
  detection_confidence: ["Minimum detection confidence (0-1)", "number"],
  duplicate_distance_m: ["Duplicate distance (metres)", "number"],
  duplicate_close_distance_m: ["Same-category duplicate distance when photos differ (metres)", "number"],
  duplicate_time_window_hours: ["Duplicate time window (hours)", "number"],
  duplicate_hash_max_distance: ["Max image-hash distance for 'similar' (0-64)", "number"],
  max_reports_per_hour: ["Max reports per citizen per hour", "number"],
  hotspot_radius_m: ["Hotspot radius (metres)", "number"],
  hotspot_min_reports: ["Reports needed to form a hotspot", "number"],
  max_image_mb: ["Max image size (MB)", "number"],
  min_image_side_px: ["Min image side (px)", "number"],
  blur_threshold: ["Blur threshold (lower = stricter reject)", "number"],
  dark_mean_max: ["Too-dark brightness limit", "number"],
  bright_mean_min: ["Too-bright brightness limit", "number"],
  model_version: ["Model version label", "text"],
};

export default function SystemSettings() {
  const [vals, setVals] = useState(null);
  const [scoring, setScoring] = useState("");
  const [models, setModels] = useState([]);
  const [msg, setMsg] = useState({ text: "", error: false });
  const say = (text, error = false) => setMsg({ text, error });

  const load = () => {
    adminApi.settings().then((r) => { setVals(r.data.settings); setScoring(JSON.stringify(r.data.scoring, null, 2)); }).catch((e) => say(errText(e), true));
    adminApi.models().then((r) => setModels(r.data)).catch(() => {});
  };
  useEffect(load, []);

  async function save() {
    const body = {};
    for (const k of Object.keys(LABELS)) body[k] = LABELS[k][1] === "number" ? Number(vals[k]) : vals[k];
    try { await adminApi.saveSettings(body); say("Settings saved."); } catch (e) { say(errText(e), true); }
  }
  async function saveScoring() {
    try { await adminApi.saveScoring(JSON.parse(scoring)); say("Scoring rules saved."); }
    catch (e) { say(e instanceof SyntaxError ? "That is not valid JSON." : errText(e), true); }
  }
  async function activate(v) {
    try { await adminApi.activateModel(v); say(`Model ${v} activated.`); load(); } catch (e) { say(errText(e), true); }
  }

  if (!vals) return <Layout title="System"><p>{msg.text || "Loading..."}</p></Layout>;

  return (
    <Layout title="System Settings & AI Models">
      {msg.text && <div className="card" role="status" style={{ marginBottom: 16, background: msg.error ? "#fbeceb" : "#eef6f0" }}>{msg.text}</div>}

      <div className="card" style={{ marginBottom: 16 }}>
        <h2>AI models</h2>
        <table>
          <thead><tr><th>Model</th><th>Version</th><th>Trained</th><th>Dataset</th><th>mAP50</th><th>Precision</th><th>Recall</th><th>Status</th><th></th></tr></thead>
          <tbody>
            {models.map((m) => (
              <tr key={m.version}>
                <td>{m.model_name || "wastewatch"}</td><td>{m.version}</td><td>{m.trained_at ? new Date(m.trained_at).toLocaleDateString() : "-"}</td>
                <td>{m.dataset_version || "-"}</td>
                <td>{m.map50 ?? "-"}</td><td>{m.precision ?? "-"}</td><td>{m.recall ?? "-"}</td>
                <td>{m.active ? "ACTIVE" : "inactive"}</td>
                <td>{!m.active && <button onClick={() => activate(m.version)}>Activate</button>}</td>
              </tr>
            ))}
            {models.length === 0 && <tr><td colSpan={9} className="muted">No trained models registered yet. Train one first (see docs) &mdash; metrics are only shown once a model has actually been evaluated.</td></tr>}
          </tbody>
        </table>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <h2>Detection, duplicate and hotspot settings</h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(260px,1fr))", gap: 12 }}>
          {Object.entries(LABELS).map(([k, [label, type]]) => (
            <div className="field" key={k}>
              <label htmlFor={k}>{label}</label>
              <input id={k} type={type} step="any" min="0" value={vals[k] ?? ""} onChange={(e) => setVals({ ...vals, [k]: e.target.value })} style={{ width: "100%" }} />
            </div>
          ))}
        </div>
        <button onClick={save}>Save settings</button>
      </div>

      <div className="card">
        <h2>Severity &amp; priority scoring rules</h2>
        <p className="muted">Every point value and threshold used by the severity engine, priority score and confidence levels. Changes apply to new reports only and are written to the audit log.</p>
        <textarea aria-label="Scoring JSON" rows={18} value={scoring} onChange={(e) => setScoring(e.target.value)} style={{ width: "100%", fontFamily: "var(--font-mono)", fontSize: 12 }} />
        <button onClick={saveScoring} style={{ marginTop: 8 }}>Save scoring rules</button>
      </div>
    </Layout>
  );
}
