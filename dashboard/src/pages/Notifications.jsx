import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import Layout from "../components/Layout";
import { notificationsApi } from "../services/resources";

export default function Notifications() {
  const [items, setItems] = useState([]);
  const load = () => notificationsApi.list().then((r) => setItems(r.data));
  useEffect(() => { load(); }, []);
  return (
    <Layout title="Notifications" actions={<button className="secondary" onClick={() => notificationsApi.readAll().then(load)}>Mark all read</button>}>
      <div className="card">
        {items.map((n) => (
          <div key={n.id} style={{ padding: "10px 0", borderBottom: "1px solid var(--line)", opacity: n.is_read ? 0.6 : 1 }}>
            <strong>{n.title}</strong> {!n.is_read && <span className="badge" style={{ background: "var(--brand)" }}>new</span>}
            <div className="muted">{n.body} {n.report_id && <Link to={`/reports/${n.report_id}`} onClick={() => notificationsApi.read(n.id)}>Open report</Link>} &middot; {new Date(n.created_at).toLocaleString()}</div>
          </div>
        ))}
        {items.length === 0 && <p className="muted">No notifications.</p>}
      </div>
    </Layout>
  );
}
