/**
 * services/logic.ts -- pure functions with NO React Native imports, so they
 * can be unit-tested with plain Node (npm test). Screens call these instead
 * of embedding decisions in JSX.
 */

export interface DetectionResult {
  success: boolean;
  detected: boolean;
  /** true = waste, false = not waste, null/undefined = the AI could not decide */
  is_waste?: boolean | null;
  code?: string | null;
  message?: string | null;
  detections: Array<{
    class_name: string;
    confidence: number;
    confidence_level?: string | null;
    bbox?: number[];
    box: { x1: number; y1: number; x2: number; y2: number };
  }>;
  object_count: number;
  model_version?: string | null;
  confidence_level?: string | null;
  severity?: string | null;
  severity_score?: number | null;
  priority_score?: number | null;
  priority_level?: string | null;
}

export type Tone = "ok" | "warn" | "error";

export interface Verdict {
  tone: Tone;
  title: string;
  /** false only when the photo itself is unusable and must be retaken */
  canSubmit: boolean;
  /** the AI decision; null when it could not decide (staff will review) */
  isWaste: boolean | null;
}

/** Turns the server's detection response into a user-facing verdict. Never invents a result. */
export function describeDetection(r: DetectionResult): Verdict {
  if (!r.success) {
    if (r.code === "IMAGE_QUALITY_LOW") {
      return { tone: "error", title: r.message || "Image quality is too low. Please capture a clearer image.", canSubmit: false, isWaste: null };
    }
    if (r.code === "MODEL_UNAVAILABLE") {
      return { tone: "warn", title: "AI detection is not available right now. You can still submit; staff will review the photo.", canSubmit: true, isWaste: null };
    }
    return { tone: "warn", title: r.message || "Something went wrong. Please try again.", canSubmit: true, isWaste: null };
  }
  // Not waste: the photo is still saved (separately), but it creates no cleanup request.
  if (r.is_waste === false || !r.detected || r.detections.length === 0) {
    return { tone: "warn", title: "Not waste. This photo will be saved separately and no cleanup request will be created.", canSubmit: true, isWaste: false };
  }
  if (r.code === "LOW_CONFIDENCE") {
    return { tone: "warn", title: r.message || "Low-confidence detection. Please capture a clearer image.", canSubmit: true, isWaste: true };
  }
  return { tone: "ok", title: r.message || "Waste detected", canSubmit: true, isWaste: true };
}

export function formatReportId(id: number): string {
  return `WW-${String(id).padStart(6, "0")}`;
}

export function percent(conf: number | null | undefined): string {
  return conf == null ? "-" : `${Math.round(conf * 100)}%`;
}

/** Idempotency key: the server returns the ORIGINAL report if the same key is sent twice. */
export function makeClientUuid(now: number = Date.now(), rand: () => number = Math.random): string {
  const part = () => Math.floor(rand() * 0xffffffff).toString(16).padStart(8, "0");
  return `ww-${now.toString(16)}-${part()}-${part()}`;
}

/** True when the request never got an HTTP response (offline, DNS, timeout) -> safe to queue and retry. */
export function isNetworkError(err: unknown): boolean {
  const e = err as { response?: unknown; code?: string; message?: string } | null;
  return !!e && !e.response;
}

export type QueueStatus = "PENDING_UPLOAD" | "UPLOADING" | "FAILED" | "SYNCED";

export function queueLabel(status: QueueStatus): string {
  switch (status) {
    case "SYNCED": return "Synced";
    case "FAILED": return "Sync Failed";
    case "UPLOADING": return "Syncing...";
    default: return "Pending Sync";
  }
}

/** Rows the sync pass should (re)try. UPLOADING is included: it means the app died mid-upload,
 *  and the client_uuid makes the retry safe (no duplicate report). */
export function needsSync(status: QueueStatus): boolean {
  return status !== "SYNCED";
}
