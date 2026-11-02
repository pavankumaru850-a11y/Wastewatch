import { useRef, useState } from "react";
import { View, Text, Pressable, StyleSheet, ActivityIndicator, ScrollView, Alert, TextInput } from "react-native";
import { CameraView, useCameraPermissions } from "expo-camera";
import * as Location from "expo-location";
import * as ImagePicker from "expo-image-picker";
import { File, Paths } from "expo-file-system";
import { useRouter } from "expo-router";
import { useRequireAuth } from "../services/useRequireAuth";
import { useNetworkSync } from "../services/useNetworkSync";
import { detectionApi, reportsApi } from "../services/resources";
import { enqueuePendingReport } from "../database/db";
import { describeDetection, formatReportId, isNetworkError, makeClientUuid, percent } from "../services/logic";
import type { DetectionResult } from "../services/logic";
import BoxedImage from "../components/BoxedImage";
import { colors } from "../constants/theme";

type Step = "camera" | "preview" | "detecting" | "result" | "submitting" | "done";
type Gps = "idle" | "searching" | "ok" | "denied" | "unavailable";
type Photo = { uri: string; width: number; height: number; fromGallery: boolean };

const SEV_COLOR: Record<string, string> = { LOW: "#2f8a4f", MEDIUM: "#c9a227", HIGH: "#d9772b", CRITICAL: "#b83a2a" };

