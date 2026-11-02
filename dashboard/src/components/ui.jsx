import { useState } from "react";
export const SEV_COLOR = { LOW: "#2f8a4f", MEDIUM: "#c9a227", HIGH: "#d9772b", CRITICAL: "#b83a2a" };

export function SeverityBadge({ level }) {
  if (!level) return <span className="muted">-</span>;
  return <span className="badge" style={{ background: SEV_COLOR[level] || "#6b7280" }}>{level}</span>;
}

export function errText(e) {
  return e?.response?.data?.detail || "Something went wrong. Please try again.";
}

export function download(blob, name) {
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = name; a.click();
  window.URL.revokeObjectURL(url);
}

export const rid = (id) => `WW-${String(id).padStart(6, "0")}`;

/** Image with AI bounding boxes drawn as an SVG overlay (coordinates are in original-image pixels). */
export function BoxedImage({ src, detections = [] }) {
  const [dim, setDim] = useState(null);
  return (
    <div style={{ position: "relative", lineHeight: 0 }}>
      <img src={src} alt="Report" style={{ width: "100%", borderRadius: 6 }}
        onLoad={(e) => setDim({ w: e.target.naturalWidth, h: e.target.naturalHeight })} />
      {dim && detections.length > 0 && (
        <svg viewBox={`0 0 ${dim.w} ${dim.h}`} style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
          {detections.map((d) => {
            const fs = Math.max(dim.w / 40, 12);
            const label = `${d.class_name} ${Math.round(d.confidence * 100)}%`;
            return (
              <g key={d.id ?? `${d.x1}-${d.y1}`}>
                <rect x={d.x1} y={d.y1} width={d.x2 - d.x1} height={d.y2 - d.y1} fill="none" stroke="#ffcc00" strokeWidth={Math.max(dim.w / 250, 2)} />
                <rect x={d.x1} y={Math.max(d.y1 - fs * 1.3, 0)} width={label.length * fs * 0.62 + 8} height={fs * 1.3} fill="#ffcc00" />
                <text x={d.x1 + 3} y={Math.max(d.y1 - fs * 0.3, fs)} fontSize={fs} fill="#000">
                  {label}
                </text>
              </g>
            );
          })}
        </svg>
      )}
    </div>
  );
}

/** One word for the AI decision on a report: waste / not waste / could not decide. */
export const resultLabel = (r) => (r.is_waste === true ? "Waste" : r.is_waste === false ? "Not waste" : "Needs review");
