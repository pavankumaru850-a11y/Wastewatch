import { useEffect } from "react";
import { View, Text, ActivityIndicator, StyleSheet } from "react-native";
import { useRouter } from "expo-router";
import { useAuth } from "../context/AuthContext";
import { colors } from "../constants/theme";
import { API_BASE_URL } from "../constants/config";

export default function Splash() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    router.replace(user ? "/home" : "/login");
  }, [loading, user]);

  return (
    <View style={styles.container}>
      <Text style={styles.title}>WasteWatch</Text>
      <Text style={styles.subtitle}>Roadside waste reporting</Text>
      <ActivityIndicator size="large" color="#fff" style={{ marginTop: 24 }} />
      {!API_BASE_URL && (
        <Text style={styles.warning}>
          EXPO_PUBLIC_API_URL is not set. Add it to .env (see README) before logging in.
        </Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.brandDark, alignItems: "center", justifyContent: "center", padding: 24 },
  title: { color: "#fff", fontSize: 32, fontWeight: "800" },
  subtitle: { color: "#cfe3d6", fontSize: 14, marginTop: 4 },
  warning: { color: "#f3c9a8", fontSize: 12, textAlign: "center", marginTop: 32 },
});
