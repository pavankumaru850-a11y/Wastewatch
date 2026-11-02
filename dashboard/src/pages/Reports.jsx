import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import Layout from "../components/Layout";
import StatusBadge from "../components/StatusBadge";
import { adminApi, reportsApi } from "../services/resources";
import { API_URL } from "../services/api";
import { useAuth } from "../context/AuthContext";
import { download, errText, resultLabel } from "../components/ui";

const STATUSES = ["NEW", "AI_DETECTED", "STAFF_REVIEW", "VERIFIED", "ASSIGNED", "IN_PROGRESS", "CLEANED", "CLEANUP_VERIFICATION", "CLOSED", "COMPLETED", "REJECTED"];

const PRIORITIES = ["LOW", "MEDIUM", "HIGH", "CRITICAL"];

/** Non-empty filters -> API params. A picked end date means "through the end of that day". */
function buildParams(filters, only) {
  const p = Object.fromEntries(Object.entries(filters).filter(([k, v]) => v && (!only || only.includes(k))));
  if (p.date_from) p.date_from = `${p.date_from}T00:00:00`;
  if (p.date_to) p.date_to = `${p.date_to}T23:59:59`;
  return p;
}

export default function Reports() {
  const { user } = useAuth();
  const [reports, setReports] = useState([]);
  const [filters, setFilters] = useState({ status: "", priority: "", severity: "", village: "", search: "", duplicate: "", min_confidence: "", date_from: "", date_to: "", hotspot_id: "", district: "", assigned_to: "" });
  const [staffList, setStaffList] = useState([]);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    const res = await reportsApi.list(buildParams(filters));
    setReports(res.data);
    setLoading(false);
  }

  useEffect(() => { load(); }, [filters]);
  useEffect(() => { if (user?.role === "ADMIN") adminApi.listUsers("STAFF").then((r) => setStaffList(r.data)).catch(() => {}); }, [user]);

  async function exportFile(kind) {
    try {
      const res = await reportsApi.exportFile(kind, buildParams(filters, ["status", "priority", "severity", "date_from", "date_to"]));
      download(res.data, `wastewatch_reports_${new Date().toISOString().slice(0, 10)}.${kind}`);
    } catch (e) { window.alert(errText(e)); }
  }

  async function downloadPdf() {
    const res = await reportsApi.exportPdf(buildParams(filters));
    const url = window.URL.createObjectURL(new Blob([res.data], { type: "application/pdf" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = `wastewatch_report_${new Date().toISOString().slice(0, 10)}.pdf`;
    a.click();
    window.URL.revokeObjectURL(url);
  }

  return (
    <Layout title={user?.role === "ADMIN" ? "Reports" : "Assigned Reports"}>
      <div className="filters">
        <select value={filters.status} onChange={(e) => setFilters({ ...filters, status: e.target.value })}>
          <option value="">All statuses</option>
          {STATUSES.map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}
        </select>
        <select value={filters.priority} onChange={(e) => setFilters({ ...filters, priority: e.target.value })}>
          <option value="">All priorities</option>
          {PRIORITIES.map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
        <input
          placeholder="Village" value={filters.village}
          onChange={(e) => setFilters({ ...filters, village: e.target.value })}
        />
        <select aria-label="Severity" value={filters.severity} onChange={(e) => setFilters({ ...filters, severity: e.target.value })}>
          <option value="">All severities</option>
          {PRIORITIES.map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
        <input aria-label="Search" placeholder="Search text" value={filters.search} onChange={(e) => setFilters({ ...filters, search: e.target.value })} />
        <select aria-label="Duplicates" value={filters.duplicate} onChange={(e) => setFilters({ ...filters, duplicate: e.target.value })}>
          <option value="">Duplicates: any</option><option value="true">Possible duplicates</option><option value="false">Not duplicates</option>
        </select>
        <select aria-label="Confidence" value={filters.min_confidence} onChange={(e) => setFilters({ ...filters, min_confidence: e.target.value })}>
          <option value="">Any confidence</option><option value="0.5">&ge; 50%</option><option value="0.75">&ge; 75%</option>
        </select>
        <label className="muted" style={{ display: "flex", alignItems: "center", gap: 4 }}>From
          <input type="date" aria-label="From date" value={filters.date_from} onChange={(e) => setFilters({ ...filters, date_from: e.target.value })} /></label>
        <label className="muted" style={{ display: "flex", alignItems: "center", gap: 4 }}>To
          <input type="date" aria-label="To date" value={filters.date_to} onChange={(e) => setFilters({ ...filters, date_to: e.target.value })} /></label>
        <input aria-label="District" placeholder="District" value={filters.district} onChange={(e) => setFilters({ ...filters, district: e.target.value })} />
        <input aria-label="Hotspot ID" type="number" min="1" placeholder="Hotspot #" value={filters.hotspot_id} onChange={(e) => setFilters({ ...filters, hotspot_id: e.target.value })} style={{ width: 110 }} />
        {user?.role === "ADMIN" && (
          <select aria-label="Assigned staff" value={filters.assigned_to} onChange={(e) => setFilters({ ...filters, assigned_to: e.target.value })}>
            <option value="">Any staff</option>
            {staffList.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
          </select>
        )}
        <button className="secondary" onClick={() => setFilters({ status: "", priority: "", severity: "", village: "", search: "", duplicate: "", min_confidence: "", date_from: "", date_to: "", hotspot_id: "", district: "", assigned_to: "" })}>Clear filters</button>
        <button className="secondary" onClick={downloadPdf}>Export PDF</button>
        {user?.role === "ADMIN" && (<>
          <button className="secondary" onClick={() => exportFile("csv")}>Export CSV</button>
          <button className="secondary" onClick={() => exportFile("xlsx")}>Export Excel</button>
        </>)}
      </div>

      <div className="card">
        <table>
          <thead>
            <tr>
              <th>Image</th><th>Report ID</th><th>AI Result</th><th>Confidence</th>
              <th>Village</th><th>District</th><th>Date</th><th>Sev. score</th>
              <th>Deadline</th><th>Priority</th><th>Status</th><th></th>
            </tr>
          </thead>
          <tbody>
            {reports.map((r) => (
              <tr key={r.id}>
                <td><img className="badge-thumb" src={`${API_URL}/${r.image_path}`} alt="" /></td>
                <td>
                  WW-{String(r.id).padStart(6, "0")}
                  {r.is_possible_duplicate && (
                    <span title={`Possible duplicate of WW-${String(r.duplicate_of_id).padStart(6, "0")}`} style={{ marginLeft: 6, color: "#b8792e", fontSize: 11 }}>
                      ⚠ dup
                    </span>
                  )}
                </td>
                <td>{resultLabel(r)}</td>
                <td>{r.confidence ? `${Math.round(r.confidence * 100)}%` : "-"}</td>
                <td>{r.village || "-"}</td>
                <td>{r.district || "-"}</td>
                <td>{new Date(r.created_at).toLocaleDateString()}</td>
                <td>{r.severity_score ?? "-"}</td>
                <td>{r.deadline ? new Date(r.deadline).toLocaleDateString() : "-"}</td>
                <td>{r.severity ? `${r.severity} / ` : ""}{r.priority}{r.priority_score != null ? ` (${Math.round(r.priority_score)})` : ""}</td>
                <td><StatusBadge status={r.status} /></td>
                <td><Link to={`/reports/${r.id}`}>View</Link></td>
              </tr>
            ))}
            {!loading && reports.length === 0 && (
              <tr><td colSpan={12} className="muted">No reports match these filters.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </Layout>
  );
}
