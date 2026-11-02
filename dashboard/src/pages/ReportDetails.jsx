import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import Layout from "../components/Layout";
import StatusBadge from "../components/StatusBadge";
import { BoxedImage, SeverityBadge, errText, rid, resultLabel } from "../components/ui";
import { reportsApi, adminApi, duplicatesApi } from "../services/resources";
import { API_URL } from "../services/api";
import { useAuth } from "../context/AuthContext";

const img = (p) => `${API_URL}/${p}`;

export default function ReportDetails() {
  const { id } = useParams();
  const { user } = useAuth();
  const isAdmin = user?.role === "ADMIN";
  const [report, setReport] = useState(null);
  const [hist, setHist] = useState(null);
  const [cleanup, setCleanup] = useState(null);
  const [dups, setDups] = useState([]);
  const [staffList, setStaffList] = useState([]);
  const [msg, setMsg] = useState({ text: "", error: false });
  const [selectedStaff, setSelectedStaff] = useState("");
  const [beforeFile, setBeforeFile] = useState(null);
  const [afterFile, setAfterFile] = useState(null);
  const [remarks, setRemarks] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    const res = await reportsApi.get(id);
    setReport(res.data);
    reportsApi.history(id).then((r) => setHist(r.data)).catch(() => {});
    if (["IN_PROGRESS", "CLEANED", "CLEANUP_VERIFICATION", "CLOSED", "COMPLETED"].includes(res.data.status)) {
      reportsApi.cleanup(id).then((r) => setCleanup(r.data)).catch(() => setCleanup(null));  // evidence only exists once cleanup began
    } else {
      setCleanup(null);
    }
    duplicatesApi.list("").then((r) => setDups(r.data.filter((d) => d.report_id === Number(id) || d.candidate_id === Number(id)))).catch(() => {});
  }

  useEffect(() => {
    load().catch((e) => setMsg({ text: errText(e), error: true }));
    if (isAdmin) adminApi.listUsers("STAFF").then((r) => setStaffList(r.data));
  }, [id]);

  async function act(fn, okText) {
    setBusy(true);
    try {
      await fn();
      setMsg({ text: okText, error: false });
      try { await load(); } catch { /* the action succeeded; keep the success message even if a refresh is no longer permitted */ }
    } catch (e) {
      setMsg({ text: errText(e), error: true });
    } finally {
      setBusy(false);
    }
  }

  if (!report) return <Layout title="Report"><p>{msg.text || "Loading..."}</p></Layout>;

  const next = hist?.allowed_next || [];
  const isMine = report.assignment?.staff_id === user.id;
  const canWork = isAdmin || isMine;
  const inReview = ["NEW", "AI_DETECTED", "STAFF_REVIEW"].includes(report.status);

  function reject() {
    const reason = window.prompt("Reason for rejecting this report (required):");
    if (reason && reason.trim()) act(() => reportsApi.setStatus(id, "REJECTED", reason.trim()), "Report rejected.");
  }

  function complete(e) {
    e.preventDefault();
    if (!afterFile) { setMsg({ text: "Attach the AFTER photo first.", error: true }); return; }
    const fd = new FormData();
    fd.append("completion_image", afterFile);
    fd.append("remarks", remarks);
    const send = () => act(() => reportsApi.complete(id, fd), "Cleanup submitted for verification.");
    if (!navigator.geolocation) return send();
    navigator.geolocation.getCurrentPosition(
      (pos) => { fd.append("latitude", pos.coords.latitude); fd.append("longitude", pos.coords.longitude); send(); },
      () => send(), { timeout: 5000 });
  }

  function uploadBefore() {
    if (!beforeFile) { setMsg({ text: "Choose a BEFORE photo first.", error: true }); return; }
    const fd = new FormData(); fd.append("image", beforeFile);
    act(() => reportsApi.before(id, fd), "Before image saved.");
  }

  const cleanupDecided = cleanup?.verified_at;

  return (
    <Layout title={`Report ${rid(report.id)}`}>
      {msg.text && (
        <div className="card" role="status" style={{ marginBottom: 16, background: msg.error ? "#fbeceb" : "#eef6f0", borderColor: msg.error ? "var(--rust)" : "var(--brand)" }}>
          {msg.text}
        </div>
      )}

      {(report.is_possible_duplicate || dups.length > 0) && (
        <div className="card" style={{ marginBottom: 16, borderColor: "#b8792e" }}>
          <h2>Possible duplicate</h2>
          {dups.map((d) => (
            <div key={d.id} style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap", padding: "6px 0", borderBottom: "1px solid var(--line)" }}>
              <span>{rid(d.report_id)} vs <Link to={`/reports/${d.candidate_id}`}>{rid(d.candidate_id)}</Link></span>
              <span className="muted">{d.distance_m} m · {d.time_diff_minutes} min · image distance {d.hash_distance ?? "n/a"} · {d.same_category ? "same category" : "different category"}</span>
              <strong>{d.decision}</strong>
              {d.decision === "PENDING" && (
                <span style={{ display: "flex", gap: 6 }}>
                  <button disabled={busy} onClick={() => act(() => duplicatesApi.decide(d.id, "CONFIRMED"), "Marked as duplicate.")}>Confirm duplicate</button>
                  <button className="secondary" disabled={busy} onClick={() => act(() => duplicatesApi.decide(d.id, "NOT_DUPLICATE"), "Marked as not a duplicate.")}>Not duplicate</button>
                  <button className="danger" disabled={busy} onClick={() => window.confirm("Merge: this newer report is closed as a duplicate of the older one. Continue?") && act(() => duplicatesApi.decide(d.id, "MERGED"), "Reports merged.")}>Merge</button>
                </span>
              )}
            </div>
          ))}
        </div>
      )}

      <div className="grid-2">
        <div>
          <div className="card" style={{ marginBottom: 16 }}>
            <h2>Reported image</h2>
            <BoxedImage src={img(report.image_path)} detections={report.detections} />
          </div>

          <div className="card" style={{ marginBottom: 16 }}>
            <h2>AI detection</h2>
            {report.detections.length === 0 ? (
              <p className="muted">No supported waste detected (or the AI model was not available when this report was submitted). A person must review the photo.</p>
            ) : (
              <>
                <p>Objects detected: <strong>{report.object_count}</strong> &middot; Model: <strong>{report.model_version || "-"}</strong> &middot; Confidence: <strong>{report.confidence_level || "-"}</strong></p>
                {report.detections.map((d) => (
                  <div key={d.id} style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", borderBottom: "1px solid var(--line)" }}>
                    <span>{d.class_name}</span>
                    <span className="muted">Detection Confidence: {Math.round(d.confidence * 100)}%</span>
                  </div>
                ))}
              </>
            )}
          </div>

          {cleanup && (
            <div className="card" style={{ marginBottom: 16 }}>
              <h2>Cleanup evidence</h2>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <div><div className="muted">Before</div>{cleanup.before_image && <img src={img(cleanup.before_image)} alt="Before cleanup" style={{ width: "100%", borderRadius: 6 }} />}</div>
                <div><div className="muted">After</div>{cleanup.after_image ? <img src={img(cleanup.after_image)} alt="After cleanup" style={{ width: "100%", borderRadius: 6 }} /> : <p className="muted">Not uploaded yet.</p>}</div>
              </div>
              {cleanup.after_image && (cleanup.analysis_available ? (
                <p style={{ marginTop: 10 }}>
                  AI count: <strong>{cleanup.before_detection_count}</strong> before &rarr; <strong>{cleanup.after_detection_count}</strong> after
                  {cleanup.improvement_percentage != null && <> &middot; improvement <strong>{cleanup.improvement_percentage}%</strong></>}
                </p>
              ) : (
                <p className="muted" style={{ marginTop: 10 }}>AI comparison unavailable (model not running). Please compare the photos by eye.</p>
              ))}
              {cleanup.remarks && <p>Remarks: {cleanup.remarks}</p>}
              {cleanupDecided && <p className="muted">Reviewed {new Date(cleanup.verified_at).toLocaleString()} by user #{cleanup.verified_by}</p>}
              {report.status === "CLEANUP_VERIFICATION" && !isAdmin && isMine && (
                <p className="muted" style={{ marginTop: 10 }}>Waiting for another staff member or an admin to verify this cleanup (you cannot sign off your own work).</p>
              )}
              {report.status === "CLEANUP_VERIFICATION" && (isAdmin || !isMine) && (
                <div style={{ display: "flex", gap: 8, marginTop: 10, flexWrap: "wrap" }}>
                  <input aria-label="Verification remarks" placeholder="Remarks (optional)" value={remarks} onChange={(e) => setRemarks(e.target.value)} style={{ flex: 1, minWidth: 180 }} />
                  <button disabled={busy} onClick={() => act(() => reportsApi.decideCleanup(id, true, remarks), "Cleanup approved. Report closed.")}>Approve &amp; close</button>
                  <button className="danger" disabled={busy} onClick={() => act(() => reportsApi.decideCleanup(id, false, remarks || "Cleanup insufficient"), "Sent back for more cleanup.")}>Insufficient &mdash; reopen</button>
                </div>
              )}
            </div>
          )}

          {hist && (
            <div className="card">
              <h2>Status history</h2>
              {hist.history.length === 0 && <p className="muted">No status changes yet.</p>}
              {hist.history.map((h, i) => (
                <div key={i} style={{ padding: "6px 0", borderBottom: "1px solid var(--line)" }}>
                  <StatusBadge status={h.new} /> <span className="muted">{new Date(h.at).toLocaleString()} · user #{h.by ?? "-"}</span>
                  {h.remarks && <div className="muted">{h.remarks}</div>}
                </div>
              ))}
            </div>
          )}
        </div>

        <div>
          <div className="card" style={{ marginBottom: 16 }}>
            <h2>Details</h2>
            <p><StatusBadge status={report.status} /> &nbsp; Severity: <SeverityBadge level={report.severity} /> &nbsp; Priority: <strong>{report.priority}</strong>{report.priority_score != null && ` (${report.priority_score}/100)`}</p>
            <p>AI result: <strong>{resultLabel(report)}</strong>{report.confidence ? ` (${Math.round(report.confidence * 100)}% sure)` : ""}</p>
            <p>Location: <span className="muted" style={{ fontFamily: "var(--font-mono)" }}>{report.latitude.toFixed(5)}, {report.longitude.toFixed(5)}</span>{report.gps_accuracy != null && <span className="muted"> (&plusmn;{Math.round(report.gps_accuracy)} m)</span>}</p>
            <p>Village / Town: {report.village || "-"} / {report.town || "-"}</p>
            <p>District / State / Country: {[report.district, report.state, report.country].map((v) => v || "-").join(" / ")}</p>
            {!report.address && !report.village && !report.town && <p className="muted">Address not available (reverse geocoding is optional).</p>}
            {report.address && <p>Address: {report.address}</p>}
            <p>Reported: {new Date(report.created_at).toLocaleString()}</p>
            {report.hotspot_id && <p>Hotspot: <Link to="/hotspots">#{report.hotspot_id}</Link></p>}
            {report.description && <p>Notes: {report.description}</p>}
            <a href={`https://www.openstreetmap.org/?mlat=${report.latitude}&mlon=${report.longitude}#map=17/${report.latitude}/${report.longitude}`} target="_blank" rel="noreferrer">Open in map &rarr;</a>
          </div>

          {report.status === "NOT_WASTE" && (
            <div className="card" style={{ marginBottom: 16, borderColor: "var(--brand)" }}>
              <h2>Saved as Not Waste</h2>
              <p className="muted">The AI found no waste in this photo, so it is stored separately and is not counted in the waste reports, map or hotspots.</p>
              {isAdmin && <button disabled={busy} onClick={() => act(() => reportsApi.reclassify(id, true, "Admin: this is waste"), "Moved to the waste reports.")}>Actually it is waste</button>}
            </div>
          )}

          {inReview && (
            <div className="card" style={{ marginBottom: 16 }}>
              <h2>Review</h2>
              <div className="field">
                <label>Is this really waste?</label>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  {next.includes("STAFF_REVIEW") && report.status !== "STAFF_REVIEW" && (
                    <button className="secondary" disabled={busy} onClick={() => act(() => reportsApi.setStatus(id, "STAFF_REVIEW", "Accepted for review"), "Accepted for review.")}>Accept for review</button>
                  )}
                  <button disabled={busy} onClick={() => act(() => adminApi.verifyReport(id, { verification_status: "CORRECT" }), "Report verified.")}>Yes, it is waste (verify)</button>
                  <button className="secondary" disabled={busy} onClick={() => act(() => reportsApi.setStatus(id, "NOT_WASTE", "Reviewer: not waste"), "Moved to Not Waste.")}>Not waste</button>
                  <button className="danger" disabled={busy} onClick={reject}>Reject</button>
                </div>
              </div>
            </div>
          )}

          {isAdmin && report.status === "VERIFIED" && (
            <div className="card" style={{ marginBottom: 16 }}>
              <h2>Assign cleanup</h2>
              <div style={{ display: "flex", gap: 8 }}>
                <select aria-label="Staff" value={selectedStaff} onChange={(e) => setSelectedStaff(e.target.value)} style={{ flex: 1 }}>
                  <option value="">Select staff...</option>
                  {staffList.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select>
                <button disabled={busy || !selectedStaff} onClick={() => act(() => reportsApi.assign(id, Number(selectedStaff), ""), "Assigned.")}>Assign</button>
              </div>
              <button className="danger" style={{ marginTop: 10 }} disabled={busy} onClick={reject}>Reject</button>
            </div>
          )}

          {isAdmin && report.status === "ASSIGNED" && (
            <div className="card" style={{ marginBottom: 16 }}>
              <p>Assigned to staff #{report.assignment?.staff_id}. Waiting for cleanup to start.</p>
            </div>
          )}

          {!isAdmin && isMine && report.status === "ASSIGNED" && (
            <div className="card" style={{ marginBottom: 16 }}>
              <h2>Cleanup task</h2>
              <button style={{ width: "100%" }} disabled={busy} onClick={() => act(() => reportsApi.setStatus(id, "IN_PROGRESS", "Cleanup started"), "Cleanup started.")}>Start cleanup</button>
            </div>
          )}

          {canWork && report.status === "IN_PROGRESS" && (
            <div className="card" style={{ marginBottom: 16 }}>
              <h2>Cleanup</h2>
              <div className="field">
                <label htmlFor="bf">Before photo (optional &mdash; defaults to the citizen&apos;s photo)</label>
                <div style={{ display: "flex", gap: 8 }}>
                  <input id="bf" type="file" accept="image/jpeg,image/png,image/webp" onChange={(e) => setBeforeFile(e.target.files[0])} />
                  <button className="secondary" disabled={busy} onClick={uploadBefore}>Upload</button>
                </div>
              </div>
              <form onSubmit={complete}>
                <div className="field">
                  <label htmlFor="af">After photo</label>
                  <input id="af" type="file" accept="image/jpeg,image/png,image/webp" onChange={(e) => setAfterFile(e.target.files[0])} />
                </div>
                <div className="field">
                  <label htmlFor="rm">Remarks</label>
                  <textarea id="rm" rows={3} style={{ width: "100%" }} value={remarks} onChange={(e) => setRemarks(e.target.value)} />
                </div>
                <button type="submit" style={{ width: "100%" }} disabled={busy}>Complete cleanup &amp; send for verification</button>
              </form>
            </div>
          )}

          {isAdmin && (
            <div className="card">
              <h2>Admin</h2>
              <div className="field">
                <label htmlFor="pr">Manual priority override</label>
                <select id="pr" value={report.priority} onChange={(e) => act(() => reportsApi.update(id, { priority: e.target.value }), "Priority updated.")} style={{ width: "100%" }}>
                  {["LOW", "MEDIUM", "HIGH", "CRITICAL"].map((p) => <option key={p} value={p}>{p}</option>)}
                </select>
              </div>
              <button className="secondary" onClick={() => act(() => adminApi.addToTraining(id), "Added to verified training dataset.")}>Add to training dataset</button>
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
}
