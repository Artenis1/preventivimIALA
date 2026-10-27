import { afterEach, describe, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import PriceImport from "./PriceImport";
import Prices from "./Prices";
const json = (data: any, status = 200) => ({
  ok: status < 400,
  status,
  json: async () => data,
});
const sheet = {
  name: "Katalogu 2026",
  preview: [
    ["Nr", "Emri", "Njësia", "Çmimi", "Furnitori"],
    [1, "Beton C25/30", "m³", "12,50", "Test"],
  ],
  header_row: 0,
  suggested_mapping: { name: 1, unit: 2, price: 3, supplier: 4 },
  row_count: 2,
  column_count: 5,
};
function preview(overrides: Record<string, any> = {}) {
  return {
    preview_id: "preview-1",
    sheets: [sheet, { ...sheet, name: "Çmime FV" }],
    sheet: sheet.name,
    mapping: { ...sheet.suggested_mapping },
    header_row: 0,
    rows: [
      {
        source_row: 2,
        status: "valid",
        values: {
          code: "IMPORT-0002",
          name: "Beton C25/30",
          description: "Beton C25/30",
          unit: "m³",
          price: "12.50",
          currency: "ALL",
        },
        errors: [],
        warnings: ["Kodi u gjenerua sepse mungon në skedar."],
      },
    ],
    valid_count: 1,
    error_count: 0,
    skipped_count: 0,
    warnings: [],
    can_commit: true,
    ...overrides,
  };
}
function selectFile(name = "katalog.xlsx") {
  const file = new File(["workbook bytes"], name);
  fireEvent.change(screen.getByLabelText("Skedari Excel i çmimeve"), {
    target: { files: [file] },
  });
  return file;
}
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
describe("Price Excel import", () => {
  it("opens preview workflow from Price Database without directly writing prices", async () => {
    const calls: any[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, options: any = {}) => {
        calls.push([url, options]);
        return url.includes("preview") ? json(preview()) : json([]);
      }),
    );
    render(<Prices mode="prices" />);
    await screen.findByText("Asnjë zë nuk u gjet.");
    fireEvent.click(screen.getByRole("button", { name: "Importo" }));
    expect(
      screen.getByRole("dialog", { name: "Importo çmime nga Excel" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Konfirmo importin" }),
    ).toBeDisabled();
    selectFile("çmimet.xls");
    await screen.findByText("IMPORT-0002");
    expect(screen.getByLabelText("Fleta e çmimeve")).toHaveValue(
      "Katalogu 2026",
    );
    expect(calls.some(([url]) => url === "/api/prices/import")).toBe(false);
    expect(calls.some(([url]) => url.endsWith("/commit"))).toBe(false);
    const body = calls.find(([url]) => url.endsWith("/preview"))[1].body;
    expect(body.get("file").name).toBe("çmimet.xls");
    expect(body.get("currency")).toBe("ALL");
    expect(body.get("sheet")).toBe(null);
    expect(body.get("mapping")).toBe(null);
    expect(screen.getByLabelText("Skedari Excel i çmimeve")).toHaveAttribute(
      "accept",
      ".xlsx,.xlsm,.xls",
    );
  });
  it("invalidates a preview when mapping changes and preserves detected advanced fields on recheck", async () => {
    const fetchMock = vi.fn(async () => json(preview()));
    vi.stubGlobal("fetch", fetchMock);
    render(<PriceImport onClose={vi.fn()} onImported={vi.fn()} />);
    const file = selectFile();
    await screen.findByText("IMPORT-0002");
    expect(
      screen.getByRole("button", { name: "Konfirmo importin" }),
    ).toBeEnabled();
    fireEvent.change(screen.getByLabelText("Kodi"), { target: { value: "0" } });
    expect(
      screen.getByRole("button", { name: "Konfirmo importin" }),
    ).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Monedha kur mungon në skedar"), {
      target: { value: "EUR" },
    });
    fireEvent.change(screen.getByLabelText("Prefiksi i kodeve të gjeneruara"), {
      target: { value: "PV" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Rikontrollo importin" }),
    );
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Konfirmo importin" }),
      ).toBeEnabled(),
    );
    const body = (fetchMock.mock.calls[1] as any[])[1].body;
    expect(body.get("file")).toBe(file);
    expect(body.get("sheet")).toBe("Katalogu 2026");
    expect(body.get("header_row")).toBe("0");
    expect(body.get("currency")).toBe("EUR");
    expect(body.get("code_prefix")).toBe("PV");
    expect(JSON.parse(body.get("mapping"))).toEqual({
      name: 1,
      unit: 2,
      price: 3,
      supplier: 4,
      code: 0,
    });
  });
  it("requires a new server preview when the selected sheet or header changes", async () => {
    const fetchMock = vi.fn(async () => json(preview()));
    vi.stubGlobal("fetch", fetchMock);
    render(<PriceImport onClose={vi.fn()} onImported={vi.fn()} />);
    selectFile();
    await screen.findByText("IMPORT-0002");
    fireEvent.change(screen.getByLabelText("Fleta e çmimeve"), {
      target: { value: "Çmime FV" },
    });
    fireEvent.change(screen.getByLabelText("Rreshti i titujve në Excel"), {
      target: { value: "2" },
    });
    expect(
      screen.getByRole("button", { name: "Konfirmo importin" }),
    ).toBeDisabled();
    fireEvent.click(
      screen.getByRole("button", { name: "Rikontrollo importin" }),
    );
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    const body = (fetchMock.mock.calls[1] as any[])[1].body;
    expect(body.get("sheet")).toBe("Çmime FV");
    expect(body.get("header_row")).toBe("1");
  });
  it("shows row-specific errors and prevents committing a valid subset", async () => {
    const result = preview({
      error_count: 1,
      valid_count: 1,
      can_commit: false,
      rows: [
        ...preview().rows,
        {
          source_row: 8,
          status: "invalid",
          values: {
            name: "Çmim i gabuar",
            price: "jo numër",
            currency: "euro",
          },
          errors: [
            { field: "price", message: "Çmimi nuk është numër i vlefshëm" },
            { field: "code", message: "Kodi ekziston" },
          ],
          warnings: [],
        },
      ],
    });
    const fetchMock = vi.fn(async () => json(result));
    vi.stubGlobal("fetch", fetchMock);
    render(<PriceImport onClose={vi.fn()} onImported={vi.fn()} />);
    selectFile();
    await screen.findByText("price: Çmimi nuk është numër i vlefshëm");
    expect(screen.getByText("code: Kodi ekziston")).toBeInTheDocument();
    expect(screen.getByText("jo numër")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Konfirmo importin" }),
    ).toBeDisabled();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(
      screen.getByText(/Asnjë nëngrup rreshtash nuk ruhet/),
    ).toBeInTheDocument();
  });
  it("shows the exact decimal price that the user will approve", async () => {
    const result = preview();
    result.rows[0].values.price = "123.456789";
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => json(result)),
    );
    render(<PriceImport onClose={vi.fn()} onImported={vi.fn()} />);
    selectFile();
    expect(await screen.findByText("123.456789")).toBeInTheDocument();
    expect(
      screen.getByText(/BOQ pa çmime importohet te projekti/),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Konfirmo importin" }),
    ).toBeEnabled();
  });
  it("saves only after explicit confirmation of the clean preview token", async () => {
    const imported = vi.fn(),
      fetchMock = vi.fn(async (url: string) =>
        url.endsWith("/commit") ? json({ imported: 1 }) : json(preview()),
      );
    vi.stubGlobal("fetch", fetchMock);
    render(<PriceImport onClose={vi.fn()} onImported={imported} />);
    selectFile();
    await screen.findByText("IMPORT-0002");
    expect(
      screen.getByText("ALL", { selector: "span.cell-sub" }),
    ).toBeInTheDocument();
    expect(imported).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Konfirmo importin" }));
    await waitFor(() => expect(imported).toHaveBeenCalledWith({ imported: 1 }));
    const commit = fetchMock.mock.calls.find(([url]) =>
      url.endsWith("/commit"),
    ) as any[];
    expect(JSON.parse(commit[1].body)).toEqual({
      preview_id: "preview-1",
      confirm: true,
    });
  });
  it("cancels a validated preview without saving it", async () => {
    const close = vi.fn(),
      fetchMock = vi.fn(async () => json(preview()));
    vi.stubGlobal("fetch", fetchMock);
    render(<PriceImport onClose={close} onImported={vi.fn()} />);
    selectFile();
    await screen.findByText("IMPORT-0002");
    fireEvent.click(screen.getByRole("button", { name: "Anulo" }));
    expect(close).toHaveBeenCalledOnce();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
  it("keeps duplicate column mappings from being revalidated or confirmed", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => json(preview())),
    );
    render(<PriceImport onClose={vi.fn()} onImported={vi.fn()} />);
    selectFile();
    await screen.findByText("IMPORT-0002");
    fireEvent.change(screen.getByLabelText("Kodi"), { target: { value: "1" } });
    expect(
      screen.getByRole("button", { name: "Konfirmo importin" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Rikontrollo importin" }),
    ).toBeDisabled();
    expect(
      screen.getByText(/Një kolonë është lidhur me disa fusha/),
    ).toBeInTheDocument();
  });
  it("requires revalidation after a commit rejection rather than retrying a stale token", async () => {
    const fetchMock = vi.fn(async (url: string) =>
      url.endsWith("/commit")
        ? json({ detail: "Kodi tashmë ekziston" }, 409)
        : json(preview()),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<PriceImport onClose={vi.fn()} onImported={vi.fn()} />);
    selectFile();
    await screen.findByText("IMPORT-0002");
    fireEvent.click(screen.getByRole("button", { name: "Konfirmo importin" }));
    await screen.findByText("Kodi tashmë ekziston");
    expect(
      screen.getByRole("button", { name: "Konfirmo importin" }),
    ).toBeDisabled();
  });
});
