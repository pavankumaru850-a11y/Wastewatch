import { useEffect, useState } from "react";
import { View, Text, StyleSheet, ActivityIndicator, ScrollView, Linking, Pressable } from "react-native";
import { useLocalSearchParams } from "expo-router";
import { useRequireAuth } from "../services/useRequireAuth";
import { reportsApi, WasteReport, StatusHistory } from "../services/resources";
import { API_BASE_URL } from "../constants/config";
import { formatReportId, percent } from "../services/logic";
import BoxedImage from "../components/BoxedImage";
import StatusPill from "../components/StatusPill";
import { colors, severityColor } from "../constants/theme";

export default function ReportDetails() {
  useRequireAuth();
  const { id } = useLocalSearchParams<{ id: string }>();
  const [report, setReport] = useState<WasteReport | null>(null);
  const [hist, setHist] = useState<StatusHistory | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!id) return;
    reportsApi.get(Number(id))
      .then((res) => setReport(res.data))
      .catch((err) => setError(err?.response?.data?.detail || "Could not load report."));
    reportsApi.history(Number(id)).then((r) => setHist(r.data)).catch(() => {});
  }, [id]);

  if (error) return <View style={styles.center}><Text style={styles.warn}>{error}</Text></View>;
  if (!report) return <View style={styles.center}><ActivityIndicator color={colors.brand} /></View>;

  const mapUrl = `https://www.openstreetmap.org/?mlat=${report.latitude}&mlon=${report.longitude}#map=17/${report.latitude}/${report.longitude}`;
  const boxes = report.detections.map((d) => ({ x1: d.x1, y1: d.y1, x2: d.x2, y2: d.y2, class_name: d.class_name, confidence: d.confidence }));

  return (
    <ScrollView style={{ backgroundColor: colors.bg }} contentContainerStyle={styles.container}>
      <BoxedImage uri={`${API_BASE_URL}/${report.image_path}`} boxes={boxes} />

      <View style={styles.row}>
        <Text style={styles.title}>{formatReportId(report.id)}</Text>
        <StatusPill status={report.status} />
      </View>

      {report.is_possible_duplicate && (
        <View style={[styles.card, { borderColor: colors.clay }]}>
          <Text style={styles.cardTitle}>Possible duplicate</Text>
          <Text style={styles.detectionRow}>A similar report exists nearby. Staff will review it; nothing has been deleted.</Text>
        </View>
      )}

      <View style={styles.card}>
        <Text style={styles.cardTitle}>AI Detection</Text>
        <Row label="AI result" value={report.is_waste === true ? "Waste" : report.is_waste === false ? "Not waste (saved separately)" : "Awaiting staff review"} />
        {report.confidence != null && <Row label="Detection Confidence" value={`${percent(report.confidence)}${report.confidence_level ? ` (${report.confidence_level})` : ""}`} />}
        {report.is_waste !== false && (
          <>
        <Row label="Objects detected" value={String(report.object_count ?? report.detections.length)} />
        <View style={styles.rowItem}>
          <Text style={styles.rowLabel}>Severity</Text>
          {report.severity
            ? <Text style={[styles.rowValue, { color: severityColor[report.severity], fontWeight: "800" }]}>{report.severity}</Text>
            : <Text style={styles.rowValue}>-</Text>}
        </View>
        <Row label="Priority" value={`${report.priority}${report.priority_score != null ? ` (${Math.round(report.priority_score)}/100)` : ""}`} />
          </>
        )}
        {report.model_version ? <Row label="Model" value={report.model_version} /> : null}
      </View>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>Location</Text>
        <Row label="GPS" value={`${report.latitude.toFixed(5)}, ${report.longitude.toFixed(5)}${report.gps_accuracy != null ? `  (±${Math.round(report.gps_accuracy)} m)` : ""}`} />
        {report.address ? <Row label="Address" value={report.address} /> : null}
        {[report.village, report.town, report.district, report.state, report.country].filter(Boolean).length > 0 && (
          <Row label="Area" value={[report.village, report.town, report.district, report.state, report.country].filter(Boolean).join(", ")} />
        )}
        <Row label="Reported" value={new Date(report.created_at).toLocaleString()} />
        {report.description ? <Row label="Notes" value={report.description} /> : null}
      </View>

      {report.detections.length > 0 && (
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Detected objects</Text>
          {report.detections.map((d) => (
            <Text key={d.id} style={styles.detectionRow}>{d.class_name} — {percent(d.confidence)}</Text>
          ))}
        </View>
      )}

      {hist && hist.history.length > 0 && (
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Progress</Text>
          {hist.history.map((h, i) => (
            <View key={i} style={styles.timelineItem}>
              <StatusPill status={h.new} />
              <Text style={styles.timelineDate}>{new Date(h.at).toLocaleString()}</Text>
              {h.remarks ? <Text style={styles.timelineRemark}>{h.remarks}</Text> : null}
            </View>
          ))}
        </View>
      )}

      <Pressable style={styles.mapButton} onPress={() => Linking.openURL(mapUrl)}>
        <Text style={styles.mapButtonText}>Open location in map</Text>
      </Pressable>
    </ScrollView>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.rowItem}>
      <Text style={styles.rowLabel}>{label}</Text>
      <Text style={styles.rowValue}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { padding: 16 },
  center: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.bg, padding: 24 },
  warn: { color: colors.rust, textAlign: "center" },
  row: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginTop: 14, marginBottom: 6 },
  title: { fontSize: 18, fontWeight: "800", color: colors.ink },
  card: { backgroundColor: "#fff", borderRadius: 10, borderWidth: 1, borderColor: colors.line, padding: 14, marginTop: 10 },
  cardTitle: { fontWeight: "700", color: colors.ink, marginBottom: 8 },
  rowItem: { marginBottom: 8 },
  rowLabel: { fontSize: 11, fontWeight: "700", color: colors.inkSoft, textTransform: "uppercase" },
  rowValue: { fontSize: 15, color: colors.ink },
  detectionRow: { fontSize: 14, color: colors.ink, paddingVertical: 3 },
  timelineItem: { paddingVertical: 6, borderBottomWidth: 1, borderColor: colors.line },
  timelineDate: { fontSize: 11, color: colors.inkSoft, marginTop: 4 },
  timelineRemark: { fontSize: 13, color: colors.ink, marginTop: 2 },
  mapButton: { backgroundColor: colors.brand, borderRadius: 10, padding: 15, alignItems: "center", marginTop: 16, marginBottom: 30 },
  mapButtonText: { color: "#fff", fontWeight: "700" },
});
