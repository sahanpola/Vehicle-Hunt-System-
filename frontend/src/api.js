const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function request(path, options = {}) {
  const res = await fetch(`${BASE}/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detail = Array.isArray(body.detail)
      ? body.detail.map((d) => `${d.loc.at(-1)}: ${d.msg}`).join(", ")
      : body.detail;
    throw new Error(detail || `Request failed (${res.status})`);
  }
  return res.status === 204 ? null : res.json();
}

export const api = {
  sites: () => request("/sites"),
  listRequests: (email) => request(`/requests${email ? `?email=${encodeURIComponent(email)}` : ""}`),
  createRequest: (data) => request("/requests", { method: "POST", body: JSON.stringify(data) }),
  updateRequest: (id, data) => request(`/requests/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteRequest: (id) => request(`/requests/${id}`, { method: "DELETE" }),
  runNow: (id) => request(`/requests/${id}/run`, { method: "POST" }),
  reports: (id) => request(`/requests/${id}/reports`),
};
