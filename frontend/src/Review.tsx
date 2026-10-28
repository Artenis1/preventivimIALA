import { useEffect, useState } from "react";
import {
  Sparkles,
  CheckCheck,
  Download,
  Filter,
  Pencil,
  RotateCcw,
  LockKeyhole,
  FileUp,
  RefreshCw,
  GitCompareArrows,
  Settings2,
} from "lucide-react";
import { api, send, download } from "./api";
import type { Price, Project, BoqRow, Page } from "./types";
import { money, number, list } from "./utils";
import { Field, ErrorBox, Loading, Empty, Badge, Modal, Confirm } from "./ui";
import { ProjectForm } from "./Projects";
import { PriceForm, newPrice } from "./Prices";
export default function Review({
  projectId,
  mode,
  onProject,
  onNavigate,
}: {
  projectId: number | null;
  mode: Page;
  onProject: (id: number) => void;
  onNavigate: (page: Page) => void;
}) {
  const [projects, setProjects] = useState<Project[]>([]),
    [selected, setSelected] = useState<number | null>(projectId),
    [data, setData] = useState<any>(),
    [prices, setPrices] = useState<Price[]>([]),
    [loading, setLoading] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>(),
    [filter, setFilter] = useState("all"),
    [edit, setEdit] = useState<BoqRow | null>(null),
    [confirm, setConfirm] = useState<{
      title: string;
      detail: string;
      action: () => Promise<void>;
    } | null>(null),
    [message, setMessage] = useState(""),
    [settings, setSettings] = useState(false),
    [compare, setCompare] = useState(false),
    [originalExport, setOriginalExport] = useState(false);
  useEffect(() => {
    Promise.all([api("/projects"), api("/prices")])
      .then(([p, i]) => {
        setProjects(list<Project>(p));
        setPrices(list<Price>(i));
      })
      .catch(setError);
  }, []);
  const load = async () => {
    if (!selected) return;
    setLoading(true);
    try {
      setData(await api(`/projects/${selected}`));
    } catch (e) {
      setError(e);
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    setData(undefined);
    load();
  }, [selected]);
  const project: Project | undefined =
    data?.project ?? (data?.name ? data : undefined);
  const rows: BoqRow[] = data?.rows || [];
  const totals = data?.totals || {};
  const versions = data?.versions || [];
  const filtered = rows.filter(
    (r) =>
      filter === "all" ||
      (filter === "unresolved" && r.decision !== "approved") ||
      r.decision === filter,
  );
  const finalized = project?.status === "finalized";
  const action = async (fn: () => Promise<any>, success: string) => {
    setBusy(true);
    setError(undefined);
    try {
      await fn();
      setMessage(success);
      await load();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };
  const prompt = (
    title: string,
    detail: string,
    fn: () => Promise<any>,
    success: string,
  ) =>
    setConfirm({
      title,
      detail,
      action: async () => {
        await fn();
        setMessage(success);
        await load();
      },
    });
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">
            {mode === "estimates"
              ? "LLOGARITJE & VERSIONE"
              : "KONTROLLI INXHINIERIK"}
          </span>
          <h1>
            {mode === "estimates"
              ? "Preventivi i projektit"
              : "Rishikimi i përputhjeve"}
          </h1>
          <p>
            Përputhja më e mirë miratohet automatikisht. Kontrolloni besimin,
            fushën e punës dhe njësitë.
          </p>
        </div>
        {project && <Badge status={project.status || "draft"} />}
      </div>
      <div className="panel project-selector">
        <Field label="Projekti aktiv">
          <select
            value={selected || ""}
            onChange={(e) => {
              const id = Number(e.target.value);
              setSelected(id);
              onProject(id);
              setMessage("");
            }}
          >
            <option value="">Zgjidhni projektin…</option>
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} · {p.currency}
              </option>
            ))}
          </select>
        </Field>
        {project && (
          <div className="project-selector-meta">
            <span>{project.client}</span>
            <span>{project.location}</span>
            <button
              className="secondary"
              disabled={finalized}
              onClick={() => setSettings(true)}
            >
              <Settings2 size={16} />
              Cilësimet
            </button>
          </div>
        )}
      </div>
      <ErrorBox error={error} />
      {message && <div className="notice">{message}</div>}
      {loading ? (
        <Loading />
      ) : !selected ? (
        <Empty text="Zgjidhni projektin që dëshironi të rishikoni." />
      ) : (
        project && (
          <>
            <div className="review-actions">
              <div>
                <button
                  disabled={busy || finalized || !rows.length}
                  onClick={() =>
                    action(
                      () => send(`/projects/${selected}/match`, "POST"),
                      "Përputhjet më të mira u miratuan automatikisht. Kontrolloni besimin dhe paralajmërimet.",
                    )
                  }
                >
                  <Sparkles size={16} />
                  {busy ? "Duke përpunuar…" : "Gjej përputhjet"}
                </button>
                <button
                  className="secondary"
                  disabled={busy || finalized || !rows.length}
                  onClick={async () => {
                    try {
                      const preview = await api(
                        `/projects/${selected}/approve-preview`,
                      );
                      const ids =
                        preview.row_ids ||
                        preview.rows?.map((r: any) => r.id) ||
                        [];
                      if (!ids.length) {
                        setMessage(
                          "Nuk ka përputhje në pritje që mund të miratohen në grup.",
                        );
                        return;
                      }
                      prompt(
                        "Mirato përputhjet më të mira?",
                        `${ids.length} rreshta do të miratohen. Kontrolloni përputhshmërinë teknike: besimi i modelit nuk është garanci saktësie. ${preview.warnings?.join(" ") || ""}\n\n${(preview.rows || []).map((r: any) => `${r.item_number} · ${r.description} → ${prices.find((p) => p.id === r.match_result?.suggested_item_id)?.code || ""} · ${number(Number(r.match_result?.confidence || 0) * 100)}%`).join("\n")}`,
                        () =>
                          send(`/projects/${selected}/approve-bulk`, "POST", {
                            row_ids: ids,
                            confirm: true,
                          }),
                        "Rreshtat e zgjedhur u miratuan.",
                      );
                    } catch (e) {
                      setError(e);
                    }
                  }}
                >
                  <CheckCheck size={16} />
                  Mirato në grup
                </button>
                <button
                  className="secondary"
                  disabled={busy || finalized}
                  onClick={() => onNavigate("import")}
                >
                  <FileUp size={16} />
                  Importo
                </button>
              </div>
              <div>
                <button
                  className="secondary"
                  onClick={() =>
                    download(
                      `/projects/${selected}/export?format=standard`,
                      `${project.name}-preventiv.xlsx`,
                    ).catch(setError)
                  }
                >
                  <Download size={16} />
                  Excel standard
                </button>
                <button
                  className="secondary"
                  onClick={() => setOriginalExport(true)}
                >
                  Formati origjinal
                </button>
              </div>
            </div>
            {finalized && (
              <div className="notice">
                <LockKeyhole size={16} /> Preventivi është finalizuar. Çmimet
                dhe vendimet ruhen në këtë version. Rihapeni për të bërë
                ndryshime.
              </div>
            )}
            <div className="panel">
              <div className="toolbar">
                <span className="table-title">
                  Zërat e preventivit <small>{rows.length} zëra</small>
                </span>
                <div className="filter-tabs">
                  {[
                    ["all", "Të gjithë"],
                    ["unresolved", "Të pazgjidhur"],
                    ["approved", "Miratuar"],
                    ["rejected", "Refuzuar"],
                  ].map(([v, t]) => (
                    <button
                      key={v}
                      className={filter === v ? "active" : ""}
                      onClick={() => setFilter(v)}
                    >
                      {v === "unresolved" && <Filter size={12} />} {t}
                    </button>
                  ))}
                </div>
              </div>
              {!rows.length ? (
                <Empty
                  text="Importoni një BOQ Excel për të filluar."
                  action={
                    <button onClick={() => onNavigate("import")}>
                      Importo BOQ
                    </button>
                  }
                />
              ) : !filtered.length ? (
                <Empty text="Nuk ka rreshta për këtë filtër." />
              ) : (
                <div className="table-wrap">
                  <table className="review-table">
                    <thead>
                      <tr>
                        <th>Nr.</th>
                        <th>Përshkrimi origjinal / përputhja</th>
                        <th>Njësia</th>
                        <th>Sasia</th>
                        <th>Çmimi / njësi</th>
                        <th>Vlera</th>
                        <th>Statusi</th>
                        <th />
                      </tr>
                    </thead>
                    <tbody>
                      {filtered.map((r) => {
                        const match = r.match_result || {};
                        const item =
                          r.decision === "approved" && r.price_snapshot
                            ? r.price_snapshot
                            : prices.find(
                                (p) =>
                                  p.id ===
                                  (r.item_id || match.suggested_item_id),
                              );
                        return (
                          <tr key={r.id}>
                            <td className="code">{r.item_number}</td>
                            <td>
                              <strong>{r.description}</strong>
                              {item ? (
                                <span className="match-item">
                                  ↳ {item.code} · {item.name}
                                </span>
                              ) : (
                                <span className="cell-sub">
                                  {match.explanation ||
                                    "Pa përputhje të zgjedhur"}
                                </span>
                              )}
                              {match.discrepancies?.length > 0 && (
                                <span className="warning-text">
                                  {match.discrepancies.join(" · ")}
                                </span>
                              )}
                            </td>
                            <td>{r.unit}</td>
                            <td className="numeric">{number(r.quantity)}</td>
                            <td className="numeric">
                              {money(r.unit_price, project.currency)}
                              {r.original_unit_price !== null &&
                                r.original_unit_price !== r.unit_price && (
                                  <span className="cell-sub">
                                    Origjinal:{" "}
                                    {money(
                                      r.original_unit_price,
                                      project.currency,
                                    )}
                                  </span>
                                )}
                            </td>
                            <td className="numeric">
                              {money(r.total, project.currency)}
                            </td>
                            <td>
                              <Badge status={r.decision || "pending"} />
                              {match.classification && (
                                <span className="cell-sub">
                                  <Badge status={match.classification} />{" "}
                                  {number(Number(match.confidence || 0) * 100)}%
                                </span>
                              )}
                            </td>
                            <td>
                              <button
                                className="icon-button"
                                title="Rishiko zërin"
                                aria-label={`Rishiko zërin ${r.item_number}`}
                                onClick={() => setEdit(r)}
                              >
                                <Pencil size={17} />
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
              <div className="table-footer">
                Kandidati me përqindjen më të lartë miratohet automatikisht,
                edhe kur besimi është i ulët. Kontrolloni përqindjen dhe
                paralajmërimet.
              </div>
            </div>
            <div className="estimate-bottom">
              <div className="panel calculation-info">
                <span className="eyebrow">RREGULLAT E LLOGARITJES</span>
                <h3>Çmime me gjurmë të plota</h3>
                <p>
                  Sasia × çmimi neto → nëntotali → shpenzime → shtesë fitimi →
                  zbritje → tarifa → TVSH. Kostot përbërëse nuk shtohen dy herë.
                </p>
                <dl>
                  <div>
                    <dt>Baza e shpenzimeve / fitimit</dt>
                    <dd>
                      {project.calculation_base === "direct"
                        ? "Nëntotali neto"
                        : "Nëntotali neto + shpenzime"}
                    </dd>
                  </div>
                  <div>
                    <dt>Shpenzime të përgjithshme</dt>
                    <dd>{project.overhead_percent}%</dd>
                  </div>
                  <div>
                    <dt>Fitim / zbritje</dt>
                    <dd>
                      {project.profit_percent}% / {project.discount_percent}%
                    </dd>
                  </div>
                </dl>
                {totals.warnings?.length > 0 && (
                  <div className="notice">{totals.warnings.join(" · ")}</div>
                )}
                <div className="version-actions">
                  <button
                    className="secondary"
                    onClick={() => setCompare(true)}
                  >
                    <GitCompareArrows size={15} />
                    Krahaso versionet
                  </button>
                  <button
                    className="secondary"
                    disabled={finalized}
                    onClick={async () => {
                      try {
                        const preview = await send(
                          `/projects/${selected}/refresh-prices`,
                          "POST",
                          { confirm: false },
                        );
                        prompt(
                          "Përditëso çmimet nga katalogu?",
                          preview.differences
                            .map(
                              (d: any) =>
                                `Zëri #${d.row_id}: ${d.old_price} → ${d.new_price} ${project.currency}`,
                            )
                            .join(" · ") || "Nuk ka çmime për të rifreskuar.",
                          () =>
                            send(
                              `/projects/${selected}/refresh-prices`,
                              "POST",
                              { confirm: true },
                            ),
                          "Çmimet u rifreskuan. Diferencat u ruajtën në auditim.",
                        );
                      } catch (e) {
                        setError(e);
                      }
                    }}
                  >
                    <RefreshCw size={15} />
                    Rifresko çmimet
                  </button>
                </div>
              </div>
              <div className="panel totals-panel">
                <span className="eyebrow">
                  PËRMBLEDHJE FINANCIARE · {project.currency}
                </span>
                {[
                  ["subtotal", "Nëntotali"],
                  ["overhead", "Shpenzime të përgjithshme"],
                  ["profit", "Fitimi"],
                  ["discount", "Zbritje"],
                  ["other_charges", "Tarifa të tjera"],
                  ["vat", "TVSH"],
                ].map(([k, t]) => (
                  <div key={k}>
                    <span>{t}</span>
                    <b>
                      {money(
                        totals[k] ?? totals[k + "_amount"] ?? "0",
                        project.currency,
                      )}
                    </b>
                  </div>
                ))}
                <div className="grand-total">
                  <span>Totali përfundimtar</span>
                  <b>
                    {money(
                      totals.grand_total ?? totals.total ?? "0",
                      project.currency,
                    )}
                  </b>
                </div>
                <span
                  className={`total-caution ${totals.incomplete ? "" : "complete"}`}
                >
                  {totals.incomplete
                    ? `${totals.unresolved_count ?? rows.filter((r) => r.decision !== "approved").length} zëra pa miratim · Totali mund të jetë i paplotë.`
                    : rows.length
                      ? "Të gjithë zërat janë miratuar dhe përfshirë në total."
                      : "Nuk ka zëra të importuar."}
                </span>
                <button
                  className={finalized ? "secondary" : "full-width"}
                  disabled={busy || !rows.length}
                  onClick={() =>
                    finalized
                      ? prompt(
                          "Rihap preventivin?",
                          "Versioni i finalizuar ruhet në historik. Projekti bëhet sërish i redaktueshëm.",
                          () =>
                            send(`/projects/${selected}/reopen`, "POST", {
                              confirm: true,
                            }),
                          "Preventivi u rihap.",
                        )
                      : prompt(
                          "Finalizo preventivin?",
                          "Konfirmoni që të gjitha përshkrimet, sasitë dhe çmimet janë verifikuar. Versioni dhe çmimet do të ruhen të pandryshuara.",
                          () =>
                            send(`/projects/${selected}/finalize`, "POST", {
                              confirm: true,
                            }),
                          "Preventivi u finalizua.",
                        )
                  }
                >
                  {finalized ? (
                    <RotateCcw size={16} />
                  ) : (
                    <LockKeyhole size={16} />
                  )}{" "}
                  {finalized ? "Rihap për ndryshime" : "Finalizo preventivin"}
                </button>
              </div>
            </div>
          </>
        )
      )}
      {edit && project && (
        <RowEditor
          row={edit}
          prices={prices}
          project={project}
          onClose={() => setEdit(null)}
          onSave={async (payload) => {
            await send(
              `/projects/${selected}/rows/${edit.id}`,
              "PATCH",
              payload,
            );
            setEdit(null);
            await load();
          }}
        />
      )}
      {confirm && (
        <Confirm
          title={confirm.title}
          detail={confirm.detail}
          onClose={() => setConfirm(null)}
          onConfirm={confirm.action}
        />
      )}{" "}
      {settings && project && (
        <ProjectForm
          value={project}
          onClose={() => setSettings(false)}
          onSave={async (d) => {
            await send(`/projects/${selected}`, "PATCH", d);
            setSettings(false);
            await load();
          }}
        />
      )}
      {originalExport && project && (
        <Modal
          title="Eksporto në formatin origjinal"
          onClose={() => setOriginalExport(false)}
        >
          <p>
            Zgjidhni skedarin e importuar. Vetëm rreshtat e tij plotësohen;
            skedari burimor ruhet pa ndryshime.
          </p>
          {[...new Set(rows.map((r) => r.upload_id).filter(Boolean))].map(
            (id) => (
              <button
                className="secondary export-file"
                key={id}
                onClick={() =>
                  download(
                    `/projects/${selected}/export?format=original&upload_id=${id}`,
                    `${project.name}-boq-${id}.xlsx`,
                  ).catch(setError)
                }
              >
                <Download size={16} />
                BOQ #{id} · {rows.filter((r) => r.upload_id === id).length} zëra
              </button>
            ),
          )}
          {!rows.some((r) => r.upload_id) && (
            <Empty text="Nuk ka një skedar burimor për eksport." />
          )}
        </Modal>
      )}
      {compare && (
        <Compare
          projectId={selected!}
          versions={versions}
          onClose={() => setCompare(false)}
        />
      )}
    </>
  );
}
function RowEditor({
  row,
  prices,
  project,
  onClose,
  onSave,
}: {
  row: BoqRow;
  prices: Price[];
  project: Project;
  onClose: () => void;
  onSave: (d: any) => Promise<void>;
}) {
  const match = row.match_result || {};
  const [itemId, setItemId] = useState<number | null>(
      row.item_id || match.suggested_item_id || null,
    ),
    [price, setPrice] = useState(row.unit_price ?? ""),
    [decision, setDecision] = useState(row.decision || "pending"),
    [notes, setNotes] = useState(row.notes || ""),
    [query, setQuery] = useState(""),
    [confirmed, setConfirmed] = useState(false),
    [error, setError] = useState<unknown>(),
    [busy, setBusy] = useState(false),
    [creating, setCreating] = useState(false),
    [addedPrices, setAddedPrices] = useState<Price[]>([]);
  const catalog = [...prices, ...addedPrices];
  const item = catalog.find((p) => p.id === itemId);
  return (
    <Modal title={`Rishiko zërin ${row.item_number}`} onClose={onClose} wide>
      <div className="original-description">
        <span className="eyebrow">PËRSHKRIMI ORIGJINAL</span>
        <h3>{row.description}</h3>
        <span>
          {number(row.quantity)} {row.unit}
        </span>
      </div>
      {match.method && (
        <div className="match-analysis">
          <Badge status={match.classification || "pending"} />
          <span>
            {match.method} · {number(Number(match.confidence || 0) * 100)}%
            besim
          </span>
          <p>{match.explanation}</p>
          {match.discrepancies?.length > 0 && (
            <div className="notice">{match.discrepancies.join(" · ")}</div>
          )}
          <p className="muted">
            Besimi mat ngjashmërinë e sugjerimit dhe nuk garanton
            përputhshmërinë teknike.
          </p>
        </div>
      )}
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          try {
            await onSave({
              item_id: itemId,
              decision,
              unit_price: price === "" ? null : price,
              notes,
              confirm_override: confirmed,
            });
          } catch (e) {
            setError(e);
          } finally {
            setBusy(false);
          }
        }}
      >
        <Field label="Kërko në bazën e çmimeve">
          <input
            placeholder="Kodi ose përshkrimi…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </Field>
        <Field label="Zëri i katalogut">
          <select
            value={itemId || ""}
            onChange={(e) =>
              setItemId(e.target.value ? Number(e.target.value) : null)
            }
          >
            <option value="">Pa zë të katalogut / çmim manual</option>
            {catalog
              .filter(
                (p) =>
                  p.id === itemId ||
                  [p.code, p.name, p.description]
                    .join(" ")
                    .toLowerCase()
                    .includes(query.toLowerCase()),
              )
              .map((p) => (
                <option key={p.id} value={p.id}>
                  {p.code} · {p.name} · {p.unit} · {money(p.price, p.currency)}
                </option>
              ))}
          </select>
        </Field>
        <button
          type="button"
          className="text-button"
          onClick={() => setCreating(true)}
        >
          + Krijo zë të ri në bazën e çmimeve
        </button>
        {item && (
          <div className="item-scope">
            <div>
              <b>{item.description}</b>
              <p>{item.technical_specs}</p>
            </div>
            <span>
              {item.unit} · {money(item.price, item.currency)}
            </span>
            <small>
              {item.supply_included ? "Përfshin furnizimin" : "Pa furnizim"} ·{" "}
              {item.installation_included
                ? "Përfshin instalimin"
                : "Pa instalim"}{" "}
              · {item.price_kind}
            </small>
          </div>
        )}
        {match.alternatives?.length > 0 && (
          <div className="alternatives">
            <small>Kandidatë alternativë</small>
            {match.alternatives.map((a: any, i: number) => (
              <button
                type="button"
                className="secondary"
                key={i}
                onClick={() => setItemId(a.item_id ?? a.id)}
              >
                {a.code ||
                  catalog.find((p) => p.id === (a.item_id ?? a.id))?.code ||
                  a.item_id}{" "}
                · {number(Number(a.confidence ?? a.score ?? 0) * 100)}%
              </button>
            ))}
          </div>
        )}
        <div className="form-grid">
          <Field
            label={`Çmim i personalizuar (${project.currency} / ${row.unit})`}
            hint="Lëreni bosh për çmimin e katalogut me konvertimin e njësisë dhe monedhës."
          >
            <input
              type="number"
              min="0"
              step="any"
              value={price}
              onChange={(e) => setPrice(e.target.value)}
            />
          </Field>
          <Field label="Vendimi">
            <select
              value={decision}
              onChange={(e) => setDecision(e.target.value)}
            >
              <option value="pending">Në pritje / hiq miratimin</option>
              <option value="approved">Mirato çmimin</option>
              <option value="rejected">Refuzo përputhjen</option>
            </select>
          </Field>
        </div>
        <Field label="Shënime dhe arsyetimi">
          <textarea value={notes} onChange={(e) => setNotes(e.target.value)} />
        </Field>
        <label className="check wrap">
          <input
            type="checkbox"
            checked={confirmed}
            onChange={(e) => setConfirmed(e.target.checked)}
          />
          Konfirmoj ndryshimin e vendimit ose çmimit të miratuar dhe kam
          kontrolluar njësinë, fushën e punës e specifikimet.
        </label>
        <ErrorBox error={error} />
        <footer>
          <button type="button" className="secondary" onClick={onClose}>
            Anulo
          </button>
          <button
            disabled={
              busy ||
              project.status === "finalized" ||
              (row.decision === "approved" && !confirmed)
            }
          >
            {busy ? "Duke ruajtur…" : "Ruaj vendimin"}
          </button>
        </footer>
      </form>
      {creating && (
        <PriceForm
          value={{
            ...newPrice(),
            description: row.description,
            unit: row.unit,
            currency: project.currency,
          }}
          items={catalog}
          onClose={() => setCreating(false)}
          onSave={async (data) => {
            const created = await send<Price>("/prices", "POST", data);
            setAddedPrices([...addedPrices, created]);
            setItemId(created.id);
            setCreating(false);
          }}
        />
      )}
    </Modal>
  );
}
function Compare({
  projectId,
  versions: onPage,
  onClose,
}: {
  projectId: number;
  versions: any[];
  onClose: () => void;
}) {
  const [versions, setVersions] = useState<any[]>(onPage),
    [left, setLeft] = useState(""),
    [right, setRight] = useState(""),
    [result, setResult] = useState<any>(),
    [error, setError] = useState<unknown>();
  useEffect(() => {
    api(`/projects/${projectId}/versions`)
      .then((d) => {
        const v = list<any>(d);
        setVersions(v);
        setLeft(String(v[0]?.number ?? ""));
        setRight(String(v[1]?.number ?? v[0]?.number ?? ""));
      })
      .catch(setError);
  }, [projectId]);
  return (
    <Modal title="Krahasimi i versioneve" onClose={onClose} wide>
      <ErrorBox error={error} />
      {!versions.length ? (
        <Empty text="Versionet krijohen kur finalizohet ose rishikohet preventivi." />
      ) : (
        <>
          <div className="form-grid">
            {[
              ["left", left, setLeft],
              ["right", right, setRight],
            ].map(([key, value, setter]) => (
              <Field
                key={String(key)}
                label={
                  key === "left" ? "Versioni bazë" : "Versioni i krahasimit"
                }
              >
                <select
                  value={String(value)}
                  onChange={(e) =>
                    (setter as (v: string) => void)(e.target.value)
                  }
                >
                  {versions.map((v) => (
                    <option key={v.id} value={v.number}>
                      Versioni {v.number ?? v.id} · {v.created_at?.slice(0, 10)}
                    </option>
                  ))}
                </select>
              </Field>
            ))}
          </div>
          <button
            onClick={() =>
              api(`/projects/${projectId}/compare?left=${left}&right=${right}`)
                .then(setResult)
                .catch(setError)
            }
          >
            Krahaso versionet
          </button>
          {result && (
            <div className="comparison">
              {result.warnings?.length > 0 && (
                <div className="notice">{result.warnings.join(" · ")}</div>
              )}
              <p>
                Diferenca totale:{" "}
                <b>
                  {money(
                    result.difference ??
                      result.total_difference ??
                      result.grand_total_difference,
                    result.currency || "EUR",
                  )}
                </b>
              </p>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Zëri</th>
                      <th>Çmimi i mëparshëm</th>
                      <th>Çmimi i ri</th>
                      <th>Diferenca</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(
                      result.row_differences ||
                      result.rows ||
                      result.changes ||
                      []
                    ).map((r: any, i: number) => (
                      <tr key={i}>
                        <td>{r.item_number || r.description || r.row_id}</td>
                        <td>
                          {money(
                            r.old_unit_price,
                            result.left_currency || result.currency,
                          )}
                        </td>
                        <td>
                          {money(
                            r.new_unit_price,
                            result.right_currency || result.currency,
                          )}
                        </td>
                        <td>
                          {money(r.unit_price_difference, result.currency)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </Modal>
  );
}
