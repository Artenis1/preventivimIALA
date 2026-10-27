import { afterEach, describe, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import App from "./App";
import Prices from "./Prices";
import Import from "./Import";
import Review from "./Review";
const json = (data: any, status = 200) => ({
  ok: status < 400,
  status,
  json: async () => data,
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
describe("Albanian workspace", () => {
  it("requires authentication and sends registration through backend", async () => {
    const calls: any[] = [];
    let loggedIn = false;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, options: any = {}) => {
        calls.push([url, options]);
        if (url === "/api/auth/register") {
          loggedIn = true;
          return json({ id: 1 });
        }
        if (url === "/api/auth/me")
          return loggedIn
            ? json({ display_name: "Ana", email: "ana@example.com" })
            : json({ detail: "Hyni" }, 401);
        if (url === "/api/dashboard")
          return json({
            total_projects: 0,
            draft_estimates: 0,
            finalized_estimates: 0,
            total_prices: 0,
            awaiting_approval: 0,
            unmatched_rows: 0,
            total_values: { EUR: "0", ALL: "0" },
            recent_prices: [],
            frequently_used: [],
          });
        return json([]);
      }),
    );
    render(<App />);
    await screen.findByText("Hyni në hapësirën tuaj");
    fireEvent.click(screen.getByRole("button", { name: "Regjistrohuni" }));
    fireEvent.change(screen.getByLabelText("Emri i plotë"), {
      target: { value: "Ana" },
    });
    fireEvent.change(screen.getByLabelText("Adresa e emailit"), {
      target: { value: "ana@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Fjalëkalimi"), {
      target: { value: "test-password-123" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Krijo llogarinë" }));
    await screen.findByText("Përmbledhja e punës");
    expect(
      JSON.parse(calls.find((c) => c[0] === "/api/auth/register")[1].body),
    ).toEqual({
      email: "ana@example.com",
      password: "test-password-123",
      display_name: "Ana",
    });
    expect(
      screen.getByRole("navigation").querySelectorAll("button"),
    ).toHaveLength(10);
  });
  it("updates price fields without sending database-only metadata", async () => {
    const item = {
      id: 7,
      owner_id: 1,
      version: 2,
      attachments: [],
      embedding_model: "example",
      code: "FV-01",
      name: "Panel FV",
      description: "Furnizim panel FV",
      synonyms: "",
      technical_specs: "450Wp",
      category: "Module fotovoltaike",
      subcategory: "",
      unit: "copë",
      price: "100",
      currency: "EUR",
      supplier: "",
      price_date: "2026-10-27",
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
    const fetchMock = vi.fn(async (_url: string, options: any = {}) =>
      options.method === "PUT" ? json(item) : json([item]),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<Prices mode="prices" />);
    fireEvent.click(
      await screen.findByRole("button", { name: "Redakto FV-01" }),
    );
    const dialog = screen.getByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Arsyeja e ndryshimit"), {
      target: { value: "Ofertë e re" },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: "Ruaj zërin" }));
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some((c) => (c[1] as any)?.method === "PUT"),
      ).toBe(true),
    );
    const payload = JSON.parse(
      (
        fetchMock.mock.calls.find(
          (c) => (c[1] as any)?.method === "PUT",
        )![1] as any
      ).body,
    );
    expect(payload.valid_until).toBe("");
    expect(payload.price).toBe("100");
    expect(payload.reason).toBe("Ofertë e re");
    for (const key of [
      "id",
      "owner_id",
      "version",
      "attachments",
      "embedding_model",
    ])
      expect(payload).not.toHaveProperty(key);
  });
  it("previews workbook and allows manual column mapping before committing", async () => {
    const fetchMock = vi.fn(async (url: string, options: any = {}) => {
      if (url === "/api/projects")
        return json([{ id: 1, name: "Projekt FV", currency: "EUR" }]);
      if (options.body instanceof FormData)
        return json({
          id: 3,
          sheets: [
            {
              name: "Preventivi",
              header_row: 0,
              suggested_mapping: { description: 1, unit: 2, quantity: 3 },
              preview: [
                ["Nr", "Punimi", "Njësia", "Sasia"],
                ["1", "Montim FV", "copë", 5],
              ],
            },
          ],
        });
      return json({
        imported: 1,
        rejected: [{ source_row: 3, reason: "Sasi e pavlefshme" }],
      });
    });
    vi.stubGlobal("fetch", fetchMock);
    const { container } = render(
      <Import projectId={1} onDone={vi.fn()} onProject={vi.fn()} />,
    );
    await screen.findByText("Projekt FV · EUR");
    const input = container.querySelector("input[type=file]")!;
    fireEvent.change(input, {
      target: { files: [new File(["data"], "boq.xlsx")] },
    });
    await screen.findByText("Kontrolloni lidhjen e kolonave");
    expect(screen.getByLabelText("Përshkrimi i punës *")).toHaveValue("1");
    fireEvent.change(screen.getByLabelText("Nr. i zërit"), {
      target: { value: "0" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Importo rreshtat" }));
    await screen.findByText("Importi përfundoi");
    const commit = fetchMock.mock.calls.find((c) => c[0].endsWith("/commit"))!;
    expect(JSON.parse((commit[1] as any).body)).toEqual({
      sheet: "Preventivi",
      header_row: 0,
      mapping: { description: 1, unit: 2, quantity: 3, item_number: 0 },
    });
    expect(screen.getByText("Sasi e pavlefshme")).toBeInTheDocument();
  });
  it("requires explicit confirmation before bulk approving eligible matches", async () => {
    const row = {
      id: 12,
      item_number: "1",
      description: "Montim FV",
      unit: "copë",
      quantity: "2",
      unit_price: null,
      original_unit_price: null,
      total: null,
      item_id: null,
      decision: "pending",
      notes: "",
      match_result: {
        suggested_item_id: 5,
        classification: "high",
        confidence: 0.98,
        discrepancies: [],
      },
    };
    const project = {
      id: 1,
      name: "FV",
      currency: "EUR",
      status: "draft",
      vat_rate: "20",
      overhead_percent: "0",
      profit_percent: "0",
      discount_percent: "0",
    };
    const fetchMock = vi.fn(async (url: string) =>
      url === "/api/projects"
        ? json([project])
        : url === "/api/prices"
          ? json([])
          : url.endsWith("approve-preview")
            ? json({ rows: [row], confirmation_required: true })
            : json({
                project,
                rows: [row],
                totals: { grand_total: "0" },
                versions: [],
              }),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(
      <Review
        projectId={1}
        mode="review"
        onProject={vi.fn()}
        onNavigate={vi.fn()}
      />,
    );
    await screen.findByText("Montim FV");
    fireEvent.click(screen.getByRole("button", { name: "Mirato në grup" }));
    await screen.findByRole("dialog");
    expect(
      fetchMock.mock.calls.some((c) => c[0].endsWith("approve-bulk")),
    ).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: "Po, konfirmoj" }));
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some((c) => c[0].endsWith("approve-bulk")),
      ).toBe(true),
    );
  });
});
