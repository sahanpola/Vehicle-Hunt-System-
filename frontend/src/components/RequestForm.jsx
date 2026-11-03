import { useEffect, useState } from "react";
import { api } from "../api";

export default function RequestForm({ onCreated }) {
  const [presets, setPresets] = useState([]);
  const [form, setForm] = useState({ email: "", vehicle_query: "", scrape_time: "08:00" });
  const [sites, setSites] = useState([]);
  const [customSite, setCustomSite] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.sites().then(setPresets).catch(() => {});
  }, []);

  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });

  const toggleSite = (site) =>
    setSites(sites.includes(site) ? sites.filter((s) => s !== site) : [...sites, site]);

  const addCustomSite = () => {
    const site = customSite.trim();
    if (site && !sites.includes(site)) setSites([...sites, site]);
    setCustomSite("");
  };

  const submit = async (e) => {
    e.preventDefault();
    if (!sites.length) return setError("Pick at least one site.");
    setSaving(true);
    setError("");
    try {
      const created = await api.createRequest({ ...form, sites });
      setForm({ ...form, vehicle_query: "" });
      setSites([]);
      onCreated(created);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const allSites = [...new Set([...presets, ...sites])];

  return (
    <form className="card" onSubmit={submit}>
      <h2>New daily search</h2>

      <label>
        Vehicle you want
        <textarea
          rows={2}
          required
          placeholder="e.g. BMW 320d 2012–2016 automatic under 9 million, or Bajaj RE three-wheeler under 2M"
          value={form.vehicle_query}
          onChange={set("vehicle_query")}
        />
      </label>

      <div className="row">
        <label>
          Email for the daily report
          <input type="email" required value={form.email} onChange={set("email")} />
        </label>
        <label>
          Daily scraping time
          <input type="time" required value={form.scrape_time} onChange={set("scrape_time")} />
        </label>
      </div>

      <fieldset>
        <legend>Sites to search</legend>
        {allSites.map((site) => (
          <label key={site} className="check">
            <input type="checkbox" checked={sites.includes(site)} onChange={() => toggleSite(site)} />
            <span>{site}</span>
          </label>
        ))}
        <div className="row add-site">
          <input
            placeholder="Add another site URL"
            value={customSite}
            onChange={(e) => setCustomSite(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addCustomSite())}
          />
          <button type="button" className="secondary" onClick={addCustomSite}>
            Add
          </button>
        </div>
      </fieldset>

      {error && <p className="error">{error}</p>}
      <button type="submit" disabled={saving}>
        {saving ? "Saving…" : "Create search"}
      </button>
    </form>
  );
}
