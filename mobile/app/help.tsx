import { ScrollView, Text, View, StyleSheet } from "react-native";
import { colors } from "../constants/theme";

const SECTIONS: Array<[string, string]> = [
  ["How to report waste", "Tap 'Detect Roadside Waste', photograph the waste (or choose a photo from the gallery), wait for your location, tap 'Detect Waste', check the result and tap 'Confirm & Submit Report'."],
  ["Good photos", "Stand a few metres back, keep the waste in the centre, use daylight and hold still. Very blurry, dark or tiny photos are rejected with 'Image quality is too low'."],
  ["What the AI result means", "The AI draws a yellow box around each item it finds and shows a confidence percentage. HIGH is 75% or more, MEDIUM 50-74%, LOW below 50%. The AI can be wrong: staff always review reports before action."],
  ["Severity and priority", "Severity (Low, Medium, High, Critical) reflects how much waste was found and what kind. Priority (0-100) helps the municipality decide what to clean first."],
  ["No internet?", "You can still take a photo and save the report. It shows as 'Pending Sync' and uploads automatically when you are back online. If an upload fails you will see 'Sync Failed' and can retry from Pending Uploads. Nothing is deleted until the server confirms it."],
  ["Location (GPS)", "Location is recorded so staff can find the waste. If it says 'Location unavailable', allow location access and tap 'Retry GPS'. For gallery photos the saved location is where you are right now."],
  ["Duplicates", "If someone already reported the same waste, your report may be flagged as a possible duplicate. It is kept and reviewed by staff, not deleted."],
  ["Report progress", "Open 'My Reports' to follow each step: review, verification, assignment, cleanup and closure. You will get a notification at each major step."],
];

export default function Help() {
  return (
    <ScrollView style={{ backgroundColor: colors.bg }} contentContainerStyle={{ padding: 16 }}>
      {SECTIONS.map(([title, body]) => (
        <View key={title} style={styles.card}>
          <Text style={styles.title}>{title}</Text>
          <Text style={styles.body}>{body}</Text>
        </View>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  card: { backgroundColor: "#fff", borderRadius: 10, borderWidth: 1, borderColor: colors.line, padding: 14, marginBottom: 10 },
  title: { fontWeight: "800", color: colors.ink, marginBottom: 4 },
  body: { color: colors.inkSoft, lineHeight: 20 },
});
