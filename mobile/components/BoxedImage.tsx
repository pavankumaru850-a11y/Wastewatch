import { useState } from "react";
import { View, Image, Text, StyleSheet, LayoutChangeEvent } from "react-native";
import { colors } from "../constants/theme";

export interface Box { x1: number; y1: number; x2: number; y2: number; class_name: string; confidence: number }

/**
 * Image with AI bounding boxes. Box coordinates are in ORIGINAL image pixels
 * (what the server saw); they are scaled to the displayed size. Pass
 * imgWidth/imgHeight when known (camera), otherwise the size is read on load.
 */
export default function BoxedImage({ uri, boxes, imgWidth, imgHeight }: { uri: string; boxes: Box[]; imgWidth?: number; imgHeight?: number }) {
  const [layoutW, setLayoutW] = useState(0);
  const [nat, setNat] = useState<{ w: number; h: number } | null>(imgWidth && imgHeight ? { w: imgWidth, h: imgHeight } : null);

  const onLayout = (e: LayoutChangeEvent) => setLayoutW(e.nativeEvent.layout.width);
  const scale = nat && layoutW ? layoutW / nat.w : 0;
  const height = nat && scale ? nat.h * scale : 220;

  return (
    <View onLayout={onLayout} style={{ width: "100%", height, borderRadius: 8, overflow: "hidden", backgroundColor: colors.line }}>
      <Image
        source={{ uri }}
        style={{ width: "100%", height: "100%" }}
        resizeMode="cover"
        onLoad={(e) => {
          const s = e.nativeEvent.source;
          if (!nat && s?.width && s?.height) setNat({ w: s.width, h: s.height });
        }}
      />
      {scale > 0 && boxes.map((b, i) => (
        <View key={i} pointerEvents="none" style={[styles.box, { left: b.x1 * scale, top: b.y1 * scale, width: (b.x2 - b.x1) * scale, height: (b.y2 - b.y1) * scale }]}>
          <Text style={styles.label} numberOfLines={1}>{b.class_name} {Math.round(b.confidence * 100)}%</Text>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  box: { position: "absolute", borderWidth: 2, borderColor: "#ffcc00" },
  label: { position: "absolute", top: 0, left: 0, backgroundColor: "#ffcc00", color: "#000", fontSize: 10, fontWeight: "700", paddingHorizontal: 3 },
});
