import { NavLink } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const ADMIN_LINKS = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/reports", label: "Reports" },
  { to: "/map", label: "Map" },
  { to: "/hotspots", label: "Hotspots" },
  { to: "/duplicates", label: "Duplicates" },
  { to: "/users", label: "Users & Staff" },
  { to: "/not-waste", label: "Not Waste" },
  { to: "/training", label: "Dataset & Training" },
  { to: "/analytics", label: "Analytics" },
  { to: "/audit-log", label: "Audit Log" },
  { to: "/system", label: "System & AI Models" },
  { to: "/notifications", label: "Notifications" },
  { to: "/settings", label: "Settings" },
];

const STAFF_LINKS = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/reports", label: "Assigned Reports" },
  { to: "/map", label: "Map" },
  { to: "/hotspots", label: "Hotspots" },
  { to: "/duplicates", label: "Duplicates" },
  { to: "/notifications", label: "Notifications" },
  { to: "/settings", label: "Settings" },
];

export default function Sidebar() {
  const { user, logout } = useAuth();
  const links = user?.role === "ADMIN" ? ADMIN_LINKS : STAFF_LINKS;

  return (
    <nav className="sidebar">
      <div className="brand">Waste<span>Watch</span></div>
      {links.map((l) => (
        <NavLink key={l.to} to={l.to} end={l.end}>
          {l.label}
        </NavLink>
      ))}
      <div className="role-tag">
        {user?.name} &middot; {user?.role}
        <div style={{ marginTop: 8 }}>
          <button className="secondary" style={{ width: "100%" }} onClick={logout}>
            Log out
          </button>
        </div>
      </div>
    </nav>
  );
}
