import { useCallback, useState } from "react";
import { View, Text, Pressable, StyleSheet } from "react-native";
import { useRouter, useFocusEffect } from "expo-router";
import * as Location from "expo-location";
import { useRequireAuth } from "../services/useRequireAuth";
import { useNetworkSync } from "../services/useNetworkSync";
import { notificationsApi } from "../services/resources";
import { colors } from "../constants/theme";

export default function Home() {
  const { user, loading } = useRequireAuth();
  const router = useRouter();
  const { isOnline, pendingCount } = useNetworkSync();
  const [gpsOk, setGpsOk] = useState<boolean | null>(null);
  const [unread, setUnread] = useState(0);

  useFocusEffect(useCallback(() => {
    (async () => {
      const { status } = await Location.getForegroundPermissionsAsync();
      setGpsOk(status === "granted");
    })();
    notificationsApi.list().then((r) => setUnread(r.data.filter((n) => !n.is_read).length)).catch(() => {});
  }, []));

  if (loading || !user) return null;

  return (
    <View style={styles.container}>
      <Text style={styles.greeting}>Hello, {user.name.split(" ")[0]}</Text>

      <View style={styles.statusRow}>
        <View style={[styles.statusPill, { backgroundColor: isOnline ? "#1f7a4d" : "#a8412a" }]}>
          <Text style={styles.statusText}>{isOnline === null ? "CHECKING..." : isOnline ? "ONLINE" : "OFFLINE"}</Text>
        </View>
        <View style={[styles.statusPill, { backgroundColor: gpsOk ? "#1f7a4d" : "#6b7280" }]}>
          <Text style={styles.statusText}>{gpsOk ? "GPS AVAILABLE" : "GPS UNAVAILABLE"}</Text>
        </View>
      </View>

      <Pressable style={styles.primaryButton} onPress={() => router.push("/camera")}>
        <Text style={styles.primaryButtonText}>Detect Roadside Waste</Text>
      </Pressable>

      <Pressable style={styles.button} onPress={() => router.push("/reports")}>
        <Text style={styles.buttonText}>My Reports</Text>
      </Pressable>

      <Pressable style={styles.button} onPress={() => router.push("/pending-sync")}>
        <Text style={styles.buttonText}>
          Pending Uploads{pendingCount > 0 ? ` (${pendingCount})` : ""}
        </Text>
      </Pressable>

      <Pressable style={styles.button} onPress={() => router.push("/notifications")}>
        <Text style={styles.buttonText}>Notifications{unread > 0 ? ` (${unread} new)` : ""}</Text>
      </Pressable>

      <Pressable style={styles.button} onPress={() => router.push("/help")}>
        <Text style={styles.buttonText}>Help</Text>
      </Pressable>

      <Pressable style={styles.button} onPress={() => router.push("/profile")}>
        <Text style={styles.buttonText}>Profile</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg, padding: 24, paddingTop: 32 },
  greeting: { fontSize: 22, fontWeight: "800", color: colors.ink, marginBottom: 16 },
  statusRow: { flexDirection: "row", gap: 8, marginBottom: 28 },
  statusPill: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 20 },
  statusText: { color: "#fff", fontSize: 11, fontWeight: "700" },
  primaryButton: { backgroundColor: colors.brand, borderRadius: 12, padding: 22, alignItems: "center", marginBottom: 16 },
  primaryButtonText: { color: "#fff", fontSize: 18, fontWeight: "800" },
  button: { backgroundColor: "#fff", borderWidth: 1, borderColor: colors.line, borderRadius: 12, padding: 18, alignItems: "center", marginBottom: 12 },
  buttonText: { color: colors.ink, fontSize: 16, fontWeight: "700" },
});
