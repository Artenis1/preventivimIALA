import { useEffect, useState } from "react";
import {
  FolderOpen,
  Calculator,
  ScanSearch,
  Database,
  ArrowUpRight,
  FileUp,
  Activity,
  Clock3,
} from "lucide-react";
import { api } from "./api";
import type { Page } from "./types";
import { money, number, list } from "./utils";
import { ErrorBox, Loading, Empty, Badge } from "./ui";
export default function Dashboard({
  onNavigate,
}: {
  onNavigate: (p: Page) => void;
}) {
  const [data, setData] = useState<any>(),
    [projects, setProjects] = useState<any[]>([]),
    [error, setError] = useState<unknown>();
  useEffect(() => {
    Promise.all([api("/dashboard"), api("/projects")])
      .then(([d, p]) => {
        setData(d);
        setProjects(list(p));
      })
      .catch(setError);
  }, []);
  if (error) return <ErrorBox error={error} />;
  if (!data) return <Loading />;
  const stats = [
    {
      label: "Projekte gjithsej",
      value: data.total_projects,
      icon: FolderOpen,
      foot: `${data.finalized_estimates} preventiva të finalizuar`,
      page: "projects",
    },
    {
      label: "Preventiva në punë",
      value: data.draft_estimates,
      icon: Calculator,
      foot: "Projekte në fazën e përgatitjes",
      page: "estimates",
    },
    {
      label: "Në pritje të miratimit",
      value: data.awaiting_approval,
      icon: ScanSearch,
      foot: `${data.unmatched_rows} zëra pa përputhje`,
      page: "review",
    },
    {
      label: "Zëra në bazën e çmimeve",
      value: data.total_prices,
      icon: Database,
      foot: "Katalogu aktiv i llogarisë suaj",
      page: "prices",
    },
  ];
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">KONTROLLI I PROJEKTEVE</span>
          <h1>Përmbledhja e punës</h1>
          <p>
            Një pamje e qartë e çmimeve, projekteve dhe vendimeve që presin.
          </p>
        </div>
        <button onClick={() => onNavigate("import")}>
          <FileUp size={17} />
          Importo BOQ
        </button>
      </div>
      <div className="welcome-banner">
        <div>
          <span className="eyebrow">
            VLERËSIM INTELIGJENT, MIRATIM NJERËZOR
          </span>
          <h2>Nga përshkrimi te preventivi i verifikuar.</h2>
          <p>
            Importoni sasitë, gjeni çmimet dhe kontrolloni çdo ndryshim teknik.
          </p>
          <button onClick={() => onNavigate("projects")}>
            Hap projektet
            <ArrowUpRight size={16} />
          </button>
        </div>
        <div className="engineering-art" aria-hidden="true">
          <div className="art-grid" />
          <svg viewBox="0 0 300 170">
            <path
              d="M24 130 125 78 264 118 158 166Z M24 130V60L125 8V78 M125 8 264 48V118 M24 60 158 99 264 48 M158 99V166 M74 34 211 74 M74 104 211 144 M74 34V104 M211 74V144"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.2"
            />
            <path
              d="m24 60 134 39 106-51-139-40Z"
              fill="currentColor"
              opacity=".09"
            />
          </svg>
          <span>SAKTËSI NË ÇDO ZË.</span>
        </div>
      </div>
      <div className="stats-grid">
        {stats.map((s) => (
          <button
            className="stat-card"
            key={s.label}
            onClick={() => onNavigate(s.page as Page)}
          >
            <div>
              <span>{s.label}</span>
              <s.icon size={18} />
            </div>
            <b>{number(s.value ?? 0)}</b>
            <small>{s.foot}</small>
          </button>
        ))}
      </div>
      <div className="dashboard-grid">
        <section className="panel">
          <div className="section-heading dashboard-panel-heading">
            <div>
              <span className="eyebrow">PORTOFOLI</span>
              <h2>Projektet e fundit</h2>
            </div>
            <button
              className="text-button"
              onClick={() => onNavigate("projects")}
            >
              Shih të gjitha
              <ArrowUpRight size={13} />
            </button>
          </div>
          {!projects.length ? (
            <Empty text="Krijoni projektin e parë për të nisur vlerësimin." />
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Projekti</th>
                    <th>Monedha</th>
                    <th>Statusi</th>
                  </tr>
                </thead>
                <tbody>
                  {projects.slice(0, 5).map((p) => (
                    <tr key={p.id}>
                      <td>
                        <strong>{p.name}</strong>
                        <span className="cell-sub">
                          {p.client} · {p.location}
                        </span>
                      </td>
                      <td>{p.currency}</td>
                      <td>
                        <Badge status={p.status} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
        <section className="panel portfolio-value">
          <span className="eyebrow">VLERA E PREVENTIVAVE</span>
          <h2>Portofoli financiar</h2>
          <p>Totale të ndara sipas monedhës</p>
          {Object.entries(data.total_values || {}).map(([currency, value]) => (
            <div key={currency}>
              <span>{currency}</span>
              <b>{money(value, currency)}</b>
            </div>
          ))}
          <small>
            Draftet mund të përmbajnë zëra ende të pamiratuar. Monedhat nuk
            mblidhen pa kurs këmbimi.
          </small>
        </section>
        <section className="panel">
          <div className="section-heading dashboard-panel-heading">
            <div>
              <span className="eyebrow">AKTIVITETI I KATALOGUT</span>
              <h2>Ndryshimet e fundit të çmimeve</h2>
            </div>
            <button
              className="text-button"
              onClick={() => onNavigate("history")}
            >
              Historiku
              <ArrowUpRight size={13} />
            </button>
          </div>
          {!data.recent_prices?.length ? (
            <Empty text="Përditësimet e çmimeve do të shfaqen këtu." />
          ) : (
            <div className="activity-list">
              {data.recent_prices.slice(0, 5).map((p: any) => (
                <div key={p.id}>
                  <span className="activity-symbol">
                    <Activity size={16} />
                  </span>
                  <div>
                    <strong>{p.snapshot?.name || `Zëri #${p.item_id}`}</strong>
                    <small>
                      {p.reason} · {p.created_at?.slice(0, 10)}
                    </small>
                  </div>
                  <span>
                    {money(p.old_price, p.currency)}
                    <ArrowUpRight size={12} />
                    <b>{money(p.new_price, p.currency)}</b>
                  </span>
                </div>
              ))}
            </div>
          )}
        </section>
        <section className="panel frequent-panel">
          <span className="eyebrow">BURIMET E PËRDORURA</span>
          <h2>Zërat më të përdorur</h2>
          {!data.frequently_used?.length ? (
            <Empty text="Zërat shfaqen pas miratimit në projekte." />
          ) : (
            <div className="frequent-list">
              {data.frequently_used.map((p: any, i: number) => (
                <div key={p.item_id}>
                  <span>{String(i + 1).padStart(2, "0")}</span>
                  <div>
                    <b>{p.name}</b>
                    <i
                      style={{
                        width: `${Math.max(5, (p.count / (data.frequently_used[0]?.count || 1)) * 100)}%`,
                      }}
                    />
                  </div>
                  <small>{p.count}</small>
                </div>
              ))}
            </div>
          )}
          <div className="insight">
            <Clock3 size={16} />
            <span>Historiku ruan arsyen dhe datën e çdo vendimi.</span>
          </div>
        </section>
      </div>
    </>
  );
}
