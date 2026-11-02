import { useState } from "react";
import { View, Text, TextInput, Pressable, StyleSheet, ScrollView, Alert } from "react-native";
import { useRouter } from "expo-router";
import { useRequireAuth } from "../services/useRequireAuth";
import { useAuth } from "../context/AuthContext";
import { profileApi } from "../services/resources";
import { colors } from "../constants/theme";
import { API_BASE_URL } from "../constants/config";

export default function Profile() {
  const { user } = useRequireAuth();
  const { logout, refreshUser } = useAuth();
  const router = useRouter();
  const [phone, setPhone] = useState(user?.phone || "");
  const [village, setVillage] = useState(user?.village || "");
  const [district, setDistrict] = useState(user?.district || "");
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");

  if (!user) return null;

  async function save() {
    setSaving(true);
    setMsg("");
    try {
      await profileApi.update({ phone, village, district });
      await refreshUser();
      setMsg("Saved.");
    } catch (err: any) {
      setMsg(err?.response?.data?.detail || "Could not save changes.");
    } finally {
      setSaving(false);
    }
  }

  function handleLogout() {
    Alert.alert("Log out", "Are you sure you want to log out?", [
      { text: "Cancel", style: "cancel" },
      { text: "Log out", style: "destructive", onPress: async () => { await logout(); router.replace("/login"); } },
    ]);
  }

  return (
    <ScrollView style={{ backgroundColor: colors.bg }} contentContainerStyle={styles.container}>
      <View style={styles.headerCard}>
        <Text style={styles.name}>{user.name}</Text>
        <Text style={styles.email}>{user.email}</Text>
        <Text style={styles.role}>{user.role}</Text>
      </View>

      <Text style={styles.label}>Phone</Text>
      <TextInput style={styles.input} keyboardType="phone-pad" value={phone} onChangeText={setPhone} />

      <Text style={styles.label}>Village</Text>
      <TextInput style={styles.input} value={village} onChangeText={setVillage} />

      <Text style={styles.label}>District</Text>
      <TextInput style={styles.input} value={district} onChangeText={setDistrict} />

      {!!msg && <Text style={styles.msg}>{msg}</Text>}

      <Pressable style={styles.button} onPress={save} disabled={saving}>
        <Text style={styles.buttonText}>{saving ? "Saving..." : "Save changes"}</Text>
      </Pressable>

      <Pressable style={styles.logoutButton} onPress={handleLogout}>
        <Text style={styles.logoutText}>Log out</Text>
      </Pressable>

      <Text style={styles.apiNote}>Connected to: {API_BASE_URL || "not configured"}</Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { padding: 24, flexGrow: 1 },
  headerCard: { backgroundColor: "#fff", borderRadius: 12, borderWidth: 1, borderColor: colors.line, padding: 18, marginBottom: 20, alignItems: "center" },
  name: { fontSize: 20, fontWeight: "800", color: colors.ink },
  email: { fontSize: 13, color: colors.inkSoft, marginTop: 2 },
  role: { fontSize: 11, fontWeight: "700", color: colors.brand, marginTop: 8, textTransform: "uppercase" },
  label: { fontSize: 13, fontWeight: "700", color: colors.inkSoft, marginBottom: 6, marginTop: 14 },
  input: { backgroundColor: "#fff", borderWidth: 1, borderColor: colors.line, borderRadius: 8, padding: 14, fontSize: 16 },
  msg: { marginTop: 12, color: colors.brand, fontSize: 13 },
  button: { backgroundColor: colors.brand, borderRadius: 8, padding: 16, alignItems: "center", marginTop: 20 },
  buttonText: { color: "#fff", fontWeight: "700", fontSize: 16 },
  logoutButton: { borderRadius: 8, padding: 16, alignItems: "center", marginTop: 12, borderWidth: 1, borderColor: colors.rust },
  logoutText: { color: colors.rust, fontWeight: "700", fontSize: 16 },
  apiNote: { textAlign: "center", color: colors.inkSoft, fontSize: 11, marginTop: 24 },
});
