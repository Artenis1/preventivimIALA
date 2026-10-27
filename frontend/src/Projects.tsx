import { useEffect, useState } from "react";
import { Plus, FolderOpen, ArrowUpRight, MapPin } from "lucide-react";
import { api, send } from "./api";
import type { Project } from "./types";
import { list } from "./utils";
import { Field, Modal, ErrorBox, Loading, Empty, Badge } from "./ui";
const blank = {
  name: "",
  client: "",
  location: "",
  project_type: "Ndërtim",
  currency: "EUR",
  vat_rate: "20",
  overhead_percent: "0",
  profit_percent: "0",
  discount_percent: "0",
  other_charges: "0",
  calculation_base: "direct",
  notes: "",
};
export default function Projects({ onOpen }: { onOpen: (id: number) => void }) {
  const [projects, setProjects] = useState<Project[]>([]),
    [loading, setLoading] = useState(true),
    [error, setError] = useState<unknown>(),
    [edit, setEdit] = useState<any>(null),
    [query, setQuery] = useState("");
  const load = () => {
    setLoading(true);
    api("/projects")
      .then((d) => setProjects(list<Project>(d)))
      .catch(setError)
      .finally(() => setLoading(false));
  };
  useEffect(load, []);
  const filtered = projects.filter((p) =>
    (p.name + " " + p.client + " " + p.location)
      .toLowerCase()
      .includes(query.toLowerCase()),
  );
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">MENAXHIMI I PUNËS</span>
          <h1>Projektet</h1>
          <p>Preventiva të pavarura, me çmime të ruajtura për çdo projekt.</p>
        </div>
        <button onClick={() => setEdit({ ...blank })}>
          <Plus size={17} />
          Projekt i ri
        </button>
      </div>
      <ErrorBox error={error} />
      <div className="toolbar panel">
        <input
          className="project-search"
          placeholder="Kërko projekt ose klient…"
          aria-label="Kërko projekt"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <span className="muted">
          {projects.length} projekte në hapësirën tuaj
        </span>
      </div>
      {loading ? (
        <Loading />
      ) : !filtered.length ? (
        <Empty
          text="Nuk ka projekte ende."
          action={
            <button onClick={() => setEdit({ ...blank })}>
              Krijo projektin e parë
            </button>
          }
        />
      ) : (
        <div className="project-grid">
          {filtered.map((p) => (
            <article className="project-card" key={p.id}>
              <div className="project-top">
                <div className="project-symbol">
                  <FolderOpen size={22} />
                </div>
                <Badge status={p.status || "draft"} />
              </div>
              <span className="eyebrow">
                {p.project_type || "PROJEKT INXHINIERIK"}
              </span>
              <h2>{p.name}</h2>
              <p>{p.client || "Klient i papërcaktuar"}</p>
              <div className="project-location">
                <MapPin size={13} />
                {p.location || "Vendndodhje e papërcaktuar"}
              </div>
              <div className="project-meta">
                <span>
                  Monedha <b>{p.currency}</b>
                </span>
                <span>
                  TVSH <b>{p.vat_rate}%</b>
                </span>
              </div>
              <footer>
                <button className="text-button" onClick={() => setEdit(p)}>
                  Cilësimet
                </button>
                <button className="secondary" onClick={() => onOpen(p.id)}>
                  Hap preventivin
                  <ArrowUpRight size={16} />
                </button>
              </footer>
            </article>
          ))}
        </div>
      )}
      {edit && (
        <ProjectForm
          value={edit}
          onClose={() => setEdit(null)}
          onSave={async (data) => {
            const result = await send(
              edit.id ? `/projects/${edit.id}` : "/projects",
              edit.id ? "PATCH" : "POST",
              data,
            );
            setEdit(null);
            load();
            if (!edit.id) onOpen(result.id);
          }}
        />
      )}
    </>
  );
}
export function ProjectForm({
  value,
  onClose,
  onSave,
}: {
  value: any;
  onClose: () => void;
  onSave: (d: any) => Promise<void>;
}) {
  const [form, setForm] = useState({ ...blank, ...value }),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>();
  const change = (k: string, v: string) => setForm({ ...form, [k]: v });
  const text = (key: string, label: string, required = false) => (
    <Field label={label}>
      <input
        required={required}
        value={(form as any)[key] || ""}
        onChange={(e) => change(key, e.target.value)}
      />
    </Field>
  );
  const percent = (key: string, label: string) => (
    <Field label={label}>
      <input
        type="number"
        min="0"
        max={key === "other_charges" ? undefined : "100"}
        step="any"
        required
        value={(form as any)[key]}
        onChange={(e) => change(key, e.target.value)}
      />
    </Field>
  );
  return (
    <Modal
      title={value.id ? "Cilësimet e projektit" : "Krijo projekt të ri"}
      onClose={onClose}
      wide
    >
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          try {
            const data = Object.fromEntries(
              Object.keys(blank).map((k) => [k, (form as any)[k]]),
            );
            await onSave(data);
          } catch (e) {
            setError(e);
          } finally {
            setBusy(false);
          }
        }}
      >
        <div className="form-grid">
          {text("name", "Emri i projektit", true)}
          {text("client", "Klienti")}
          {text("location", "Vendndodhja")}
          <Field label="Lloji i projektit">
            <select
              value={form.project_type}
              onChange={(e) => change("project_type", e.target.value)}
            >
              <option>Ndërtim</option>
              <option>Fotovoltaik</option>
              <option>Inxhinieri civile</option>
              <option>Instalime elektrike</option>
              <option>Tjetër</option>
            </select>
          </Field>
          <Field label="Monedha">
            <select
              value={form.currency}
              onChange={(e) => change("currency", e.target.value)}
            >
              <option>EUR</option>
              <option>ALL</option>
            </select>
          </Field>
          {percent("vat_rate", "TVSH (%)")}
          {percent("overhead_percent", "Shpenzime të përgjithshme (%)")}
          {percent("profit_percent", "Shtesë fitimi (%)")}
          {percent("discount_percent", "Zbritje (%)")}
          {percent(
            "other_charges",
            "Tarifa të tjera (në monedhën e projektit)",
          )}
          <Field label="Baza e shpenzimeve dhe fitimit">
            <select
              value={form.calculation_base}
              onChange={(e) => change("calculation_base", e.target.value)}
            >
              <option value="direct">
                Nëntotali neto i çmimeve të zgjedhura
              </option>
              <option value="subtotal">
                Nëntotali neto + shpenzime (për fitimin)
              </option>
            </select>
          </Field>
        </div>
        <Field label="Shënime">
          <textarea
            value={form.notes}
            onChange={(e) => change("notes", e.target.value)}
          />
        </Field>
        <div className="notice">
          Llogaritjet kryhen në server me aritmetikë dhjetore. Çmimet ruhen si
          snapshot dhe ndryshimet në katalog nuk i ndryshojnë automatikisht.
        </div>
        <ErrorBox error={error} />
        <footer>
          <button className="secondary" type="button" onClick={onClose}>
            Anulo
          </button>
          <button disabled={busy}>
            {busy ? "Duke ruajtur…" : "Ruaj projektin"}
          </button>
        </footer>
      </form>
    </Modal>
  );
}
