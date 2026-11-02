import { useState } from "react";
import { View, Text, TextInput, Pressable, StyleSheet, ActivityIndicator, ScrollView } from "react-native";
import { useRouter } from "expo-router";
import { useAuth } from "../context/AuthContext";
import { colors } from "../constants/theme";

export default function Register() {
  const { register } = useAuth();
  const router = useRouter();
  const [form, setForm] = useState({ name: "", email: "", password: "", phone: "", village: "", district: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  function set(key: string, value: string) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function handleRegister() {
    setError("");
    if (!form.name || !form.email || !form.password) {
      setError("Name, email, and password are required.");
      return;
    }
    setBusy(true);
    try {
      await register(form);
      router.replace("/home");
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Could not create account.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text style={styles.label}>Full name</Text>
      <TextInput style={styles.input} value={form.name} onChangeText={(v) => set("name", v)} />

      <Text style={styles.label}>Email</Text>
      <TextInput style={styles.input} autoCapitalize="none" keyboardType="email-address" value={form.email} onChangeText={(v) => set("email", v)} />

      <Text style={styles.label}>Password</Text>
      <TextInput style={styles.input} secureTextEntry value={form.password} onChangeText={(v) => set("password", v)} />

      <Text style={styles.label}>Phone (optional)</Text>
      <TextInput style={styles.input} keyboardType="phone-pad" value={form.phone} onChangeText={(v) => set("phone", v)} />

      <Text style={styles.label}>Village (optional)</Text>
      <TextInput style={styles.input} value={form.village} onChangeText={(v) => set("village", v)} />

      <Text style={styles.label}>District (optional)</Text>
      <TextInput style={styles.input} value={form.district} onChangeText={(v) => set("district", v)} />

      {!!error && <Text style={styles.error}>{error}</Text>}

      <Pressable style={styles.button} onPress={handleRegister} disabled={busy}>
        {busy ? <ActivityIndicator color="#fff" /> : <Text style={styles.buttonText}>Create account</Text>}
      </Pressable>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { padding: 24, backgroundColor: colors.bg, flexGrow: 1 },
  label: { fontSize: 13, fontWeight: "700", color: colors.inkSoft, marginBottom: 6, marginTop: 14 },
  input: { backgroundColor: "#fff", borderWidth: 1, borderColor: colors.line, borderRadius: 8, padding: 14, fontSize: 16 },
  button: { backgroundColor: colors.brand, borderRadius: 8, padding: 16, alignItems: "center", marginTop: 24, marginBottom: 40 },
  buttonText: { color: "#fff", fontWeight: "700", fontSize: 16 },
  error: { color: colors.rust, marginTop: 12, fontSize: 13 },
});
