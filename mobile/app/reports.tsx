import { useCallback, useState } from "react";
import { View, Text, FlatList, Pressable, StyleSheet, Image, ActivityIndicator, RefreshControl } from "react-native";
import { useRouter, useFocusEffect } from "expo-router";
import { useRequireAuth } from "../services/useRequireAuth";
import { reportsApi, WasteReport } from "../services/resources";
import { API_BASE_URL } from "../constants/config";
import StatusPill from "../components/StatusPill";
import { colors, severityColor } from "../constants/theme";
import { formatReportId } from "../services/logic";

export default function Reports() {
  useRequireAuth();
  const router = useRouter();
  const [reports, setReports] = useState<WasteReport[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  async function load() {
    try {
      const res = await reportsApi.list();
      setReports(res.data);
    } catch {
      // leave whatever was previously loaded on screen
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  useFocusEffect(
    useCallback(() => {
      load();
    }, [])
  );

  if (loading) {
    return <View style={styles.center}><ActivityIndicator color={colors.brand} /></View>;
  }

  return (
    <FlatList
      style={{ backgroundColor: colors.bg }}
      contentContainerStyle={{ padding: 16 }}
      data={reports}
      keyExtractor={(r) => String(r.id)}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}
      ListEmptyComponent={<Text style={styles.empty}>No reports yet. Report your first from the Home screen.</Text>}
      renderItem={({ item }) => (
        <Pressable style={styles.card} onPress={() => router.push({ pathname: "/report-details", params: { id: item.id } })}>
          <Image source={{ uri: `${API_BASE_URL}/${item.image_path}` }} style={styles.thumb} />
          <View style={{ flex: 1 }}>
            <Text style={styles.reportId}>{formatReportId(item.id)}</Text>
            <Text style={styles.wasteType}>{item.is_waste === true ? "Waste" : item.is_waste === false ? "Not waste" : "Awaiting review"}</Text>
            {item.severity ? <Text style={[styles.sev, { color: severityColor[item.severity] }]}>{item.severity} severity</Text> : null}
            <Text style={styles.date}>{new Date(item.created_at).toLocaleDateString()}</Text>
          </View>
          <StatusPill status={item.status} />
        </Pressable>
      )}
    />
  );
}

const styles = StyleSheet.create({
  center: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.bg },
  empty: { textAlign: "center", color: colors.inkSoft, marginTop: 40 },
  card: {
    flexDirection: "row", alignItems: "center", gap: 12, backgroundColor: "#fff",
    borderRadius: 10, borderWidth: 1, borderColor: colors.line, padding: 12, marginBottom: 10,
  },
  thumb: { width: 52, height: 52, borderRadius: 8, backgroundColor: colors.line },
  reportId: { fontWeight: "700", color: colors.ink },
  wasteType: { color: colors.inkSoft, fontSize: 13 },
  sev: { fontSize: 11, fontWeight: "700", marginTop: 2 },
  date: { color: colors.inkSoft, fontSize: 11, marginTop: 2 },
});
