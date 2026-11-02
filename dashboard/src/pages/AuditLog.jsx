import { useEffect, useState } from "react";
import Layout from "../components/Layout";
import { adminApi } from "../services/resources";

export default function AuditLog() {
  const [logs, setLogs] = useState([]);

  useEffect(() => {
    adminApi.auditLog().then((r) => setLogs(r.data));
  }, []);

  return (
    <Layout title="Audit Log">
      <div className="card">
        <p className="muted">
          Every assignment, status change, verification, and completion is recorded here.
          Rows are never edited or deleted.
        </p>
        <table>
          <thead><tr><th>When</th><th>User</th><th>Action</th><th>Report</th><th>Details</th><th>Old</th><th>New</th><th>IP</th></tr></thead>
          <tbody>
            {logs.map((l) => (
              <tr key={l.id}>
                <td>{new Date(l.created_at).toLocaleString()}</td>
                <td>#{l.user_id}</td>
                <td>{l.action}</td>
                <td>{l.report_id ? `WW-${String(l.report_id).padStart(6, "0")}` : "-"}</td>
                <td>{l.details || "-"}</td><td>{l.old_value || "-"}</td><td>{l.new_value || "-"}</td><td>{l.ip_address || "-"}</td>
              </tr>
            ))}
            {logs.length === 0 && <tr><td colSpan={8} className="muted">No activity recorded yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </Layout>
  );
}
