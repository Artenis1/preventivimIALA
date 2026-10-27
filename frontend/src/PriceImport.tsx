import { useRef, useState } from "react";
import {
  CheckCircle2,
  FileSpreadsheet,
  RefreshCw,
  UploadCloud,
} from "lucide-react";
import { api, send } from "./api";
import { Field, ErrorBox, Modal } from "./ui";
import { duplicateMapping, excelColumn } from "./utils";

const coreFields = [
  ["code", "Kodi"],
  ["name", "Emërtimi"],
  ["description", "Përshkrimi"],
  ["unit", "Njësia *"],
  ["price", "Çmimi për njësi *"],
  ["currency", "Monedha nga skedari"],
];
const advancedFields = [
  ["synonyms", "Sinonime"],
  ["technical_specs", "Specifikime teknike"],
  ["category", "Kategoria"],
  ["subcategory", "Nënkategoria"],
  ["supplier", "Furnitori"],
  ["price_date", "Data e çmimit"],
  ["valid_until", "Vlefshmëria"],
  ["vat_included", "Përfshin TVSH"],
  ["vat_rate", "TVSH (%)"],
  ["material_cost", "Kosto materiale"],
  ["labor_cost", "Kosto pune"],
  ["machinery_cost", "Kosto makinerish"],
  ["transport_cost", "Kosto transporti"],
  ["other_cost", "Kosto të tjera"],
  ["price_kind", "Lloji i çmimit"],
  ["supply_included", "Përfshin furnizimin"],
  ["installation_included", "Përfshin instalimin"],
  ["active", "Aktiv"],
  ["notes", "Shënime"],
  ["reason", "Arsyeja / burimi"],
];
interface WorkbookSheet {
  name: string;
  preview: unknown[][];
  header_row: number;
  suggested_mapping: Record<string, number>;
  row_count: number;
  column_count: number;
}
interface PreviewRow {
  source_row: number;
  status: "valid" | "invalid" | "skipped";
  values?: Record<string, any>;
  errors: { field: string; message: string }[];
  warnings: string[];
}
interface PricePreview {
  preview_id: string;
  sheets: WorkbookSheet[];
  sheet: string;
  mapping: Record<string, number>;
  header_row: number;
  rows: PreviewRow[];
  valid_count: number;
  error_count: number;
  skipped_count: number;
  warnings: string[];
  can_commit: boolean;
}

