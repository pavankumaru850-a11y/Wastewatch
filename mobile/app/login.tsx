import { useState } from "react";
import { View, Text, TextInput, Pressable, StyleSheet, ActivityIndicator, Alert } from "react-native";
import { Link, useRouter } from "expo-router";
import { useAuth } from "../context/AuthContext";
import { colors } from "../constants/theme";
import { ApiNotConfiguredError } from "../services/api";

export default function Login() {
  const { login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function handleLogin() {
    setError("");
    setBusy(true);
    try {
      await login(email.trim(), password);
      router.replace("/home");
    } catch (err: any) {
      if (err instanceof ApiNotConfiguredError) {
        setError(err.message);
      } else {
        setError(err?.response?.data?.detail || "Login failed. Check your email and password.");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <View style={styles.container}>
      <Text style={styles.label}>Email</Text>
      <TextInput
        style={styles.input} autoCapitalize="none" keyboardType="email-address"
        value={email} onChangeText={setEmail} placeholder="you@example.com"
      />
      <Text style={styles.label}>Password</Text>
      <TextInput style={styles.input} secureTextEntry value={password} onChangeText={setPassword} />

      {!!error && <Text style={styles.error}>{error}</Text>}

      <Pressable style={styles.button} onPress={handleLogin} disabled={busy}>
        {busy ? <ActivityIndicator color="#fff" /> : <Text style={styles.buttonText}>Sign in</Text>}
      </Pressable>

      <Link href="/register" style={styles.link}>
        <Text>New here? Create an account</Text>
      </Link>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 24, backgroundColor: colors.bg, justifyContent: "center" },
  label: { fontSize: 13, fontWeight: "700", color: colors.inkSoft, marginBottom: 6, marginTop: 14 },
  input: { backgroundColor: "#fff", borderWidth: 1, borderColor: colors.line, borderRadius: 8, padding: 14, fontSize: 16 },
  button: { backgroundColor: colors.brand, borderRadius: 8, padding: 16, alignItems: "center", marginTop: 24 },
  buttonText: { color: "#fff", fontWeight: "700", fontSize: 16 },
  error: { color: colors.rust, marginTop: 12, fontSize: 13 },
  link: { marginTop: 20, alignSelf: "center" },
});
