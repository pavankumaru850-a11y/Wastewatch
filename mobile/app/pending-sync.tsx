import { useCallback, useState } from "react";
import { View, Text, FlatList, Image, StyleSheet, Pressable, ActivityIndicator, Alert } from "react-native";
import { useFocusEffect } from "expo-router";
import { listPendingReports, deletePendingReport, clearSynced, PendingReport } from "../database/db";
import { syncPendingReports } from "../services/sync";
import { useNetworkSync } from "../services/useNetworkSync";
import { queueLabel, needsSync, formatReportId } from "../services/logic";
import { colors } from "../constants/theme";

export default function PendingSync() {
  const { isOnline } = useNetworkSync();
  const [items, setItems] = useState<PendingReport[]>([]);
  const [syncing, setSyncing] = useState(false);
  const [lastResult, setLastResult] = useState<string | null>(null);

  async function load() {
    setItems(await listPendingReports());
  }
  useFocusEffect(useCallback(() => { load(); }, []));

  const waiting = items.filter((i) => needsSync(i.status)).length;
  const syncedCount = items.length - waiting;

  async function handleSync() {
    setSyncing(true);
    setLastResult(null);
    const r = await syncPendingReports();
    await load();
    setSyncing(false);
    if (r.synced > 0 && r.failed === 0) setLastResult(`${r.synced} report${r.synced > 1 ? "s" : ""} synchronized`);
    else if (r.synced > 0) setLastResult(`${r.synced} synchronized, ${r.failed} still waiting`);
    else if (r.failed > 0) setLastResult("Could not synchronize. Check your connection and retry.");
  }

  function confirmDiscard(item: PendingReport) {
    Alert.alert("Discard this report?", "The photo and location saved on this phone will be deleted and it will NOT be uploaded.", [
      { text: "Keep", style: "cancel" },
      { text: "Discard", style: "destructive", onPress: async () => { await deletePendingReport(item.id); load(); } },
    ]);
  }

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <View style={styles.header}>
        <Text style={styles.headerText}>
          {waiting === 0 ? "No reports waiting for synchronization" : `${waiting} report${waiting > 1 ? "s" : ""} waiting for synchronization`}
        </Text>
        {!isOnline && <Text style={styles.offlineNote}>You're offline. These will sync automatically when you're back online.</Text>}
        {lastResult && <Text style={styles.result}>{lastResult}</Text>}
        <Pressable
          style={[styles.syncButton, (!isOnline || syncing || waiting === 0) && styles.syncButtonDisabled]}
          onPress={handleSync}
          disabled={!isOnline || syncing || waiting === 0}
        >
          {syncing ? <ActivityIndicator color="#fff" /> : <Text style={styles.syncButtonText}>Sync now / Retry</Text>}
        </Pressable>
        {syncedCount > 0 && (
          <Pressable onPress={async () => { await clearSynced(); load(); }}>
            <Text style={styles.clear}>Clear {syncedCount} synced from this list</Text>
          </Pressable>
        )}
      </View>

      <FlatList
        contentContainerStyle={{ padding: 16 }}
        data={items}
        keyExtractor={(i) => String(i.id)}
        ListEmptyComponent={<Text style={styles.empty}>Nothing here. Reports saved offline appear in this list.</Text>}
        renderItem={({ item }) => (
          <View style={styles.card}>
            <Image source={{ uri: item.image_uri }} style={styles.thumb} />
            <View style={{ flex: 1 }}>
              <Text style={styles.coords}>{item.latitude.toFixed(5)}, {item.longitude.toFixed(5)}</Text>
              <Text style={styles.date}>{new Date(item.created_at).toLocaleString()}</Text>
              <Text style={[styles.status, item.status === "FAILED" && styles.statusFailed, item.status === "SYNCED" && styles.statusOk]}>
                {queueLabel(item.status)}
                {item.status === "SYNCED" && item.server_report_id ? ` · ${formatReportId(item.server_report_id)}` : ""}
                {item.status === "FAILED" && item.last_error ? `: ${item.last_error}` : ""}
              </Text>
            </View>
            {item.status === "FAILED" && (
              <Pressable onPress={() => confirmDiscard(item)} accessibilityLabel="Discard report"><Text style={styles.discard}>Discard</Text></Pressable>
            )}
          </View>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  header: { padding: 16, backgroundColor: "#fff", borderBottomWidth: 1, borderColor: colors.line },
  headerText: { fontSize: 15, fontWeight: "700", color: colors.ink },
  offlineNote: { fontSize: 12, color: colors.rust, marginTop: 4 },
  result: { fontSize: 12, color: colors.brand, marginTop: 4, fontWeight: "600" },
  clear: { fontSize: 12, color: colors.inkSoft, marginTop: 10, textDecorationLine: "underline" },
  empty: { textAlign: "center", color: colors.inkSoft, marginTop: 40 },
  syncButton: { backgroundColor: colors.brand, borderRadius: 8, padding: 12, alignItems: "center", marginTop: 12 },
  syncButtonDisabled: { opacity: 0.5 },
  syncButtonText: { color: "#fff", fontWeight: "700" },
  card: { flexDirection: "row", gap: 12, backgroundColor: "#fff", borderRadius: 10, borderWidth: 1, borderColor: colors.line, padding: 12, marginBottom: 10, alignItems: "center" },
  thumb: { width: 52, height: 52, borderRadius: 8, backgroundColor: colors.line },
  coords: { fontWeight: "700", color: colors.ink, fontSize: 13 },
  date: { color: colors.inkSoft, fontSize: 11, marginTop: 2 },
  status: { color: colors.clay, fontSize: 12, marginTop: 4, fontWeight: "600" },
  statusFailed: { color: colors.rust },
  statusOk: { color: colors.brand },
  discard: { color: colors.rust, fontWeight: "700", fontSize: 12 },
});
