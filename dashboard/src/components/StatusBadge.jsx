export default function StatusBadge({ status }) {
  const color = `var(--status-${status?.toLowerCase()}, var(--gray))`;
  return (
    <span className="badge" style={{ background: color }}>
      {status?.replaceAll("_", " ")}
    </span>
  );
}
