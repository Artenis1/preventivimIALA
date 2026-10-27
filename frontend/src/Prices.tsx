import { useEffect, useState } from "react";
import {
  Plus,
  Search,
  Download,
  Upload,
  Pencil,
  Archive,
  Layers3,
} from "lucide-react";
import { api, send, upload, download } from "./api";
import PriceImport from "./PriceImport";
import type { Price, Page } from "./types";
import { categories } from "./i18n";
import { money, list } from "./utils";
import { Modal, Field, ErrorBox, Empty, Loading, Badge, Confirm } from "./ui";
const blank = {
  code: "",
  name: "",
  description: "",
  synonyms: "",
  technical_specs: "",
  category: categories[0],
  subcategory: "",
  unit: "copë",
  price: "0",
  currency: "EUR",
  supplier: "",
  price_date: new Date().toISOString().slice(0, 10),
  valid_until: "",
  vat_included: false,
  vat_rate: "20",
  material_cost: "0",
  labor_cost: "0",
  machinery_cost: "0",
  transport_cost: "0",
  other_cost: "0",
  notes: "",
  active: true,
  price_kind: "purchase",
  supply_included: true,
  installation_included: false,
};
export default function Prices({
  mode,
  onChange,
}: {
  mode: Page;
  onChange?: () => void;
}) {
  const [items, setItems] = useState<Price[]>([]),
    [query, setQuery] = useState(""),
    [category, setCategory] = useState(""),
    [archived, setArchived] = useState(false),
    [loading, setLoading] = useState(true),
    [error, setError] = useState<unknown>(),
    [edit, setEdit] = useState<any>(null),
    [archive, setArchive] = useState<Price | null>(null),
    [resource, setResource] = useState<Price | null>(null),
    [message, setMessage] = useState(""),
    [importing, setImporting] = useState(false);
  const load = () => {
    setLoading(true);
    api("/prices?include_inactive=true")
      .then((d) => setItems(list<Price>(d)))
      .catch(setError)
      .finally(() => setLoading(false));
  };
  useEffect(load, []);
  const filtered = items.filter(
    (p) =>
      (archived || p.active !== false) &&
      (!category || p.category === category) &&
      [p.code, p.name, p.description, p.synonyms]
        .join(" ")
        .toLowerCase()
        .includes(query.toLowerCase()) &&
      (mode === "materials"
        ? p.price_kind === "purchase"
        : mode === "labor"
          ? /pun|pajis|makiner|transport|labor|equipment/i.test(
              p.category + " " + p.name,
            ) || p.price_kind === "installed"
          : true),
  );
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">KATALOGU QENDROR</span>
          <h1>
            {mode === "materials"
              ? "Materialet"
              : mode === "labor"
                ? "Puna dhe pajisjet"
                : "Baza e çmimeve"}
          </h1>
          <p>
            Çmime të dokumentuara, të ndara sipas burimit dhe fushës së punës.
          </p>
        </div>
        <button onClick={() => setEdit({ ...blank })}>
          <Plus size={17} />
          Shto zë
        </button>
      </div>
      <ErrorBox error={error} />
      {message && <div className="notice">{message}</div>}
      <div className="panel">
        <div className="toolbar">
          <label className="search">
            <Search size={18} />
            <input
              aria-label="Kërko çmime"
              placeholder="Kërko kod, përshkrim ose sinonim…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
          <select
            aria-label="Kategoria"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
          >
            <option value="">Të gjitha kategoritë</option>
            {categories.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
          <label className="check">
            <input
              type="checkbox"
              checked={archived}
              onChange={(e) => setArchived(e.target.checked)}
            />
            Arkivuar
          </label>
          <button className="secondary" onClick={() => setImporting(true)}>
            <Upload size={16} />
            Importo
          </button>
          <button
            className="secondary"
            onClick={() =>
              download("/prices/export", "baza-e-cmimeve.xlsx").catch(setError)
            }
          >
            <Download size={16} />
            Eksporto
          </button>
        </div>
        {loading ? (
          <Loading />
        ) : !filtered.length ? (
          <Empty
            text="Asnjë zë nuk u gjet."
            action={
              <button onClick={() => setEdit({ ...blank })}>
                Shto çmimin e parë
              </button>
            }
          />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Kodi / zëri</th>
                  <th>Kategoria</th>
                  <th>Njësia</th>
                  <th>Çmimi</th>
                  <th>Lloji / përfshirjet</th>
                  <th>Data</th>
                  <th aria-label="Veprime" />
                </tr>
              </thead>
              <tbody>
                {filtered.map((p) => (
                  <tr key={p.id}>
                    <td>
                      <span className="code">{p.code}</span>
                      <strong>{p.name}</strong>
                      <span className="cell-sub">{p.description}</span>
                    </td>
                    <td>
                      {p.category}
                      <span className="cell-sub">{p.supplier}</span>
                    </td>
                    <td>{p.unit}</td>
                    <td className="numeric">
                      {money(p.price, p.currency)}
                      {p.active === false && <Badge status="inactive" />}
                    </td>
                    <td>
                      {(
                        {
                          purchase: "Blerje",
                          direct: "Kosto direkte",
                          installed: "Punim i instaluar",
                          selling: "Çmim shitjeje",
                        } as any
                      )[p.price_kind] || p.price_kind}
                      <span className="cell-sub">
                        {p.supply_included ? "Furnizim " : ""}
                        {p.installation_included ? " · Montim" : ""}
                      </span>
                    </td>
                    <td>{p.price_date}</td>
                    <td>
                      <div className="row-actions">
                        <button
                          className="icon-button"
                          aria-label={`Analiza ${p.code}`}
                          title="Analiza e burimeve"
                          onClick={() => setResource(p)}
                        >
                          <Layers3 size={17} />
                        </button>
                        <button
                          className="icon-button"
                          aria-label={`Redakto ${p.code}`}
                          onClick={() => setEdit({ ...p, reason: "" })}
                        >
                          <Pencil size={17} />
                        </button>
                        {p.active !== false && (
                          <button
                            className="icon-button danger-text"
                            aria-label={`Arkivo ${p.code}`}
                            onClick={() => setArchive(p)}
                          >
                            <Archive size={17} />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="table-footer">
          {filtered.length} zëra · Çmimet nuk konvertohen pa kurs të
          konfiguruar.
        </div>
      </div>
      {importing && (
        <PriceImport
          onClose={() => setImporting(false)}
          onImported={(result) => {
            setMessage(
              `Importi përfundoi: ${result.imported ?? result.count ?? ""} zëra.`,
            );
            setImporting(false);
            load();
            onChange?.();
          }}
        />
      )}
      {edit && (
        <PriceForm
          value={edit}
          items={items}
          onClose={() => setEdit(null)}
          onSave={async (data) => {
            await send(
              edit.id ? `/prices/${edit.id}` : "/prices",
              edit.id ? "PUT" : "POST",
              data,
            );
            setEdit(null);
            load();
            onChange?.();
          }}
        />
      )}
      {archive && (
        <Confirm
          title="Arkivo zërin?"
          detail={`Zëri ${archive.code} nuk do të përdoret në sugjerime të reja. Preventivat ekzistues ruajnë çmimet e tyre.`}
          onClose={() => setArchive(null)}
          onConfirm={async () => {
            await send(`/prices/${archive.id}`, "DELETE");
            load();
          }}
        />
      )}
      {resource && (
        <Resources
          item={resource}
          items={items}
          onClose={() => setResource(null)}
          onSave={load}
        />
      )}
    </>
  );
}
export function PriceForm({
  value,
  items,
  onClose,
  onSave,
}: {
  value: any;
  items: Price[];
  onClose: () => void;
  onSave: (d: any) => Promise<void>;
}) {
  const [form, setForm] = useState({ ...value }),
    [error, setError] = useState<unknown>(),
    [busy, setBusy] = useState(false);
  const update = (key: string, value: any) =>
    setForm({ ...form, [key]: value });
  const text = (key: string, label: string, required = false) => (
    <Field label={label}>
      <input
        required={required}
        value={form[key] ?? ""}
        onChange={(e) => update(key, e.target.value)}
      />
    </Field>
  );
  const decimal = (key: string, label: string) => (
    <Field label={label}>
      <input
        type="number"
        min="0"
        step="any"
        required
        value={form[key] ?? "0"}
        onChange={(e) => update(key, e.target.value)}
      />
    </Field>
  );
  const duplicate = items.some(
    (p) =>
      p.id !== form.id &&
      p.description?.trim().toLowerCase() ===
        form.description?.trim().toLowerCase() &&
      form.description,
  );
  return (
    <Modal
      title={form.id ? "Redakto zërin e çmimit" : "Zë i ri çmimi"}
      onClose={onClose}
      wide
    >
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError(undefined);
          try {
            const payload = Object.fromEntries(
              [...Object.keys(blank), "reason"]
                .filter((k) => form[k] !== undefined)
                .map((k) => [k, form[k]]),
            );
            await onSave(payload);
          } catch (e) {
            setError(e);
          } finally {
            setBusy(false);
          }
        }}
      >
        <div className="form-grid">
          {text("code", "Kodi unik", true)}
          {text("name", "Emërtimi", true)}
          <Field label="Përshkrimi i standardizuar">
            <textarea
              required
              value={form.description}
              onChange={(e) => update("description", e.target.value)}
            />
          </Field>
          <Field label="Specifikimet teknike">
            <textarea
              value={form.technical_specs}
              onChange={(e) => update("technical_specs", e.target.value)}
            />
          </Field>
          {text("synonyms", "Sinonime dhe emërtime alternative")}
          <Field label="Kategoria">
            <select
              value={form.category}
              onChange={(e) => update("category", e.target.value)}
            >
              {categories.map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
          </Field>
          {text("subcategory", "Nënkategoria")}
          {text("unit", "Njësia", true)}
          {decimal("price", "Çmimi për njësi")}
          <Field label="Monedha">
            <select
              value={form.currency}
              onChange={(e) => update("currency", e.target.value)}
            >
              <option>EUR</option>
              <option>ALL</option>
            </select>
          </Field>
          <Field label="Lloji i çmimit">
            <select
              value={form.price_kind}
              onChange={(e) => update("price_kind", e.target.value)}
            >
              <option value="purchase">Blerje furnitori</option>
              <option value="direct">Kosto direkte</option>
              <option value="installed">Kosto e instaluar</option>
              <option value="selling">Çmim shitjeje</option>
            </select>
          </Field>
          {text("supplier", "Furnitori")}
          <Field label="Data e çmimit">
            <input
              type="date"
              required
              value={form.price_date}
              onChange={(e) => update("price_date", e.target.value)}
            />
          </Field>
          <Field label="I vlefshëm deri">
            <input
              type="date"
              value={form.valid_until || ""}
              onChange={(e) => update("valid_until", e.target.value)}
            />
          </Field>
          {decimal("vat_rate", "TVSH (%)")}
          <div className="checks">
            <label className="check">
              <input
                type="checkbox"
                checked={form.vat_included}
                onChange={(e) => update("vat_included", e.target.checked)}
              />
              Çmimi përfshin TVSH
            </label>
            <label className="check">
              <input
                type="checkbox"
                checked={form.supply_included}
                onChange={(e) => update("supply_included", e.target.checked)}
              />
              Përfshin furnizimin
            </label>
            <label className="check">
              <input
                type="checkbox"
                checked={form.installation_included}
                onChange={(e) =>
                  update("installation_included", e.target.checked)
                }
              />
              Përfshin instalimin
            </label>
            <label className="check">
              <input
                type="checkbox"
                checked={form.active}
                onChange={(e) => update("active", e.target.checked)}
              />
              Aktiv
            </label>
          </div>
        </div>
        <h3>Përbërja e kostos</h3>
        <p className="muted">
          Vlera shpjeguese për analizë. Nuk i shtohen përsëri çmimit për njësi.
        </p>
        <div className="form-grid three">
          {decimal("material_cost", "Materiale")}
          {decimal("labor_cost", "Punë")}
          {decimal("machinery_cost", "Makineri")}
          {decimal("transport_cost", "Transport")}
          {decimal("other_cost", "Kosto të tjera")}
          {form.id && text("reason", "Arsyeja e ndryshimit", true)}
        </div>
        <Field label="Shënime">
          <textarea
            value={form.notes}
            onChange={(e) => update("notes", e.target.value)}
          />
        </Field>
        {form.id && (
          <section className="attachment-section">
            <h3>Dokumente dhe oferta</h3>
            <p className="muted">
              PDF, PNG ose JPEG · maksimumi 5 MB. Ngarkimi ruhet menjëherë.
            </p>
            <div>
              {(form.attachments || []).map((a: any) => (
                <button
                  type="button"
                  key={a.id}
                  className="secondary"
                  onClick={() =>
                    download(
                      `/prices/${form.id}/attachments/${a.id}`,
                      a.filename,
                    ).catch(setError)
                  }
                >
                  <Download size={14} />
                  {a.filename}
                </button>
              ))}
            </div>
            <label className="attachment-upload">
              Shto dokument
              <input
                type="file"
                accept=".pdf,.png,.jpg,.jpeg"
                disabled={busy}
                onChange={async (e) => {
                  const file = e.target.files?.[0];
                  if (!file) return;
                  setBusy(true);
                  try {
                    const a = await upload(
                      `/prices/${form.id}/attachments`,
                      file,
                    );
                    setForm({
                      ...form,
                      attachments: [...(form.attachments || []), a],
                    });
                  } catch (e) {
                    setError(e);
                  } finally {
                    setBusy(false);
                    e.target.value = "";
                  }
                }}
              />
            </label>
          </section>
        )}
        {duplicate && (
          <div className="notice">
            Ekziston një zë me të njëjtin përshkrim. Kontrolloni për dublikatë.
          </div>
        )}
        <ErrorBox error={error} />
        <footer>
          <button type="button" className="secondary" onClick={onClose}>
            Anulo
          </button>
          <button disabled={busy}>
            {busy ? "Duke ruajtur…" : "Ruaj zërin"}
          </button>
        </footer>
      </form>
    </Modal>
  );
}
function Resources({
  item,
  items,
  onClose,
  onSave,
}: {
  item: Price;
  items: Price[];
  onClose: () => void;
  onSave: () => void;
}) {
  const [rows, setRows] = useState<any[]>([]),
    [reason, setReason] = useState(""),
    [error, setError] = useState<unknown>(),
    [loading, setLoading] = useState(true),
    [busy, setBusy] = useState(false),
    [result, setResult] = useState<any>();
  useEffect(() => {
    api(`/prices/${item.id}/resources`)
      .then((d) => {
        const latest = Array.isArray(d) ? d[0] : d;
        setRows(latest?.resources || []);
        setResult(latest);
      })
      .catch(setError)
      .finally(() => setLoading(false));
  }, [item.id]);
  const change = (i: number, k: string, v: any) =>
    setRows(rows.map((r, j) => (i === j ? { ...r, [k]: v } : r)));
  return (
    <Modal title={`Analiza e burimeve · ${item.code}`} onClose={onClose} wide>
      <p>
        Koeficientët dhe humbjet përcaktohen nga inxhinieri. Nuk supozohet asnjë
        sasi.
      </p>
      <ErrorBox error={error} />
      {loading ? (
        <Loading />
      ) : (
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            try {
              setResult(
                await send(`/prices/${item.id}/resources`, "PUT", {
                  resources: rows.map(
                    ({ item_id, coefficient, waste_percent }) => ({
                      item_id: Number(item_id),
                      coefficient,
                      waste_percent,
                    }),
                  ),
                  reason,
                }),
              );
              onSave();
            } catch (e) {
              setError(e);
            } finally {
              setBusy(false);
            }
          }}
        >
          <div className="resource-list">
            {rows.map((r, i) => (
              <div className="resource-row" key={i}>
                <select
                  aria-label={`Burimi ${i + 1}`}
                  required
                  value={r.item_id}
                  onChange={(e) => change(i, "item_id", e.target.value)}
                >
                  <option value="">Zgjidh burimin</option>
                  {items
                    .filter((p) => p.id !== item.id && p.active)
                    .map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.code} · {p.name} ({p.unit})
                      </option>
                    ))}
                </select>
                <Field label="Koeficienti">
                  <input
                    type="number"
                    min="0.000001"
                    step="any"
                    required
                    value={r.coefficient}
                    onChange={(e) => change(i, "coefficient", e.target.value)}
                  />
                </Field>
                <Field label="Humbje (%)">
                  <input
                    type="number"
                    min="0"
                    max="100"
                    step="any"
                    required
                    value={r.waste_percent}
                    onChange={(e) => change(i, "waste_percent", e.target.value)}
                  />
                </Field>
                <button
                  type="button"
                  className="secondary"
                  onClick={() => setRows(rows.filter((_, j) => j !== i))}
                >
                  Hiq
                </button>
              </div>
            ))}
          </div>
          <button
            type="button"
            className="secondary"
            onClick={() =>
              setRows([
                ...rows,
                { item_id: "", coefficient: "1", waste_percent: "0" },
              ])
            }
          >
            <Plus size={16} />
            Shto burim
          </button>
          <Field label="Arsyeja / versioni i ri">
            <input
              required
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </Field>
          {result && (
            <div className="notice">
              Kosto direkte:{" "}
              {money(result.direct_cost ?? result.total, item.currency)} ·
              Versioni {result.number ?? result.version ?? "—"}
            </div>
          )}
          <footer>
            <button type="button" className="secondary" onClick={onClose}>
              Mbyll
            </button>
            <button disabled={busy}>Ruaj versionin e analizës</button>
          </footer>
        </form>
      )}
    </Modal>
  );
}

export const newPrice = () => ({ ...blank });
