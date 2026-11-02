import { useEffect } from "react";
import { useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet.markercluster";
import "leaflet.markercluster/dist/MarkerCluster.css";
import "leaflet.markercluster/dist/MarkerCluster.Default.css";

const esc = (v) => String(v ?? "-").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

/**
 * Clustered circle markers. `items` = [{ id, lat, lng, color, popupHtml }].
 * popupHtml MUST be built with esc() -- report text comes from citizens.
 */
export default function ClusterLayer({ items }) {
  const map = useMap();
  useEffect(() => {
    const group = L.markerClusterGroup({ showCoverageOnHover: false, maxClusterRadius: 45 });
    items.forEach((it) => {
      const m = L.circleMarker([it.lat, it.lng], { radius: 9, color: it.color, fillColor: it.color, fillOpacity: 0.85, weight: 2 });
      m.bindPopup(it.popupHtml);
      group.addLayer(m);
    });
    map.addLayer(group);
    return () => { map.removeLayer(group); };
  }, [items, map]);
  return null;
}

export { esc };
