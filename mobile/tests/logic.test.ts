import test from "node:test";
import assert from "node:assert/strict";
import {
  describeDetection, formatReportId, percent, makeClientUuid, isNetworkError, queueLabel, needsSync,
} from "../services/logic.ts";
import type { DetectionResult } from "../services/logic.ts";

const box = { x1: 0, y1: 0, x2: 10, y2: 10 };
const base: DetectionResult = { success: true, detected: true, detections: [{ class_name: "plastic", confidence: 0.9, box }], object_count: 1 };

test("valid detection is ok and submittable", () => {
  const v = describeDetection({ ...base, code: "WASTE_DETECTED", message: "Waste detected" });
  assert.deepEqual([v.tone, v.canSubmit, v.title], ["ok", true, "Waste detected"]);
});
test("a waste result carries isWaste=true", () => {
  assert.equal(describeDetection({ ...base, is_waste: true, code: "WASTE_DETECTED", message: "Waste detected" }).isWaste, true);
});
test("not waste -> says so, is saved separately, and can still be submitted", () => {
  for (const r of [
    { success: true, detected: false, is_waste: false, detections: [], object_count: 0, code: "NOT_WASTE" },
    { success: true, detected: false, detections: [], object_count: 0, code: "NO_WASTE" },
  ]) {
    const v = describeDetection(r);
    assert.equal(v.isWaste, false);
    assert.match(v.title, /^Not waste/);
    assert.match(v.title, /no cleanup request/);
    assert.equal(v.canSubmit, true);
  }
});
test("AI unavailable -> isWaste is null (staff decide)", () => {
  assert.equal(describeDetection({ success: false, detected: false, detections: [], object_count: 0, code: "MODEL_UNAVAILABLE" }).isWaste, null);
});
test("low confidence is a warning, not a success", () => {
  const v = describeDetection({ ...base, code: "LOW_CONFIDENCE", message: "Low-confidence detection. Please capture a clearer image." });
  assert.equal(v.tone, "warn");
  assert.match(v.title, /Low-confidence/);
});
test("bad image quality blocks submission", () => {
  const v = describeDetection({ success: false, detected: false, detections: [], object_count: 0, code: "IMAGE_QUALITY_LOW", message: "Image quality is too low. Please capture a clearer image." });
  assert.deepEqual([v.tone, v.canSubmit], ["error", false]);
});
test("model unavailable does not block the citizen", () => {
  const v = describeDetection({ success: false, detected: false, detections: [], object_count: 0, code: "MODEL_UNAVAILABLE" });
  assert.equal(v.canSubmit, true);
  assert.match(v.title, /not available/);
});
test("unknown failure never leaks raw errors", () => {
  const v = describeDetection({ success: false, detected: false, detections: [], object_count: 0 });
  assert.equal(v.title, "Something went wrong. Please try again.");
});
test("formatters", () => {
  assert.equal(formatReportId(42), "WW-000042");
  assert.equal(percent(0.913), "91%");
  assert.equal(percent(null), "-");
});
test("client uuid: unique, stable format, deterministic with injected inputs", () => {
  const seen = new Set(Array.from({ length: 500 }, () => makeClientUuid()));
  assert.equal(seen.size, 500);
  assert.equal(makeClientUuid(255, () => 0), "ww-ff-00000000-00000000");
  assert.match(makeClientUuid(), /^ww-[0-9a-f]+-[0-9a-f]{8}-[0-9a-f]{8}$/);
});
test("network vs server errors", () => {
  assert.equal(isNetworkError({ message: "Network Error" }), true);
  assert.equal(isNetworkError({ code: "ECONNABORTED" }), true);
  assert.equal(isNetworkError({ response: { status: 400 } }), false);
  assert.equal(isNetworkError(null), false);
});
test("queue labels + which rows get retried", () => {
  assert.equal(queueLabel("PENDING_UPLOAD"), "Pending Sync");
  assert.equal(queueLabel("FAILED"), "Sync Failed");
  assert.equal(queueLabel("SYNCED"), "Synced");
  assert.equal(needsSync("FAILED"), true);
  assert.equal(needsSync("UPLOADING"), true); // crashed mid-upload -> retry is safe (idempotent)
  assert.equal(needsSync("SYNCED"), false);
});
