import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import ReportView from "./ReportView";

export default function RequestCard({ req, onChanged, onDeleted }) {
  const [reports, setReports] = useState([]);
  const [error, setError] = useState("");
  const latest = reports[0];

  const loadReports = useCallback(() => api.reports(req.id).then(setReports).catch((e) => setError(e.message)), [req.id]);

  useEffect(() => {
    loadReports();
  }, [loadReports]);

  // Poll while a run is in progress.
  useEffect(() => {
    if (latest?.status !== "running") return;
    const t = setInterval(loadReports, 4000);
    return () => clearInterval(t);
  }, [latest?.status, loadReports]);

  const runNow = async () => {
    await api.runNow(req.id);
    setTimeout(loadReports, 500);
  };

  const toggleActive = async () => onChanged(await api.updateRequest(req.id, { active: !req.active }));

  const remove = async () => {
    if (!confirm("Delete this search and its reports?")) return;
    await api.deleteRequest(req.id);
    onDeleted(req.id);
  };

  return (
    <div className="card">
      <div className="card-head">
        <div>
          <h3>{req.vehicle_query}</h3>
          <p className="muted small">
            {req.email} · daily at {req.scrape_time} · {req.active ? "active" : "paused"}
          </p>
          <p className="muted small">{req.sites.join(" · ")}</p>
        </div>
        <div className="actions">
          <button onClick={runNow} disabled={latest?.status === "running"}>
            Run now
          </button>
          <button className="secondary" onClick={toggleActive}>
            {req.active ? "Pause" : "Resume"}
          </button>
          <button className="danger" onClick={remove}>
            Delete
          </button>
        </div>
      </div>
      {error ? <p className="error">{error}</p> : <ReportView report={latest} />}
    </div>
  );
}
