import { useEffect, useState } from "react";
import { BarChart, Bar, PieChart, Pie, Cell, LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import Layout from "../components/Layout";
import { SEV_COLOR, errText } from "../components/ui";
import { analyticsApi } from "../services/resources";

const COLORS = ["#2f6b4f", "#b8792e", "#35618f", "#a8412a", "#6b7280", "#4a8a67", "#7c6fb0", "#2f8a8a"];
const short = (label) => (label.length > 5 ? label.slice(5) : label);

function Card({ title, children }) {
  return <div className="chart-card"><h2>{title}</h2>{children}</div>;
}
function Empty() { return <p className="muted">No data yet.</p>; }
const hasData = (arr) => arr && arr.some((x) => x.count > 0);

export default function Analytics() {
  const [data, setData] = useState(null);
  const [days, setDays] = useState(30);
  const [period, setPeriod] = useState("day");
  const [error, setError] = useState("");

  useEffect(() => {
    analyticsApi.summary(days).then((r) => setData(r.data)).catch((e) => setError(errText(e)));
  }, [days]);

  if (error) return <Layout title="Analytics"><div className="card" role="alert">{error}</div></Layout>;
  if (!data) return <Layout title="Analytics"><p>Loading...</p></Layout>;
  if (data.total_reports === 0) return <Layout title="Analytics"><div className="card">No reports yet &mdash; charts will fill in as reports arrive.</div></Layout>;

  const series = { day: data.reports_per_day, week: data.reports_per_week, month: data.reports_per_month }[period];
  const cc = data.cleanup_completion;
  const stat = (value, label) => (<div className="stat-card"><div className="value">{value ?? "-"}</div><div className="label">{label}</div></div>);

  return (
    <Layout title="Analytics">
      <div className="stat-grid" style={{ marginBottom: 12 }}>
        {stat(data.total_reports, "Reports")}
        {stat(cc.rate_percent != null ? `${cc.rate_percent}%` : null, "Cleanup completion")}
        {stat(data.avg_resolution_hours, "Avg resolution (hours)")}
        {stat(data.avg_cleanup_improvement_percent != null ? `${data.avg_cleanup_improvement_percent}%` : null, "Avg AI-verified improvement")}
        {stat(data.hotspots_total, "Hotspots")}
        {stat(data.avg_confidence != null ? `${Math.round(data.avg_confidence * 100)}%` : null, "Avg detection confidence")}
      </div>

      <div className="filters">
        <select aria-label="Period" value={period} onChange={(e) => setPeriod(e.target.value)}>
          <option value="day">Per day</option><option value="week">Per week (12 wks)</option><option value="month">Per month (12 mo)</option>
        </select>
        {period === "day" && (
          <select aria-label="Days" value={days} onChange={(e) => setDays(Number(e.target.value))}>
            <option value={7}>Last 7 days</option><option value={30}>Last 30 days</option><option value={90}>Last 90 days</option>
          </select>
        )}
      </div>

      <div className="grid-2">
        <Card title="Reports over time">
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={series}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e9e1" />
              <XAxis dataKey="label" tickFormatter={period === "month" ? (l) => l : short} fontSize={11} interval="preserveStartEnd" />
              <YAxis allowDecimals={false} fontSize={12} />
              <Tooltip />
              <Line type="monotone" dataKey="count" name="Reports" stroke="#35618f" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </Card>

        <Card title="Waste category distribution">
          {hasData(data.waste_categories) ? (
            <ResponsiveContainer width="100%" height={260}>
              <PieChart>
                <Pie data={data.waste_categories} dataKey="count" nameKey="label" outerRadius={90} label>
                  {data.waste_categories.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          ) : <Empty />}
        </Card>

        <Card title="Area-wise reports">
          {hasData(data.area_wise) ? (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={data.area_wise} layout="vertical">
                <XAxis type="number" allowDecimals={false} fontSize={12} />
                <YAxis type="category" dataKey="label" width={110} fontSize={12} />
                <Tooltip />
                <Bar dataKey="count" name="Reports" fill="#b8792e" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : <Empty />}
        </Card>

        <Card title="Hotspot frequency (reports per hotspot)">
          {hasData(data.hotspot_frequency) ? (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={data.hotspot_frequency}>
                <XAxis dataKey="label" fontSize={11} />
                <YAxis allowDecimals={false} fontSize={12} />
                <Tooltip />
                <Bar dataKey="count" name="Reports" radius={[4, 4, 0, 0]}>
                  {data.hotspot_frequency.map((h, i) => <Cell key={i} fill={SEV_COLOR[h.severity] || "#6b7280"} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : <Empty />}
        </Card>

        <Card title="Severity distribution">
          {hasData(data.severity_distribution) ? (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={data.severity_distribution}>
                <XAxis dataKey="label" fontSize={12} />
                <YAxis allowDecimals={false} fontSize={12} />
                <Tooltip />
                <Bar dataKey="count" name="Reports" radius={[4, 4, 0, 0]}>
                  {data.severity_distribution.map((s, i) => <Cell key={i} fill={SEV_COLOR[s.label] || "#6b7280"} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : <Empty />}
        </Card>

        <Card title="AI detection confidence">
          {hasData(data.confidence_distribution) ? (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={data.confidence_distribution}>
                <XAxis dataKey="label" fontSize={12} />
                <YAxis allowDecimals={false} fontSize={12} />
                <Tooltip />
                <Bar dataKey="count" name="Reports" fill="#a8412a" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : <Empty />}
        </Card>

        <Card title="Cleanup completion">
          <table>
            <tbody>
              <tr><td>Eligible reports (not rejected)</td><td>{cc.eligible}</td></tr>
              <tr><td>Closed</td><td>{cc.closed}</td></tr>
              <tr><td>In progress</td><td>{cc.in_progress}</td></tr>
              <tr><td>Awaiting verification</td><td>{cc.awaiting_verification}</td></tr>
              <tr><td>Completion rate</td><td>{cc.rate_percent != null ? `${cc.rate_percent}%` : "-"}</td></tr>
            </tbody>
          </table>
        </Card>

        <Card title="Priority distribution">
          {hasData(data.priority_distribution) ? (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={data.priority_distribution}>
                <XAxis dataKey="label" fontSize={12} />
                <YAxis allowDecimals={false} fontSize={12} />
                <Tooltip />
                <Bar dataKey="count" name="Reports" radius={[4, 4, 0, 0]}>
                  {data.priority_distribution.map((s, i) => <Cell key={i} fill={SEV_COLOR[s.label] || "#6b7280"} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : <Empty />}
        </Card>
      </div>
    </Layout>
  );
}
