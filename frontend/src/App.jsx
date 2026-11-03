import { useEffect, useState } from "react";
import { api } from "./api";
import RequestForm from "./components/RequestForm";
import RequestCard from "./components/RequestCard";

export default function App() {
  const [requests, setRequests] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    api.listRequests().then(setRequests).catch((e) => setError(`Cannot reach the API: ${e.message}`));
  }, []);

  const replace = (updated) => setRequests(requests.map((r) => (r.id === updated.id ? updated : r)));

  return (
    <main>
      <header>
        <h1>Vehicle Search Agent</h1>
        <p className="muted">
          Tell us what vehicle you want: car, SUV, van, motorbike, three-wheeler and more. Every day our agents search
          the sites, email you the 10 best new ones, and tell you which earlier ones are still for sale or gone.
        </p>
      </header>

      <RequestForm onCreated={(r) => setRequests([r, ...requests])} />

      <h2>Your searches</h2>
      {error && <p className="error">{error}</p>}
      {!error && requests.length === 0 && <p className="muted">No searches yet.</p>}
      {requests.map((r) => (
        <RequestCard
          key={r.id}
          req={r}
          onChanged={replace}
          onDeleted={(id) => setRequests(requests.filter((x) => x.id !== id))}
        />
      ))}
    </main>
  );
}
