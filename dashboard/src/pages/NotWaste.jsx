import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import Layout from "../components/Layout";
import { reportsApi } from "../services/resources";
import { API_URL } from "../services/api";
import { errText, rid } from "../components/ui";

/** Photos the AI judged "not waste". Stored here, separate from the waste reports:
 *  no notification, no hotspot, not counted in the dashboard or map. An admin can correct a wrong decision. */
export default function NotWaste() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState({ text: "", error: false });

  async function load() {
    setLoading(true);
    try {
      const res = await reportsApi.list({ is_waste: false });
      setRows(res.data);
    } catch (e) {
      setMsg({ text: errText(e), error: true });
    }
    setLoading(false);
  }
  useEffect(() => { load(); }, []);

  async function markWaste(id) {
    try {
      await reportsApi.reclassify(id, true, "Admin: this is waste");
      setMsg({ text: `${rid(id)} moved to the waste reports.`, error: false });
      load();
    } catch (e) {
      setMsg({ text: errText(e), error: true });
    }
  }

  return (
    <Layout title="Not Waste">
      <p className="muted" style={{ marginTop: 0 }}>
        Photos the AI decided are <strong>not waste</strong>. They are kept here with their photo, location and time, but they
        do not create alerts, hotspots or cleanup tasks and are not counted as waste.
      </p>
      {msg.text && (
        <div className="card" role="status" style={{ marginBottom: 16, background: msg.error ? "#fbeceb" : "#eef6f0", borderColor: msg.error ? "var(--rust)" : "var(--brand)" }}>
          {msg.text}
        </div>
      )}
      <div className="card">
        <table>
          <thead>
            <tr><th>Image</th><th>ID</th><th>AI confidence</th><th>Village</th><th>District</th><th>Location</th><th>Date</th><th></th><th></th></tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td><img className="badge-thumb" src={`${API_URL}/${r.image_path}`} alt="" /></td>
                <td>{rid(r.id)}</td>
                <td>{r.confidence != null ? `${Math.round(r.confidence * 100)}% not waste` : "-"}</td>
                <td>{r.village || "-"}</td>
                <td>{r.district || "-"}</td>
                <td className="muted" style={{ fontFamily: "var(--font-mono)" }}>{r.latitude.toFixed(4)}, {r.longitude.toFixed(4)}</td>
                <td>{new Date(r.created_at).toLocaleString()}</td>
                <td><Link to={`/reports/${r.id}`}>View</Link></td>
                <td><button className="secondary" onClick={() => markWaste(r.id)}>It is waste</button></td>
              </tr>
            ))}
            {!loading && rows.length === 0 && <tr><td colSpan={9} className="muted">No not-waste photos yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </Layout>
  );
}
