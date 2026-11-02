import { View, Text, StyleSheet } from "react-native";
import { statusColor } from "../constants/theme";

export default function StatusPill({ status }: { status: string }) {
  const color = statusColor[status] || "#6b7280";
  return (
    <View style={[styles.pill, { backgroundColor: color }]}>
      <Text style={styles.text}>{status.replaceAll("_", " ")}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  pill: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 20, alignSelf: "flex-start" },
  text: { color: "#fff", fontSize: 12, fontWeight: "700" },
});
