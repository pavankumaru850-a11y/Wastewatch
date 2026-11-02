/**
 * database/db.ts -- the offline queue. A report captured with no signal is
 * written here first (PENDING_UPLOAD) together with a client_uuid. The row and
 * the photo file live on disk, so nothing is lost if the app is closed.
 * After the server confirms, the row becomes SYNCED (kept so the user can SEE
 * it synced); it is never deleted before confirmation.
 */
import * as SQLite from "expo-sqlite";
import type { QueueStatus } from "../services/logic";

export interface PendingReport {
  id: number;
  client_uuid: string | null;
  image_uri: string;
  latitude: number;
  longitude: number;
  accuracy: number | null;
  description: string | null;
  village: string | null;
  district: string | null;
  created_at: string;
  status: QueueStatus;
  last_error: string | null;
  server_report_id: number | null;
}

let dbPromise: Promise<SQLite.SQLiteDatabase> | null = null;

function getDb() {
  if (!dbPromise) {
    dbPromise = SQLite.openDatabaseAsync("wastewatch.db").then(async (db) => {
      await db.execAsync(`
        CREATE TABLE IF NOT EXISTS pending_reports (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          image_uri TEXT NOT NULL,
          latitude REAL NOT NULL,
          longitude REAL NOT NULL,
          accuracy REAL,
          description TEXT,
          village TEXT,
          district TEXT,
          created_at TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'PENDING_UPLOAD',
          last_error TEXT
        );
      `);
      // Upgrade installs created by the previous app version.
      const cols = await db.getAllAsync<{ name: string }>(`PRAGMA table_info(pending_reports)`);
      const have = new Set(cols.map((c) => c.name));
      if (!have.has("client_uuid")) await db.execAsync(`ALTER TABLE pending_reports ADD COLUMN client_uuid TEXT`);
      if (!have.has("server_report_id")) await db.execAsync(`ALTER TABLE pending_reports ADD COLUMN server_report_id INTEGER`);
      return db;
    });
  }
  return dbPromise;
}

export async function enqueuePendingReport(
  data: Pick<PendingReport, "client_uuid" | "image_uri" | "latitude" | "longitude" | "accuracy" | "description" | "village" | "district">
): Promise<number> {
  const db = await getDb();
  const result = await db.runAsync(
    `INSERT INTO pending_reports (client_uuid, image_uri, latitude, longitude, accuracy, description, village, district, created_at, status)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING_UPLOAD')`,
    data.client_uuid, data.image_uri, data.latitude, data.longitude, data.accuracy,
    data.description, data.village, data.district, new Date().toISOString()
  );
  return result.lastInsertRowId as number;
}

export async function listPendingReports(): Promise<PendingReport[]> {
  const db = await getDb();
  return db.getAllAsync<PendingReport>(`SELECT * FROM pending_reports ORDER BY created_at DESC`);
}

/** Reports still waiting to reach the server (SYNCED ones don't count). */
export async function countPendingReports(): Promise<number> {
  const db = await getDb();
  const row = await db.getFirstAsync<{ n: number }>(`SELECT COUNT(*) as n FROM pending_reports WHERE status != 'SYNCED'`);
  return row?.n ?? 0;
}

export async function markUploading(id: number) {
  const db = await getDb();
  await db.runAsync(`UPDATE pending_reports SET status = 'UPLOADING' WHERE id = ?`, id);
}

export async function markFailed(id: number, error: string) {
  const db = await getDb();
  await db.runAsync(`UPDATE pending_reports SET status = 'FAILED', last_error = ? WHERE id = ?`, error, id);
}

/** Only called after the server has confirmed the upload. */
export async function markSynced(id: number, serverReportId: number) {
  const db = await getDb();
  await db.runAsync(`UPDATE pending_reports SET status = 'SYNCED', server_report_id = ?, last_error = NULL WHERE id = ?`, serverReportId, id);
}

export async function clearSynced() {
  const db = await getDb();
  await db.runAsync(`DELETE FROM pending_reports WHERE status = 'SYNCED'`);
}

/** User explicitly discards a queued report (e.g. permanently failing). */
export async function deletePendingReport(id: number) {
  const db = await getDb();
  await db.runAsync(`DELETE FROM pending_reports WHERE id = ?`, id);
}
