import { useState } from "react";
import Layout from "../components/Layout";
import { profileApi } from "../services/resources";
import { useAuth } from "../context/AuthContext";

export default function Settings() {
  const { user } = useAuth();
  const [profile, setProfile] = useState({
    name: user?.name || "", phone: user?.phone || "",
    village: user?.village || "", district: user?.district || "",
  });
  const [pw, setPw] = useState({ current_password: "", new_password: "" });
  const [profileMsg, setProfileMsg] = useState("");
  const [pwMsg, setPwMsg] = useState("");

  async function saveProfile(e) {
    e.preventDefault();
    setProfileMsg("");
    try {
      await profileApi.update(profile);
      setProfileMsg("Profile updated.");
    } catch (err) {
      setProfileMsg(err.response?.data?.detail || "Could not update profile.");
    }
  }

  async function savePassword(e) {
    e.preventDefault();
    setPwMsg("");
    try {
      await profileApi.changePassword(pw);
      setPwMsg("Password updated.");
      setPw({ current_password: "", new_password: "" });
    } catch (err) {
      setPwMsg(err.response?.data?.detail || "Could not change password.");
    }
  }

  return (
    <Layout title="Settings">
      <div className="grid-2">
        <div className="card">
          <h2>Profile</h2>
          <form onSubmit={saveProfile}>
            <div className="field">
              <label>Name</label>
              <input style={{ width: "100%" }} value={profile.name} onChange={(e) => setProfile({ ...profile, name: e.target.value })} />
            </div>
            <div className="field">
              <label>Phone</label>
              <input style={{ width: "100%" }} value={profile.phone} onChange={(e) => setProfile({ ...profile, phone: e.target.value })} />
            </div>
            <div className="field">
              <label>Village</label>
              <input style={{ width: "100%" }} value={profile.village} onChange={(e) => setProfile({ ...profile, village: e.target.value })} />
            </div>
            <div className="field">
              <label>District</label>
              <input style={{ width: "100%" }} value={profile.district} onChange={(e) => setProfile({ ...profile, district: e.target.value })} />
            </div>
            {profileMsg && <p className="muted">{profileMsg}</p>}
            <button type="submit">Save profile</button>
          </form>
        </div>

        <div className="card">
          <h2>Change password</h2>
          <form onSubmit={savePassword}>
            <div className="field">
              <label>Current password</label>
              <input type="password" style={{ width: "100%" }} value={pw.current_password} onChange={(e) => setPw({ ...pw, current_password: e.target.value })} required />
            </div>
            <div className="field">
              <label>New password (min 6 characters)</label>
              <input type="password" style={{ width: "100%" }} value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} required minLength={6} />
            </div>
            {pwMsg && <p className="muted">{pwMsg}</p>}
            <button type="submit">Update password</button>
          </form>
        </div>
      </div>
    </Layout>
  );
}
