import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import Layout from "../components/Layout";
import { errText, rid } from "../components/ui";
import { duplicatesApi } from "../services/resources";

export default function Duplicates() {
  const [rows, setRows] = useState([]);
  const [filter, setFilter] = useState("PENDING");
  const [msg, setMsg] = useState("");

  const load = () => duplicatesApi.list(filter).then((r) => setRows(r.data)).catch((e) => setMsg(errText(e)));
  useEffect(() => { load(); }, [filter]);

  async function decide(id, decision) {
    try { await duplicatesApi.decide(id, decision); setMsg(`Marked ${decision.replace("_", " ").toLowerCase()}.`); load(); }
    catch (e) { setMsg(errText(e)); }
  }

  return (
    <Layout title="Duplicate Review">
      {msg && <div className="card" role="status" style={{ marginBottom: 12 }}>{msg}</div>}
      <div className="filters">
        <select aria-label="Decision" value={filter} onChange={(e) => setFilter(e.target.value)}>
          {["PENDING", "CONFIRMED", "NOT_DUPLICATE", "MERGED", ""].map((d) => <option key={d} value={d}>{d ? d.replace("_", " ") : "All"}</option>)}
        </select>
      </div>
      <div className="card">
        <p className="muted">Reports are only flagged, never deleted. Merge closes the newer report as a duplicate of the older one; the evidence is kept.</p>
        <table>
          <thead><tr><th>Report</th><th>Similar to</th><th>Distance</th><th>Time apart</th><th>Image distance</th><th>Category</th><th>Decision</th><th></th></tr></thead>
          <tbody>
            {rows.map((d) => (
              <tr key={d.id}>
                <td><Link to={`/reports/${d.report_id}`}>{rid(d.report_id)}</Link></td>
                <td><Link to={`/reports/${d.candidate_id}`}>{rid(d.candidate_id)}</Link></td>
                <td>{d.distance_m} m</td><td>{d.time_diff_minutes} min</td>
                <td>{d.hash_distance ?? "n/a"} <span className="muted">(0 = identical)</span></td>
                <td>{d.same_category ? "Same" : "Different"}</td><td>{d.decision}</td>
                <td style={{ whiteSpace: "nowrap" }}>
                  {d.decision === "PENDING" && (<>
                    <button onClick={() => decide(d.id, "CONFIRMED")}>Confirm</button>{" "}
                    <button className="secondary" onClick={() => decide(d.id, "NOT_DUPLICATE")}>Not duplicate</button>{" "}
                    <button className="danger" onClick={() => window.confirm("Merge and close the newer report?") && decide(d.id, "MERGED")}>Merge</button>
                  </>)}
                </td>
              </tr>
            ))}
            {rows.length === 0 && <tr><td colSpan={8} className="muted">Nothing to review.</td></tr>}
          </tbody>
        </table>
      </div>
    </Layout>
  );
}
