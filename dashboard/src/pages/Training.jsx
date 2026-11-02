import { useEffect, useState } from "react";
import Layout from "../components/Layout";
import { trainingApi } from "../services/resources";

export default function Training() {
  const [model, setModel] = useState(null);
  const [history, setHistory] = useState([]);
  const [images, setImages] = useState([]);

  useEffect(() => {
    trainingApi.currentModel().then((r) => setModel(r.data));
    trainingApi.history().then((r) => setHistory(r.data));
    trainingApi.images().then((r) => setImages(r.data));
  }, []);

  return (
    <Layout title="Dataset &amp; Training">
      <div className="card" style={{ marginBottom: 16 }}>
        <h2>Current deployed model</h2>
        {model?.deployed ? (
          <table>
            <tbody>
              <tr><th>Version</th><td>{model.version}</td></tr>
              {model.precision != null && <tr><th>Precision</th><td>{model.precision?.toFixed(3)}</td></tr>}
              {model.recall != null && <tr><th>Recall</th><td>{model.recall?.toFixed(3)}</td></tr>}
              {model.map50 != null && <tr><th>mAP50</th><td>{model.map50?.toFixed(3)}</td></tr>}
              {model.map5095 != null && <tr><th>mAP50-95</th><td>{model.map5095?.toFixed(3)}</td></tr>}
              {model.top1_accuracy != null && <tr><th>Top-1 accuracy</th><td>{(model.top1_accuracy * 100).toFixed(1)}%</td></tr>}
              {model.top5_accuracy != null && <tr><th>Top-5 accuracy</th><td>{(model.top5_accuracy * 100).toFixed(1)}%</td></tr>}
              {model.classes && <tr><th>Classes</th><td>{model.classes.join(", ")}</td></tr>}
              <tr><th>Trained</th><td>{new Date(model.trained_at).toLocaleString()}</td></tr>
            </tbody>
          </table>
        ) : (
          <p className="muted">
            No model has been trained and deployed yet. Use the annotation tool to
            label images, then run <code>training/train.py</code> and{" "}
            <code>training/export.py --deploy</code>. Numbers here are read directly
            from that real training run — nothing is invented.
          </p>
        )}
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <h2>Model version history</h2>
        <table>
          <thead><tr><th>Version</th><th>Precision</th><th>Recall</th><th>mAP50</th><th>Deployed</th><th>Trained</th></tr></thead>
          <tbody>
            {history.map((h) => (
              <tr key={h.version}>
                <td>{h.version}</td>
                <td>{h.precision?.toFixed(3) ?? "-"}</td>
                <td>{h.recall?.toFixed(3) ?? "-"}</td>
                <td>{h.map50?.toFixed(3) ?? "-"}</td>
                <td>{h.deployed ? "Yes" : "No"}</td>
                <td>{h.trained_at ? new Date(h.trained_at).toLocaleDateString() : "-"}</td>
              </tr>
            ))}
            {history.length === 0 && <tr><td colSpan={6} className="muted">No training runs recorded yet.</td></tr>}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h2>Verified training images ({images.length})</h2>
        <p className="muted">
          Only images explicitly marked "Add to training dataset" from a report's
          detail page appear here -- raw AI predictions never enter this list
          automatically.
        </p>
        <table>
          <thead><tr><th>Image</th><th>Class</th></tr></thead>
          <tbody>
            {images.map((i) => (
              <tr key={i.id}><td>{i.image_path.split("/").pop()}</td><td>{i.class_name}</td></tr>
            ))}
            {images.length === 0 && <tr><td colSpan={2} className="muted">None yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </Layout>
  );
}
