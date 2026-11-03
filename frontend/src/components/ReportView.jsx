const price = (p) => (p ? `Rs. ${p.toLocaleString()}` : "—");
const day = (iso) => (iso ? new Date(iso + "Z").toLocaleDateString() : "—");

function VehicleLink({ t }) {
  return (
    <>
      <a href={t.url} target="_blank" rel="noreferrer">
        {t.title}
      </a>
      <div className="muted small">{t.site}</div>
    </>
  );
}

function PriceChange({ change }) {
  if (!change) return null;
  return (
    <div className={`small ${change < 0 ? "down" : "up"}`}>
      {change < 0 ? "▼" : "▲"} Rs. {Math.abs(change).toLocaleString()} since sent
    </div>
  );
}

function NewTable({ items }) {
  if (!items.length) return <p className="muted">No new vehicles matched today.</p>;
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Vehicle</th>
            <th>Price</th>
            <th>Year</th>
            <th>Condition</th>
            <th>Value</th>
            <th>Why</th>
          </tr>
        </thead>
        <tbody>
          {items.map((t) => (
            <tr key={t.url}>
              <td>{t.rank}</td>
              <td>
                <VehicleLink t={t} />
              </td>
              <td>{price(t.price_lkr)}</td>
              <td>{t.year || "—"}</td>
              <td title={[...(t.highlights || []), ...(t.red_flags || []).map((f) => `⚠ ${f}`)].join("\n")}>
                {t.condition_score ?? "—"}/10
              </td>
              <td title={t.reasoning}>{t.value_score ?? "—"}/10</td>
              <td>{t.rank_reason}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function StillAvailableTable({ items }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Vehicle</th>
            <th>Price now</th>
            <th>Year</th>
            <th>First sent</th>
          </tr>
        </thead>
        <tbody>
          {items.map((t) => (
            <tr key={t.url}>
              <td>
                <VehicleLink t={t} />
              </td>
              <td>
                {price(t.price_lkr)}
                <PriceChange change={t.price_change} />
              </td>
              <td>{t.year || "—"}</td>
              <td>{day(t.sent_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function UnavailableTable({ items }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Vehicle</th>
            <th>Last price</th>
            <th>First sent</th>
          </tr>
        </thead>
        <tbody>
          {items.map((t) => (
            <tr key={t.url} className="gone">
              <td>
                <s>{t.title}</s>
                <div className="muted small">{t.site}</div>
              </td>
              <td>{price(t.price_lkr)}</td>
              <td>{day(t.sent_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function ReportView({ report }) {
  if (!report) return <p className="muted">No runs yet. It will run daily at the scheduled time, or press "Run now".</p>;

  const when = new Date(report.created_at + "Z").toLocaleString();

  if (report.status === "running") return <p className="muted">Running since {when}… (agents are scraping and analysing)</p>;
  if (report.status === "failed") return <p className="error">Run on {when} failed: {report.error}</p>;

  const still = report.still_available || [];
  const gone = report.unavailable || [];

  return (
    <div className="report">
      <p className="muted">
        Last run {when} · {report.listings_found} matching vehicles found
      </p>
      {report.error && <p className="error">Email not sent: {report.error}</p>}
      {report.summary && <p className="summary">{report.summary}</p>}

      <h4>New today ({report.top_listings.length})</h4>
      <NewTable items={report.top_listings} />

      {still.length > 0 && (
        <>
          <h4>Still available from earlier reports ({still.length})</h4>
          <StillAvailableTable items={still} />
        </>
      )}

      {gone.length > 0 && (
        <>
          <h4>No longer available ({gone.length})</h4>
          <UnavailableTable items={gone} />
        </>
      )}
    </div>
  );
}
