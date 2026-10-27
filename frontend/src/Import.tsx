import { useEffect, useRef, useState } from "react";
import {
  FileSpreadsheet,
  UploadCloud,
  ArrowRight,
  CheckCircle2,
} from "lucide-react";
import { api, send, upload } from "./api";
import type { Project } from "./types";
import { list, excelColumn, duplicateMapping } from "./utils";
import { Field, ErrorBox, Loading } from "./ui";
const columns = [
  ["item_number", "Nr. i zërit"],
  ["code", "Kodi i zërit"],
  ["description", "Përshkrimi i punës *"],
  ["unit", "Njësia *"],
  ["quantity", "Sasia *"],
  ["existing_unit_price", "Çmimi ekzistues"],
  ["existing_total", "Vlera ekzistuese"],
];
export default function Import({
  projectId,
  onDone,
  onProject,
}: {
  projectId: number | null;
  onDone: (id: number) => void;
  onProject: (id: number) => void;
}) {
  const [projects, setProjects] = useState<Project[]>([]),
    [selected, setSelected] = useState<number | null>(projectId),
    [workbook, setWorkbook] = useState<any>(null),
    [sheet, setSheet] = useState(""),
    [header, setHeader] = useState(0),
    [mapping, setMapping] = useState<Record<string, number>>({}),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>(),
    [result, setResult] = useState<any>(null);
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => {
    api("/projects")
      .then((d) => setProjects(list<Project>(d)))
      .catch(setError);
  }, []);
  const sheets = workbook?.sheets || [];
  const sheetData = Array.isArray(sheets)
    ? sheets.find((s: any) => (typeof s === "string" ? s : s.name) === sheet)
    : sheets[sheet];
  const preview = sheetData?.preview || workbook?.preview || [];
  const previews = preview.map((r: any) =>
    Array.isArray(r) ? r : r.values || [],
  );
  const width = Math.max(
    1,
    sheetData?.column_count || 0,
    ...previews.map((r: any[]) => r.length),
  );
  const applySheet = (name: string, w: any = workbook) => {
    setSheet(name);
    const s = Array.isArray(w.sheets)
      ? w.sheets.find((s: any) => (typeof s === "string" ? s : s.name) === name)
      : w.sheets?.[name];
    setHeader(s?.header_row ?? w.header_row ?? 0);
    setMapping(s?.suggested_mapping || s?.mapping || w.suggested_mapping || {});
  };
  const selectFile = async (file?: File) => {
    if (!file || !selected) return;
    setBusy(true);
    setError(undefined);
    setResult(null);
    try {
      const d = await upload(`/projects/${selected}/imports`, file);
      setWorkbook(d);
      const first = Array.isArray(d.sheets)
        ? d.sheets[0]
        : Object.keys(d.sheets || {})[0];
      applySheet(typeof first === "string" ? first : first?.name, d);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">NGA EXCEL NË PROJEKT</span>
          <h1>Importo preventivin</h1>
          <p>
            Zgjidhni fletën, kontrolloni kolonat dhe importoni vetëm rreshtat e
            vlefshëm.
          </p>
        </div>
        <span className="file-label">
          <FileSpreadsheet size={18} />
          .xlsx · .xlsm
        </span>
      </div>
      <div className="steps">
        <span className={workbook ? "complete" : "current"}>
          1 <b>Ngarko skedarin</b>
        </span>
        <i />
        <span className={workbook && !result ? "current" : ""}>
          2 <b>Lidh kolonat</b>
        </span>
        <i />
        <span className={result ? "complete" : ""}>
          3 <b>Kontrollo importin</b>
        </span>
      </div>
      <ErrorBox error={error} />
      <div className="panel import-panel">
        <Field label="Projekti">
          <select
            value={selected || ""}
            onChange={(e) => {
              const id = Number(e.target.value);
              setSelected(id);
              onProject(id);
              setWorkbook(null);
              setResult(null);
            }}
          >
            <option value="">Zgjidhni një projekt…</option>
            {projects.map((p) => (
              <option value={p.id} key={p.id}>
                {p.name} · {p.currency}
              </option>
            ))}
          </select>
        </Field>
        {!selected && (
          <p className="muted">
            Krijoni fillimisht një projekt nga menuja “Projektet”.
          </p>
        )}
        <input
          type="file"
          ref={input}
          hidden
          accept=".xlsx,.xlsm"
          onChange={(e) => {
            selectFile(e.target.files?.[0]);
            e.target.value = "";
          }}
        />
        <div
          className={`dropzone ${!selected ? "disabled" : ""}`}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            if (selected) selectFile(e.dataTransfer.files[0]);
          }}
        >
          <div className="upload-symbol">
            <UploadCloud size={28} />
          </div>
          <h3>Vendosni skedarin Excel këtu</h3>
          <p>Skedari origjinal ruhet pa ndryshime. Makrot nuk ekzekutohen.</p>
          <button
            className="secondary"
            disabled={!selected || busy}
            onClick={() => input.current?.click()}
          >
            Zgjidh skedarin
          </button>
          <small>Formate .xlsx / .xlsm · Kufiri përcaktohet nga serveri</small>
        </div>
        {busy && <Loading />}
      </div>
      {workbook && !result && (
        <section className="panel mapping-panel">
          <div className="section-heading">
            <div>
              <span className="eyebrow">HAPI 02</span>
              <h2>Kontrolloni lidhjen e kolonave</h2>
            </div>
          </div>
          <div className="form-grid">
            <Field label="Fleta e punës">
              <select
                value={sheet}
                onChange={(e) => applySheet(e.target.value)}
              >
                {(Array.isArray(sheets) ? sheets : Object.keys(sheets)).map(
                  (s: any) => (
                    <option key={typeof s === "string" ? s : s.name}>
                      {typeof s === "string" ? s : s.name}
                    </option>
                  ),
                )}
              </select>
            </Field>
            <Field
              label="Rreshti i titujve (numërimi në Excel)"
              hint="Rreshtat para dhe përfshirë titullin nuk importohen."
            >
              <input
                type="number"
                min="1"
                value={header + 1}
                onChange={(e) =>
                  setHeader(Math.max(0, Number(e.target.value) - 1))
                }
              />
            </Field>
          </div>
          <div className="mapping-grid">
            {columns.map(([key, label]) => (
              <Field key={key} label={label}>
                <select
                  value={mapping[key] ?? ""}
                  onChange={(e) =>
                    setMapping((prev) => {
                      const next = { ...prev };
                      if (e.target.value === "") delete next[key];
                      else next[key] = Number(e.target.value);
                      return next;
                    })
                  }
                >
                  <option value="">— Mos importo —</option>
                  {Array.from({ length: width }, (_, i) => (
                    <option value={i} key={i}>
                      {excelColumn(i)} ·{" "}
                      {String(
                        previews[header]?.[i] ?? "Kolonë pa titull",
                      ).slice(0, 60)}
                    </option>
                  ))}
                </select>
              </Field>
            ))}
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Rreshti</th>
                  {Array.from({ length: width }, (_, i) => (
                    <th key={i}>{excelColumn(i)}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {previews.slice(0, 15).map((row: any[], i: number) => (
                  <tr key={i} className={i === header ? "header-preview" : ""}>
                    <td>{i + 1}</td>
                    {Array.from({ length: width }, (_, j) => (
                      <td key={j}>{String(row[j] ?? "")}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {duplicateMapping(mapping) && (
            <div className="notice">
              Një kolonë është lidhur me disa fusha. Zgjidhni një kolonë të
              ndryshme ose “Mos importo” për fushën opsionale.
            </div>
          )}
          <footer className="mapping-footer">
            <span className="muted">
              Përshkrimi, njësia dhe sasia janë të detyrueshme.
            </span>
            <button
              disabled={
                busy ||
                duplicateMapping(mapping) ||
                mapping.description === undefined ||
                mapping.quantity === undefined ||
                mapping.unit === undefined
              }
              onClick={async () => {
                setBusy(true);
                setError(undefined);
                try {
                  setResult(
                    await send(
                      `/projects/${selected}/imports/${workbook.id ?? workbook.upload_id}/commit`,
                      "POST",
                      { sheet, mapping, header_row: header },
                    ),
                  );
                } catch (e) {
                  setError(e);
                } finally {
                  setBusy(false);
                }
              }}
            >
              Importo rreshtat
              <ArrowRight size={16} />
            </button>
          </footer>
        </section>
      )}
      {result && (
        <section className="panel import-result">
          <CheckCircle2 size={36} />
          <h2>Importi përfundoi</h2>
          <p>
            {result.imported ?? result.count ?? result.rows?.length ?? 0}{" "}
            rreshta u shtuan në projekt.
          </p>
          {result.rejected?.length > 0 && (
            <>
              <h3>Rreshtat e përjashtuar ({result.rejected.length})</h3>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Rreshti</th>
                      <th>Arsyeja</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.rejected.map((r: any, i: number) => (
                      <tr key={i}>
                        <td>{r.source_row ?? r.row}</td>
                        <td>{r.reason}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
          <button onClick={() => onDone(selected!)}>
            Vazhdo te përputhjet
            <ArrowRight size={16} />
          </button>
        </section>
      )}
    </>
  );
}
