import { useEffect, useState } from "react";
import Layout from "../components/Layout";
import { errText } from "../components/ui";
import { adminApi } from "../services/resources";
import { useAuth } from "../context/AuthContext";

const EMPTY = { name: "", email: "", password: "", role: "STAFF", phone: "", village: "", district: "" };

export default function Users() {
  const { user: me } = useAuth();
  const [users, setUsers] = useState([]);
  const [roleFilter, setRoleFilter] = useState("");
  const [form, setForm] = useState(EMPTY);
  const [msg, setMsg] = useState({ text: "", error: false });
  const say = (text, error = false) => setMsg({ text, error });

  const load = () => adminApi.listUsers(roleFilter || undefined).then((r) => setUsers(r.data));
  useEffect(() => { load(); }, [roleFilter]);

  async function create(e) {
    e.preventDefault();
    try {
      const body = Object.fromEntries(Object.entries(form).filter(([, v]) => v !== ""));
      await adminApi.createUser(body);
      say(`Account created for ${form.email}. Share the password with them securely; they can change it after signing in.`);
      setForm(EMPTY);
      load();
    } catch (err) { say(errText(err), true); }
  }

  async function update(id, data, okText) {
    try { await adminApi.updateUser(id, data); say(okText); load(); } catch (err) { say(errText(err), true); }
  }

  return (
    <Layout title="Users & Staff">
      {msg.text && <div className="card" role="status" style={{ marginBottom: 16, background: msg.error ? "#fbeceb" : "#eef6f0" }}>{msg.text}</div>}

      <div className="card" style={{ marginBottom: 16 }}>
        <h2>Create staff or admin account</h2>
        <form onSubmit={create} style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: 12 }}>
          <div className="field"><label htmlFor="un">Full name</label><input id="un" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} style={{ width: "100%" }} /></div>
          <div className="field"><label htmlFor="ue">Email</label><input id="ue" type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} style={{ width: "100%" }} /></div>
          <div className="field"><label htmlFor="up">Temporary password (min 8)</label><input id="up" type="password" required minLength={8} autoComplete="new-password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} style={{ width: "100%" }} /></div>
          <div className="field"><label htmlFor="ur">Role</label>
            <select id="ur" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })} style={{ width: "100%" }}><option value="STAFF">Staff</option><option value="ADMIN">Admin</option></select></div>
          <div className="field"><label htmlFor="uph">Phone</label><input id="uph" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} style={{ width: "100%" }} /></div>
          <div className="field"><label htmlFor="uv">Village / ward</label><input id="uv" value={form.village} onChange={(e) => setForm({ ...form, village: e.target.value })} style={{ width: "100%" }} /></div>
          <div className="field"><label htmlFor="ud">District</label><input id="ud" value={form.district} onChange={(e) => setForm({ ...form, district: e.target.value })} style={{ width: "100%" }} /></div>
          <div style={{ alignSelf: "end" }}><button type="submit">Create account</button></div>
        </form>
      </div>

      <div className="filters">
        <select aria-label="Role filter" value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)}>
          <option value="">All roles</option><option value="ADMIN">Admin</option><option value="STAFF">Staff</option><option value="CITIZEN">Citizen</option>
        </select>
      </div>
      <div className="card">
        <table>
          <thead><tr><th>Name</th><th>Email</th><th>Phone</th><th>Role</th><th>Village</th><th>District</th><th>Joined</th><th>Active</th></tr></thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id}>
                <td>{u.name}</td><td>{u.email}</td><td>{u.phone || "-"}</td>
                <td>
                  <select aria-label={`Role of ${u.name}`} value={u.role} disabled={u.id === me?.id}
                    onChange={(e) => window.confirm(`Change ${u.name} to ${e.target.value}?`) && update(u.id, { role: e.target.value }, "Role updated.")}>
                    <option value="CITIZEN">Citizen</option><option value="STAFF">Staff</option><option value="ADMIN">Admin</option>
                  </select>
                </td>
                <td>{u.village || "-"}</td><td>{u.district || "-"}</td><td>{new Date(u.created_at).toLocaleDateString()}</td>
                <td>
                  <button className={u.is_active ? "secondary" : ""} disabled={u.id === me?.id}
                    onClick={() => update(u.id, { is_active: !u.is_active }, u.is_active ? "Account deactivated." : "Account reactivated.")}>
                    {u.is_active ? "Active - deactivate" : "Inactive - activate"}
                  </button>
                </td>
              </tr>
            ))}
            {users.length === 0 && <tr><td colSpan={8} className="muted">No users found.</td></tr>}
          </tbody>
        </table>
      </div>
    </Layout>
  );
}
