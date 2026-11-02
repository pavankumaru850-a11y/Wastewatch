// Contract test: real responses captured from the FastAPI backend (tests/fixtures.json,
// regenerate with backend/tests script) must satisfy what the app's logic + screens read.
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { describeDetection, formatReportId } from "../services/logic.ts";

const fx = JSON.parse(readFileSync(new URL("./fixtures.json", import.meta.url), "utf8"));

test("real 'waste' response -> ok verdict with every field the result card reads", () => {
  const r = fx.waste;
  assert.equal(describeDetection(r).tone, "ok");
  for (const k of ["object_count", "model_version", "confidence_level", "severity", "priority_score"]) assert.notEqual(r[k], undefined, k);
  assert.equal(r.object_count, 2);
  for (const d of r.detections) for (const k of ["class_name", "confidence"]) assert.notEqual(d[k], undefined, k);
  for (const k of ["x1", "y1", "x2", "y2"]) assert.equal(typeof r.detections[0].box[k], "number", `box.${k}`);
});
test("any waste class (e.g. paper) is just 'Waste detected'", () => {
  const v = describeDetection(fx.paper);
  assert.equal(v.title, "Waste detected");
  assert.equal(v.isWaste, true);
});
test("real no-waste and not-waste responses are NOT waste but can still be saved", () => {
  for (const r of [fx.none, fx.not_waste]) {
    const v = describeDetection(r);
    assert.equal(v.isWaste, false);
    assert.match(v.title, /^Not waste/);
    assert.equal(v.canSubmit, true);
  }
  assert.equal(fx.not_waste.is_waste, false);
});
test("real low-confidence response is a warning", () => {
  const v = describeDetection(fx.low);
  assert.equal(v.tone, "warn");
  assert.match(v.title, /Low-confidence/);
});
test("real blurry-image response blocks submit", () => {
  const v = describeDetection(fx.quality);
  assert.equal(v.canSubmit, false);
  assert.match(v.title, /quality is too low/);
});
test("real model-unavailable response does not block the citizen", () => {
  const v = describeDetection(fx.unavailable);
  assert.equal(v.canSubmit, true);
  assert.match(v.title, /not available/);
});
test("real report has the fields the report screens read", () => {
  const r = fx.report;
  for (const k of ["id", "image_path", "status", "priority", "severity", "priority_score", "object_count", "model_version", "gps_accuracy", "is_possible_duplicate", "detections", "created_at"]) {
    assert.notEqual(r[k], undefined, `report.${k}`);
  }
  assert.equal(formatReportId(r.id), "WW-000001");
  for (const k of ["id", "class_name", "confidence", "x1", "y1", "x2", "y2"]) assert.notEqual(r.detections[0][k], undefined, `detection.${k}`);
  assert.equal(r.gps_accuracy, 7);
});
test("real history + notifications shapes", () => {
  assert.ok(Array.isArray(fx.history.history) && fx.history.history.length > 0);
  for (const k of ["new", "at"]) assert.notEqual(fx.history.history[0][k], undefined);
  assert.ok(fx.notifications.length > 0);
  for (const k of ["id", "title", "is_read", "created_at"]) assert.notEqual(fx.notifications[0][k], undefined);
});
