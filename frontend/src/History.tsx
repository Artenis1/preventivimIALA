import { useEffect, useState } from "react";
import { Activity, History as HistoryIcon } from "lucide-react";
import { api } from "./api";
import { money, list } from "./utils";
import { ErrorBox, Loading, Empty, Field } from "./ui";
export default function History() {
  const [history, setHistory] = useState<any[]>([]),
    [audit, setAudit] = useState<any[]>([]),
    [loading, setLoading] = useState(true),
    [error, setError] = useState<unknown>(),
    [tab, setTab] = useState("prices"),
    [selected, setSelected] = useState("");
  useEffect(() => {
    Promise.all([api("/prices/history"), api("/audit")])
      .then(([h, a]) => {
        setHistory(list(h));
        setAudit(list(a));
      })
      .catch(setError)
      .finally(() => setLoading(false));
  }, []);
  const options = [
    ...new Map(
      history.map((h) => [
        h.item_id,
        { id: h.item_id, name: h.snapshot?.name || `Zëri ${h.item_id}` },
      ]),
    ).values(),
  ];
  const filtered = history.filter(
    (h) => !selected || String(h.item_id) === selected,
  );
  const trend = selected
    ? filtered
        .filter((h) => h.currency === filtered[0]?.currency)
        .slice(0, 20)
        .reverse()
    : [];
  const min = Math.min(...trend.map((h) => Number(h.new_price))),
    max = Math.max(...trend.map((h) => Number(h.new_price)));
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">GJURMUESHMËRI E PLOTË</span>
          <h1>Historiku i çmimeve</h1>
          <p>
            Krahasoni ndryshimet dhe ndiqni veprimet e dokumentuara të
            llogarisë.
          </p>
        </div>
      </div>
      <ErrorBox error={error} />
      <div className="history-tabs">
        <button
          className={tab === "prices" ? "" : "secondary"}
          onClick={() => setTab("prices")}
        >
          <Activity size={16} />
          Çmimet
        </button>
        <button
          className={tab === "audit" ? "" : "secondary"}
          onClick={() => setTab("audit")}
        >
          <HistoryIcon size={16} />
          Regjistri i auditimit
        </button>
      </div>
      {loading ? (
        <Loading />
      ) : tab === "prices" ? (
        <>
          <div className="panel history-filter">
            <Field label="Filtroni zërin dhe shihni ecurinë e çmimit">
              <select
                value={selected}
                onChange={(e) => setSelected(e.target.value)}
              >
                <option value="">Të gjithë zërat</option>
                {options.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.name}
                  </option>
                ))}
              </select>
            </Field>
            {trend.length > 1 && (
              <div className="trend-chart">
                <span>Çmimi për njësi · {trend[0].currency}</span>
                <svg
                  viewBox="0 0 600 110"
                  preserveAspectRatio="none"
                  role="img"
                  aria-label="Ecuria e çmimit të zërit"
                >
                  <path
                    d={`M ${trend.map((h, i) => `${10 + (i * 580) / (trend.length - 1)},${90 - ((Number(h.new_price) - min) / (max - min || 1)) * 70}`).join(" L ")}`}
                    fill="none"
                    stroke="#2a8b70"
                    strokeWidth="2"
                    vectorEffect="non-scaling-stroke"
                  />
                  {trend.map((h, i) => (
                    <circle
                      key={h.id}
                      cx={10 + (i * 580) / (trend.length - 1)}
                      cy={
                        90 -
                        ((Number(h.new_price) - min) / (max - min || 1)) * 70
                      }
                      r="3"
                      fill="#2a8b70"
                    >
                      <title>
                        {h.created_at?.slice(0, 10)}: {h.new_price} {h.currency}
                      </title>
                    </circle>
                  ))}
                </svg>
                <div>
                  <small>{trend[0].created_at?.slice(0, 10)}</small>
                  <small>
                    {trend[trend.length - 1].created_at?.slice(0, 10)}
                  </small>
                </div>
              </div>
            )}
          </div>
          <div className="panel">
            {!filtered.length ? (
              <Empty text="Nuk ka ndryshime të regjistruara." />
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Zëri / burimi</th>
                      <th>Çmimi i mëparshëm</th>
                      <th>Çmimi i ri</th>
                      <th>Njësia</th>
                      <th>Data / përdoruesi</th>
                      <th>Arsyeja</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map((h) => (
                      <tr key={h.id}>
                        <td>
                          <span className="code">{h.snapshot?.code}</span>
                          <strong>{h.snapshot?.name || h.item_id}</strong>
                          <span className="cell-sub">{h.supplier}</span>
                        </td>
                        <td className="numeric">
                          {money(h.old_price, h.currency)}
                        </td>
                        <td className="numeric">
                          {money(h.new_price, h.currency)}
                        </td>
                        <td>{h.unit}</td>
                        <td>
                          {h.created_at?.replace("T", " ").slice(0, 16)}
                          <span className="cell-sub">
                            Përdoruesi #{h.owner_id}
                          </span>
                        </td>
                        <td>{h.reason}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      ) : (
        <div className="panel">
          {!audit.length ? (
            <Empty text="Asnjë veprim i regjistruar." />
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Veprimi</th>
                    <th>Objekti</th>
                    <th>Data / përdoruesi</th>
                    <th>Detaje</th>
                  </tr>
                </thead>
                <tbody>
                  {audit.map((a) => (
                    <tr key={a.id}>
                      <td>
                        <strong>{a.action}</strong>
                      </td>
                      <td>
                        {a.entity} #{a.entity_id}
                      </td>
                      <td>
                        {a.created_at?.replace("T", " ").slice(0, 16)}
                        <span className="cell-sub">
                          Përdoruesi #{a.owner_id}
                        </span>
                      </td>
                      <td>
                        <details>
                          <summary>Shih ndryshimin</summary>
                          <pre>{JSON.stringify(a.details, null, 2)}</pre>
                        </details>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </>
  );
}
