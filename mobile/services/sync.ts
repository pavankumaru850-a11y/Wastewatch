/**
 * services/sync.ts -- PENDING_UPLOAD/FAILED/UPLOADING -> upload with
 * client_uuid -> server confirms -> SYNCED. Never deletes on failure.
 * The server treats a repeated client_uuid as the same report, so retrying
 * after a crash or a lost response cannot create duplicates.
 */
import { reportsApi } from "./resources";
import { isNetworkError, needsSync } from "./logic";
import {
  listPendingReports, markUploading, markFailed, markSynced, PendingReport,
} from "../database/db";

export interface SyncResult {
  synced: number;
  failed: number;
  remaining: number;
}

let running: Promise<SyncResult> | null = null;

async function uploadOne(report: PendingReport): Promise<"ok" | "failed" | "offline"> {
  await markUploading(report.id);
  try {
    const form = new FormData();
    form.append("image", { uri: report.image_uri, name: "report.jpg", type: "image/jpeg" } as any);
    form.append("latitude", String(report.latitude));
    form.append("longitude", String(report.longitude));
    if (report.accuracy != null) form.append("gps_accuracy", String(report.accuracy));
    if (report.description) form.append("description", report.description);
    if (report.village) form.append("village", report.village);
    if (report.district) form.append("district", report.district);
    if (report.client_uuid) form.append("client_uuid", report.client_uuid);
    // Original capture time is preserved by the queue row; the server stamps receipt time.

    const res = await reportsApi.create(form);
    await markSynced(report.id, res.data.id);
    return "ok";
  } catch (err: any) {
    const offline = isNetworkError(err);
    const message = offline ? "No connection to the server" : err?.response?.data?.detail || err?.message || "Upload failed";
    await markFailed(report.id, message);
    return offline ? "offline" : "failed";
  }
}

async function runOnce(): Promise<SyncResult> {
  const queue = (await listPendingReports()).filter((r) => needsSync(r.status)).reverse(); // oldest first
  let synced = 0;
  let failed = 0;
  for (const report of queue) {
    const outcome = await uploadOne(report);
    if (outcome === "ok") synced += 1;
    else failed += 1;
    if (outcome === "offline") { // connection is gone: stop hammering, the rest stay queued
      failed += queue.length - synced - failed;
      break;
    }
  }
  return { synced, failed, remaining: failed };
}

/** Single-flight: overlapping triggers (several screens listen for connectivity) share one pass. */
export function syncPendingReports(): Promise<SyncResult> {
  if (!running) running = runOnce().finally(() => { running = null; });
  return running;
}
