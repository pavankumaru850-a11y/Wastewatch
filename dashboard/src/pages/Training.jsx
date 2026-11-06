import { useEffect, useState } from "react";
import Layout from "../components/Layout";
import { errText } from "../components/ui";
import { trainingApi } from "../services/resources";

export default function Training() {
  const [model, setModel] = useState(null);
  const [history, setHistory] = useState([]);
  const [dataset, setDataset] = useState(null);
  const [datasetError, setDatasetError] = useState("");
  const [images, setImages] = useState([]);

  useEffect(() => {
    trainingApi.currentModel().then((r) => setModel(r.data));
    trainingApi.history().then((r) => setHistory(r.data));
    trainingApi.dataset().then((r) => setDataset(r.data)).catch((e) => setDatasetError(errText(e)));
    trainingApi.images().then((r) => setImages(r.data));
  }, []);

  const datasetClasses = dataset?.available
    ? [...new Set([
      ...Object.keys(dataset.source.classes),
      ...Object.values(dataset.splits).flatMap((split) => Object.keys(split.classes)),
    ])]
    : [];

  return (
    <Layout title="Dataset &amp; Training">
      <div className="card" style={{ marginBottom: 16 }}>
        <h2>Training dataset</h2>
        {datasetError ? (
          <p role="alert" className="error-text">{datasetError}</p>
        ) : !dataset ? (
          <p className="muted">Loading dataset summary...</p>
        ) : !dataset.available ? (
          <p className="muted">Training dataset files are not available to the backend.</p>
        ) : (
          <>
            <h3 style={{ marginTop: 12 }}>Combined source: {dataset.source.total} images</h3>
            <p className="muted">
              {Object.entries(dataset.source.classes).map(([name, count]) => `${name}: ${count}`).join(" · ") || "No source images found."}
            </p>
            <h3 style={{ marginTop: 16 }}>Train / validation / test split</h3>
            <table>
              <thead>
                <tr>
                  <th>Split</th>
                  {datasetClasses.map((className) => <th key={className}>{className}</th>)}
                  <th>Total</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(dataset.splits).map(([split, summary]) => (
                  <tr key={split}>
                    <td>{split}</td>
                    {datasetClasses.map((className) => <td key={className}>{summary.classes[className] ?? 0}</td>)}
                    <td>{summary.total}</td>
                  </tr>
                ))}
                <tr>
                  <th>Total</th>
                  {datasetClasses.map((className) => (
                    <th key={className}>{Object.values(dataset.splits).reduce((total, split) => total + (split.classes[className] ?? 0), 0)}</th>
                  ))}
                  <th>{Object.values(dataset.splits).reduce((total, split) => total + split.total, 0)}</th>
                </tr>
              </tbody>
            </table>
          </>
        )}
      </div>

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