export default function PriceImport({
  onClose,
  onImported,
}: {
  onClose: () => void;
  onImported: (result: { imported?: number; count?: number }) => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null),
    [preview, setPreview] = useState<PricePreview | null>(null),
    [sheet, setSheet] = useState(""),
    [headerRow, setHeaderRow] = useState(0),
    [mapping, setMapping] = useState<Record<string, number>>({}),
    [currency, setCurrency] = useState("ALL"),
    [codePrefix, setCodePrefix] = useState("IMPORT"),
    [dirty, setDirty] = useState(false),
    [busy, setBusy] = useState<"preview" | "commit" | null>(null),
    [error, setError] = useState<unknown>(),
    [rowFilter, setRowFilter] = useState("all"),
    [visibleCount, setVisibleCount] = useState(100);
  const selectedSheet = preview?.sheets.find((s) => s.name === sheet),
    rawRows = selectedSheet?.preview || [];
  const width = Math.max(
    selectedSheet?.column_count || 0,
    ...rawRows.map((r) => r.length),
    1,
  );
  const duplicateColumns = duplicateMapping(mapping),
    missingRequired =
      mapping.unit === undefined ||
      mapping.price === undefined ||
      (mapping.name === undefined && mapping.description === undefined);
  const canCommit =
    !!preview?.can_commit &&
    preview.error_count === 0 &&
    preview.valid_count > 0 &&
    !dirty &&
    !busy &&
    !duplicateColumns &&
    !missingRequired;
  const filteredRows = (preview?.rows || []).filter(
    (r) => rowFilter === "all" || r.status === rowFilter,
  );
  async function requestPreview(selectedFile: File, autodetect = false) {
    setBusy("preview");
    setError(undefined);
    const body = new FormData();
    body.append("file", selectedFile);
    body.append("currency", currency);
    body.append("code_prefix", codePrefix);
    if (!autodetect && sheet) {
      body.append("sheet", sheet);
      body.append("header_row", String(headerRow));
      body.append("mapping", JSON.stringify(mapping));
    }
    try {
      const result = await api<PricePreview>("/prices/import/preview", {
        method: "POST",
        body,
      });
      setPreview(result);
      setSheet(result.sheet);
      setHeaderRow(result.header_row);
      setMapping({ ...result.mapping });
      setDirty(false);
      setVisibleCount(100);
      setRowFilter(result.error_count > 0 ? "invalid" : "all");
    } catch (e) {
      setError(e);
      setDirty(true);
    } finally {
      setBusy(null);
    }
  }
  function selectFile(selectedFile?: File) {
    if (!selectedFile || busy) return;
    setFile(selectedFile);
    setPreview(null);
    setDirty(true);
    requestPreview(selectedFile, true);
  }
  function changeSheet(value: string) {
    setSheet(value);
    setDirty(true);
    setVisibleCount(100);
    const target = preview?.sheets.find((s) => s.name === value);
    setHeaderRow(target?.header_row ?? 0);
    setMapping({ ...target?.suggested_mapping });
  }
  function mappingField([field, label]: string[]) {
    return (
      <Field key={field} label={label}>
        <select
          disabled={!!busy}
          value={mapping[field] ?? ""}
          onChange={(e) => {
            setMapping((previous) => {
              const next = { ...previous };
              if (e.target.value === "") delete next[field];
              else next[field] = Number(e.target.value);
              return next;
            });
            setDirty(true);
          }}
        >
          <option value="">— Pa kolonë —</option>
          {Array.from({ length: width }, (_, i) => (
            <option key={i} value={i}>
              {excelColumn(i)} ·{" "}
              {String(rawRows[headerRow]?.[i] ?? "Pa titull").slice(0, 65)}
            </option>
          ))}
        </select>
      </Field>
    );
  }
  return (
    <Modal
      title="Importo çmime nga Excel"
      onClose={() => {
        if (!busy) onClose();
      }}
      wide
    >
      <p>
        Zgjidhni fletën dhe lidhni kolonat e skedarit. Asnjë çmim nuk ruhet
        përpara konfirmimit tuaj.
      </p>
      <p className="muted">
        Katalogu kërkon çmim real për njësi. BOQ pa çmime importohet te
        projekti, nga “Importo preventivin”; çmimet që mungojnë nuk zëvendësohen
        me zero.
      </p>
      <ErrorBox error={error} />
      <input
        ref={input}
        hidden
        type="file"
        accept=".xlsx,.xlsm,.xls"
        aria-label="Skedari Excel i çmimeve"
        disabled={!!busy}
        onChange={(e) => {
          selectFile(e.target.files?.[0]);
          e.target.value = "";
        }}
      />
      <div
        className="dropzone price-import-upload"
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          selectFile(e.dataTransfer.files[0]);
        }}
      >
        <FileSpreadsheet size={26} />
        <div>
          <strong>{file?.name || "Skedar Excel me çmime"}</strong>
          <small>.xlsx · .xlsm · .xls · Makrot nuk ekzekutohen</small>
        </div>
        <button
          className="secondary"
          disabled={!!busy}
          onClick={() => input.current?.click()}
        >
          <UploadCloud size={15} />
          {file ? "Ndrysho skedarin" : "Zgjidh skedarin"}
        </button>
      </div>
      <div className="form-grid">
        <Field
          label="Monedha kur mungon në skedar"
          hint="Ky është përcaktim monedhe, jo konvertim valutor. Rreshtat me monedhë të shënuar e ruajnë atë."
        >
          <select
            value={currency}
            disabled={!!busy}
            onChange={(e) => {
              setCurrency(e.target.value);
              setDirty(true);
            }}
          >
            <option>ALL</option>
            <option>EUR</option>
          </select>
        </Field>
        <Field
          label="Prefiksi i kodeve të gjeneruara"
          hint="Kur kodi mungon, kodet e propozuara shfaqen në kontrollin e rreshtave përpara ruajtjes."
        >
          <input
            value={codePrefix}
            maxLength={40}
            disabled={!!busy}
            onChange={(e) => {
              setCodePrefix(e.target.value);
              setDirty(true);
            }}
          />
        </Field>
      </div>
      {file && !preview && !busy && (
        <button
          className="secondary"
          onClick={() => requestPreview(file, true)}
        >
          <RefreshCw size={15} />
          Provo kontrollin përsëri
        </button>
      )}
      {busy === "preview" && (
        <div role="status" className="notice">
          Duke lexuar skedarin dhe kontrolluar rreshtat…
        </div>
      )}
      {preview && (
        <>
          <div className="form-grid">
            <Field label="Fleta e çmimeve">
              <select
                value={sheet}
                disabled={!!busy}
                onChange={(e) => changeSheet(e.target.value)}
              >
                {preview.sheets.map((s) => (
                  <option key={s.name}>{s.name}</option>
                ))}
              </select>
            </Field>
            <Field
              label="Rreshti i titujve në Excel"
              hint="Numërimi fillon nga 1. Rreshtat deri te titujt përjashtohen nga importi."
            >
              <input
                type="number"
                min={1}
                max={selectedSheet?.row_count || 100000}
                value={headerRow + 1}
                disabled={!!busy}
                onChange={(e) => {
                  setHeaderRow(Math.max(0, Number(e.target.value) - 1));
                  setDirty(true);
                }}
              />
            </Field>
          </div>
          <h3>Lidhja e kolonave</h3>
          <p className="muted">
            Nevojiten njësia, çmimi dhe të paktën emërtimi ose përshkrimi. Kodi
            mund të gjenerohet.
          </p>
          <div className="mapping-grid price-import-mapping">
            {coreFields.map(mappingField)}
          </div>
          <details className="price-import-advanced">
            <summary>
              Kolona të tjera: kategori, furnitor, TVSH dhe përbërja e kostos
            </summary>
            <div className="mapping-grid">
              {advancedFields.map(mappingField)}
            </div>
          </details>
          {duplicateColumns && (
            <div className="notice">
              Një kolonë është lidhur me disa fusha. Përdorni një kolonë të
              veçantë për secilën fushë ose zgjidhni “Pa kolonë”.
            </div>
          )}
          {missingRequired && (
            <div className="notice">
              Lidhni njësinë, çmimin dhe emërtimin ose përshkrimin për të
              kontrolluar importin.
            </div>
          )}
          <details className="price-import-raw" open>
            <summary>
              Pamja e skedarit dhe titujt e zbuluar ·{" "}
              {selectedSheet?.row_count ?? 0} rreshta
            </summary>
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
                  {rawRows.slice(0, 100).map((row, i) => (
                    <tr
                      key={i}
                      className={i === headerRow ? "header-preview" : ""}
                    >
                      <td>{i + 1}</td>
                      {Array.from({ length: width }, (_, j) => (
                        <td key={j}>{String(row[j] ?? "")}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
          <div className="price-import-recheck">
            <span>
              {dirty
                ? "Konfigurimi ka ndryshuar. Kontrolloni përsëri përpara konfirmimit."
                : "Kontrolli më poshtë pasqyron konfigurimin aktual."}
            </span>
            <button
              className="secondary"
              disabled={
                !!busy ||
                !file ||
                duplicateColumns ||
                missingRequired ||
                !codePrefix.trim()
              }
              onClick={() => file && requestPreview(file)}
            >
              <RefreshCw size={15} />
              Rikontrollo importin
            </button>
          </div>
          {preview.warnings?.map((warning, i) => (
            <div className="notice" key={i}>
              {warning}
            </div>
          ))}
          <section
            className={`price-import-results ${dirty ? "stale-preview" : ""}`}
            aria-label="Kontrolli i rreshtave"
          >
            <div className="price-import-counts">
              <span>
                <b>{preview.valid_count}</b> të vlefshëm
              </span>
              <span className={preview.error_count ? "danger-text" : ""}>
                <b>{preview.error_count}</b> me gabime
              </span>
              <span>
                <b>{preview.skipped_count}</b> të përjashtuar
              </span>
            </div>
            <Field label="Shfaq rreshtat">
              <select
                value={rowFilter}
                onChange={(e) => {
                  setRowFilter(e.target.value);
                  setVisibleCount(100);
                }}
              >
                <option value="all">Të gjithë</option>
                <option value="invalid">Me gabime</option>
                <option value="valid">Të vlefshëm</option>
                <option value="skipped">Të përjashtuar</option>
              </select>
            </Field>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Rreshti / statusi</th>
                    <th>Kodi i propozuar</th>
                    <th>Emërtimi / përshkrimi</th>
                    <th>Njësia</th>
                    <th>Çmimi / monedha</th>
                    <th>Gabime dhe paralajmërime</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredRows.slice(0, visibleCount).map((row, i) => (
                    <tr key={`${row.source_row}-${i}`}>
                      <td>
                        {row.source_row}
                        <span
                          className={`badge ${row.status === "valid" ? "approved" : row.status === "invalid" ? "rejected" : "inactive"}`}
                        >
                          {row.status === "valid"
                            ? "I vlefshëm"
                            : row.status === "invalid"
                              ? "Me gabime"
                              : "Përjashtuar"}
                        </span>
                      </td>
                      <td className="code">{row.values?.code || "—"}</td>
                      <td>
                        <strong>
                          {row.values?.name || row.values?.description || "—"}
                        </strong>
                        {row.values?.name && row.values?.description && (
                          <span className="cell-sub">
                            {row.values.description}
                          </span>
                        )}
                      </td>
                      <td>{row.values?.unit || "—"}</td>
                      <td className="numeric">
                        {row.values?.price === undefined ||
                        row.values?.price === null
                          ? "—"
                          : String(row.values.price)}
                        <span className="cell-sub">
                          {row.values?.currency || "—"}
                        </span>
                      </td>
                      <td>
                        {row.errors?.map((e, j) => (
                          <span
                            className="warning-text danger-text"
                            key={`e-${j}`}
                          >
                            {e.field ? `${e.field}: ` : ""}
                            {e.message}
                          </span>
                        ))}
                        {row.warnings?.map((warning, j) => (
                          <span className="warning-text" key={`w-${j}`}>
                            {warning}
                          </span>
                        ))}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {filteredRows.length === 0 && (
              <p className="muted">Nuk ka rreshta për këtë filtër.</p>
            )}
            {filteredRows.length > visibleCount && (
              <button
                className="secondary"
                onClick={() => setVisibleCount(visibleCount + 100)}
              >
                Shfaq edhe 100 rreshta
              </button>
            )}
          </section>
          {preview.error_count > 0 && (
            <div className="error">
              Importi bllokohet deri në zgjidhjen e të gjitha gabimeve.
              Korrigjoni kolonat ose skedarin dhe rikontrolloni. Asnjë nëngrup
              rreshtash nuk ruhet automatikisht.
            </div>
          )}
          {!dirty && canCommit && (
            <div className="notice">
              <CheckCircle2 size={16} />
              Kontrolloni kodet e propozuara dhe monedhat e çdo rreshti.
              Konfirmimi ruan {preview.valid_count} çmime të reja.
            </div>
          )}
        </>
      )}
      <footer>
        <button className="secondary" disabled={!!busy} onClick={onClose}>
          Anulo
        </button>
        <button
          disabled={!canCommit}
          onClick={async () => {
            if (!preview || !canCommit) return;
            setBusy("commit");
            setError(undefined);
            try {
              const result = await send("/prices/import/commit", "POST", {
                preview_id: preview.preview_id,
                confirm: true,
              });
              onImported(result);
            } catch (e) {
              setError(e);
              setDirty(true);
            } finally {
              setBusy(null);
            }
          }}
        >
          {busy === "commit" ? "Duke ruajtur…" : "Konfirmo importin"}
        </button>
      </footer>
    </Modal>
  );
}