export default function CameraScreen() {
  useRequireAuth();
  const router = useRouter();
  const { isOnline } = useNetworkSync();
  const [permission, requestPermission] = useCameraPermissions();
  const cameraRef = useRef<CameraView>(null);
  const clientUuid = useRef<string>(makeClientUuid());

  const [step, setStep] = useState<Step>("camera");
  const [photo, setPhoto] = useState<Photo | null>(null);
  const [location, setLocation] = useState<Location.LocationObject | null>(null);
  const [gps, setGps] = useState<Gps>("idle");
  const [result, setResult] = useState<DetectionResult | null>(null);
  const [errorText, setErrorText] = useState<string | null>(null);
  const [description, setDescription] = useState("");
  const [doneInfo, setDoneInfo] = useState<{ id: string | null; offline: boolean } | null>(null);

  if (!permission) return <View style={styles.center}><ActivityIndicator /></View>;
  if (!permission.granted) {
    return (
      <View style={styles.center}>
        <Text style={styles.permText}>Camera access is needed to report waste. You can also choose a photo from your gallery.</Text>
        <Pressable style={styles.button} onPress={requestPermission}><Text style={styles.buttonText}>Grant camera access</Text></Pressable>
        <Pressable style={styles.secondaryButton} onPress={pickFromGallery}><Text style={styles.secondaryButtonText}>Choose from gallery</Text></Pressable>
      </View>
    );
  }

  async function acquireLocation(): Promise<Location.LocationObject | null> {
    setGps("searching");
    try {
      const perm = await Location.requestForegroundPermissionsAsync();
      if (perm.status !== "granted") { setLocation(null); setGps("denied"); return null; }
      const loc = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.High });
      setLocation(loc);
      setGps("ok");
      return loc;
    } catch {
      setLocation(null);
      setGps("unavailable");
      return null;
    }
  }

  async function begin(p: Photo) {
    setPhoto(p);
    setResult(null);
    setErrorText(null);
    clientUuid.current = makeClientUuid();
    setStep("preview");
    await acquireLocation();
  }

  async function capture() {
    if (!cameraRef.current) return;
    try {
      const pic = await cameraRef.current.takePictureAsync({ quality: 0.7 });
      if (pic) await begin({ uri: pic.uri, width: pic.width, height: pic.height, fromGallery: false });
    } catch {
      Alert.alert("Could not take photo", "Please try again.");
    }
  }

  async function pickFromGallery() {
    try {
      const res = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ["images"], quality: 0.7 });
      const a = res.canceled ? null : res.assets[0];
      if (a) await begin({ uri: a.uri, width: a.width, height: a.height, fromGallery: true });
    } catch {
      Alert.alert("Could not open gallery", "Please check photo permissions and try again.");
    }
  }

  function retake() {
    setPhoto(null); setLocation(null); setGps("idle"); setResult(null); setErrorText(null); setStep("camera");
  }

  function buildForm(includeDescription: boolean) {
    const form = new FormData();
    form.append("image", { uri: photo!.uri, name: "capture.jpg", type: "image/jpeg" } as any);
    form.append("latitude", String(location!.coords.latitude));
    form.append("longitude", String(location!.coords.longitude));
    if (location!.coords.accuracy != null) form.append("gps_accuracy", String(location!.coords.accuracy));
    if (includeDescription) {
      if (description) form.append("description", description);
      form.append("client_uuid", clientUuid.current);
    }
    return form;
  }

  async function runDetection() {
    if (!photo || !location) return;
    setStep("detecting");
    setErrorText(null);
    try {
      const res = await detectionApi.predict(buildForm(false));
      setResult(res.data);
    } catch (err: any) {
      setResult(null);
      setErrorText(isNetworkError(err) ? "Could not reach the server. You can save this report and it will upload later." : err?.response?.data?.detail || "Something went wrong. Please try again.");
    }
    setStep("result");
  }

  async function saveOffline(): Promise<boolean> {
    try {
      // Copy into permanent storage -- the camera's temp file can be cleared by the OS.
      const dest = new File(Paths.document, `pending_${Date.now()}.jpg`);
      await new File(photo!.uri).copy(dest);
      await enqueuePendingReport({
        client_uuid: clientUuid.current,
        image_uri: dest.uri,
        latitude: location!.coords.latitude,
        longitude: location!.coords.longitude,
        accuracy: location!.coords.accuracy,
        description: description || null,
        village: null,
        district: null,
      });
      return true;
    } catch (err) {
      Alert.alert("Could not save report locally", "Please free some storage space and try again.");
      return false;
    }
  }

  async function submitOffline() {
    if (!photo || !location) return;
    setStep("submitting");
    const ok = await saveOffline();
    if (ok) { setDoneInfo({ id: null, offline: true }); setStep("done"); } else setStep(result || errorText ? "result" : "preview");
  }

  async function submitOnline() {
    if (!photo || !location) return;
    setStep("submitting");
    try {
      const res = await reportsApi.create(buildForm(true));
      setDoneInfo({ id: formatReportId(res.data.id), offline: false });
      setStep("done");
    } catch (err: any) {
      if (isNetworkError(err)) {
        // Connection dropped mid-submit: keep the report safely in the offline queue (same client_uuid => no duplicate).
        if (await saveOffline()) { setDoneInfo({ id: null, offline: true }); setStep("done"); return; }
      } else {
        Alert.alert("Could not submit", err?.response?.data?.detail || "Something went wrong. Please try again.");
      }
      setStep("result");
    }
  }

  if (step === "camera") {
    return (
      <View style={{ flex: 1 }}>
        <CameraView ref={cameraRef} style={{ flex: 1 }} facing="back" />
        <View style={styles.captureBar}>
          <Pressable style={styles.galleryButton} onPress={pickFromGallery} accessibilityLabel="Choose from gallery">
            <Text style={styles.galleryText}>Gallery</Text>
          </Pressable>
          <Pressable style={styles.captureButton} onPress={capture} accessibilityLabel="Take photo" />
          <View style={{ width: 74 }} />
        </View>
      </View>
    );
  }

  const verdict = result ? describeDetection(result) : null;
  const toneColor = verdict?.tone === "ok" ? colors.brand : verdict?.tone === "error" ? colors.rust : colors.clay;
  const boxes = (result?.detections || []).map((d) => ({ ...d.box, class_name: d.class_name, confidence: d.confidence }));
  const busy = step === "detecting" || step === "submitting";
  const canSubmit = !!location && (verdict ? verdict.canSubmit : true);

  return (
    <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">
      {photo && <BoxedImage uri={photo.uri} boxes={boxes} imgWidth={photo.width} imgHeight={photo.height} />}

      <View style={styles.infoCard}>
        <Text style={styles.infoLabel}>Location</Text>
        {gps === "searching" && <Text style={styles.infoValue}>Getting your location...</Text>}
        {gps === "ok" && location && (
          <Text style={styles.infoValue}>
            {location.coords.latitude.toFixed(5)}, {location.coords.longitude.toFixed(5)}  (±{Math.round(location.coords.accuracy || 0)} m)
          </Text>
        )}
        {(gps === "denied" || gps === "unavailable") && (
          <>
            <Text style={styles.warnText}>Location unavailable. {gps === "denied" ? "Allow location access in settings, then retry." : "Move to an open area and retry."}</Text>
            <Pressable style={styles.smallButton} onPress={acquireLocation}><Text style={styles.smallButtonText}>Retry GPS</Text></Pressable>
          </>
        )}
        {photo?.fromGallery && gps === "ok" && (
          <Text style={styles.note}>This is a gallery photo, so the location saved is where you are now. Only report waste from where you are standing.</Text>
        )}
      </View>

      {step === "result" && (verdict || errorText) && (
        <View style={[styles.infoCard, { borderColor: toneColor }]}>
          <Text style={styles.infoLabel}>AI Detection</Text>
          <Text style={[styles.verdict, { color: toneColor }]}>{verdict ? verdict.title : errorText}</Text>

          {result && verdict && result.detections.length > 0 && (
            <>
              {result.detections.map((d, i) => (
                <Text key={i} style={styles.infoValue}>{d.class_name} — Detection Confidence: {percent(d.confidence)}</Text>
              ))}
              <View style={styles.statRow}>
                <Stat label="Objects" value={String(result.object_count)} />
                <Stat label="Confidence" value={result.confidence_level || "-"} />
                <Stat label="Model" value={result.model_version || "-"} />
              </View>
              <View style={styles.statRow}>
                <View style={[styles.sevPill, { backgroundColor: SEV_COLOR[result.severity || ""] || colors.gray }]}>
                  <Text style={styles.sevText}>Severity: {result.severity || "-"}</Text>
                </View>
                <Text style={styles.infoValue}>Priority: {result.priority_score != null ? `${Math.round(result.priority_score)}/100` : "-"}</Text>
              </View>
            </>
          )}
        </View>
      )}

      {(step === "preview" || step === "result") && (
        <View style={styles.infoCard}>
          <Text style={styles.infoLabel}>Notes (optional)</Text>
          <TextInput value={description} onChangeText={setDescription} placeholder="e.g. near the bus stop" multiline style={styles.input} maxLength={500} />
        </View>
      )}

      {step === "done" && doneInfo ? (
        <View style={styles.infoCard}>
          <Text style={styles.doneTitle}>{doneInfo.offline ? "Report saved offline" : "Report submitted successfully"}</Text>
          <Text style={styles.infoValue}>
            {doneInfo.offline ? "Status: Pending Sync. It will upload automatically when you're back online." : `Report number: ${doneInfo.id}`}
          </Text>
          <Pressable style={styles.button} onPress={() => router.replace("/home")}><Text style={styles.buttonText}>Back to Home</Text></Pressable>
        </View>
      ) : (
        <View style={styles.actions}>
          <Pressable style={styles.secondaryButton} onPress={retake} disabled={busy}><Text style={styles.secondaryButtonText}>Retake</Text></Pressable>

          {step === "preview" && isOnline && (
            <Pressable style={[styles.button, !location && styles.disabled]} onPress={runDetection} disabled={!location}>
              <Text style={styles.buttonText}>Detect Waste</Text>
            </Pressable>
          )}
          {step === "preview" && !isOnline && (
            <Pressable style={[styles.button, !location && styles.disabled]} onPress={submitOffline} disabled={!location}>
              <Text style={styles.buttonText}>Save (Offline)</Text>
            </Pressable>
          )}
          {step === "result" && (
            <Pressable style={[styles.button, !canSubmit && styles.disabled]} onPress={isOnline ? submitOnline : submitOffline} disabled={!canSubmit}>
              <Text style={styles.buttonText}>{verdict?.isWaste === false ? (isOnline ? "Save Photo (Not Waste)" : "Save (Offline)") : isOnline ? "Confirm & Submit Report" : "Save (Offline)"}</Text>
            </Pressable>
          )}
          {step === "result" && errorText && !verdict && (
            <Pressable style={styles.secondaryButton} onPress={submitOffline} disabled={!location}>
              <Text style={styles.secondaryButtonText}>Save for later upload</Text>
            </Pressable>
          )}
          {busy && <ActivityIndicator style={{ marginTop: 8 }} color={colors.brand} />}
        </View>
      )}
    </ScrollView>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <View style={{ marginRight: 20, marginTop: 8 }}>
      <Text style={styles.statLabel}>{label}</Text>
      <Text style={styles.statValue}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { padding: 16, backgroundColor: colors.bg, flexGrow: 1 },
  center: { flex: 1, alignItems: "center", justifyContent: "center", padding: 24, backgroundColor: colors.bg },
  permText: { textAlign: "center", marginBottom: 16, color: colors.ink },
  captureBar: { position: "absolute", bottom: 40, left: 0, right: 0, flexDirection: "row", alignItems: "center", justifyContent: "space-around" },
  captureButton: { width: 74, height: 74, borderRadius: 37, backgroundColor: "#fff", borderWidth: 4, borderColor: colors.brand },
  galleryButton: { width: 74, height: 44, borderRadius: 22, backgroundColor: "rgba(0,0,0,0.55)", alignItems: "center", justifyContent: "center" },
  galleryText: { color: "#fff", fontWeight: "700" },
  infoCard: { backgroundColor: "#fff", borderRadius: 10, borderWidth: 1, borderColor: colors.line, padding: 14, marginTop: 14 },
  infoLabel: { fontSize: 12, fontWeight: "700", color: colors.inkSoft, marginBottom: 4 },
  infoValue: { fontSize: 15, color: colors.ink, marginBottom: 2 },
  verdict: { fontSize: 16, fontWeight: "800", marginBottom: 6 },
  note: { fontSize: 12, color: colors.inkSoft, marginTop: 6 },
  warnText: { color: colors.rust, fontSize: 14 },
  statRow: { flexDirection: "row", alignItems: "center", flexWrap: "wrap" },
  statLabel: { fontSize: 11, color: colors.inkSoft, fontWeight: "700", textTransform: "uppercase" },
  statValue: { fontSize: 15, color: colors.ink, fontWeight: "700" },
  sevPill: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 20, marginTop: 10, marginRight: 14 },
  sevText: { color: "#fff", fontWeight: "700", fontSize: 12 },
  input: { borderWidth: 1, borderColor: colors.line, borderRadius: 8, padding: 10, minHeight: 60, textAlignVertical: "top", color: colors.ink },
  actions: { marginTop: 16, marginBottom: 30 },
  button: { backgroundColor: colors.brand, borderRadius: 10, padding: 16, alignItems: "center", marginTop: 10 },
  buttonText: { color: "#fff", fontWeight: "700", fontSize: 16 },
  disabled: { opacity: 0.5 },
  smallButton: { alignSelf: "flex-start", marginTop: 8, backgroundColor: colors.brand, borderRadius: 8, paddingVertical: 8, paddingHorizontal: 14 },
  smallButtonText: { color: "#fff", fontWeight: "700" },
  secondaryButton: { backgroundColor: "#fff", borderWidth: 1, borderColor: colors.line, borderRadius: 10, padding: 16, alignItems: "center", marginTop: 10 },
  secondaryButtonText: { color: colors.ink, fontWeight: "700", fontSize: 16 },
  doneTitle: { fontSize: 17, fontWeight: "800", color: colors.brand, marginBottom: 6 },
});
