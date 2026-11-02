import { useCallback, useState } from "react";
import { View, Text, FlatList, Pressable, StyleSheet, ActivityIndicator, RefreshControl } from "react-native";
import { useRouter, useFocusEffect } from "expo-router";
import { useRequireAuth } from "../services/useRequireAuth";
import { notificationsApi, NotificationItem } from "../services/resources";
import { formatReportId } from "../services/logic";
import { colors } from "../constants/theme";

export default function Notifications() {
  useRequireAuth();
  const router = useRouter();
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    try {
      setItems((await notificationsApi.list()).data);
      setError("");
    } catch {
      setError("Could not load notifications. Pull down to retry.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }
  useFocusEffect(useCallback(() => { load(); }, []));

  async function open(n: NotificationItem) {
    if (!n.is_read) {
      setItems((cur) => cur.map((x) => (x.id === n.id ? { ...x, is_read: true } : x)));
      notificationsApi.read(n.id).catch(() => {});
    }
    if (n.report_id) router.push({ pathname: "/report-details", params: { id: n.report_id } });
  }

  if (loading) return <View style={styles.center}><ActivityIndicator color={colors.brand} /></View>;

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      {items.some((n) => !n.is_read) && (
        <Pressable style={styles.readAll} onPress={async () => { await notificationsApi.readAll().catch(() => {}); load(); }}>
          <Text style={styles.readAllText}>Mark all as read</Text>
        </Pressable>
      )}
      <FlatList
        contentContainerStyle={{ padding: 16 }}
        data={items}
        keyExtractor={(n) => String(n.id)}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}
        ListEmptyComponent={<Text style={styles.empty}>{error || "No notifications yet."}</Text>}
        renderItem={({ item }) => (
          <Pressable style={[styles.card, !item.is_read && styles.unread]} onPress={() => open(item)}>
            <Text style={styles.title}>{item.title}</Text>
            {item.body ? <Text style={styles.body}>{item.body}</Text> : null}
            <Text style={styles.meta}>
              {item.report_id ? `${formatReportId(item.report_id)} · ` : ""}{new Date(item.created_at).toLocaleString()}
            </Text>
          </Pressable>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  center: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.bg },
  empty: { textAlign: "center", color: colors.inkSoft, marginTop: 40 },
  card: { backgroundColor: "#fff", borderRadius: 10, borderWidth: 1, borderColor: colors.line, padding: 12, marginBottom: 10 },
  unread: { borderColor: colors.brand, borderLeftWidth: 4 },
  title: { fontWeight: "700", color: colors.ink },
  body: { color: colors.inkSoft, marginTop: 2 },
  meta: { color: colors.inkSoft, fontSize: 11, marginTop: 4 },
  readAll: { padding: 12, alignItems: "flex-end", paddingRight: 16 },
  readAllText: { color: colors.brand, fontWeight: "700" },
});
