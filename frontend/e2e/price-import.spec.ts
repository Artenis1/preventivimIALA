import { test, expect } from "@playwright/test";
import { randomUUID } from "node:crypto";

for (const extension of ["xlsx", "xls"]) {
  test(`Price catalog ${extension}: titles, Albanian aliases, preview and explicit save`, async ({
    page,
  }) => {
    await page.goto("/");
    await page
      .getByRole("button", { name: "Regjistrohuni", exact: true })
      .click();
    await page.getByLabel("Emri i plotë").fill("Import Test");
    await page
      .getByLabel("Adresa e emailit")
      .fill(`import-${randomUUID()}@example.test`);
    await page.getByLabel("Fjalëkalimi", { exact: false }).fill(randomUUID());
    await page
      .getByRole("button", { name: "Krijo llogarinë", exact: true })
      .click();
    await expect(
      page.getByRole("heading", { name: "Përmbledhja e punës" }),
    ).toBeVisible();
    await page
      .getByRole("button", { name: "Baza e çmimeve", exact: true })
      .click();
    await page.getByRole("button", { name: "Importo", exact: true }).click();
    const dialog = page.getByRole("dialog", {
      name: "Importo çmime nga Excel",
    });
    const fixture =
      extension === "xls"
        ? "legacy_albanian.xls"
        : "albanian_merged_title.xlsx";
    await dialog
      .getByLabel("Skedari Excel i çmimeve")
      .setInputFiles(`../backend/tests/fixtures/price_import/${fixture}`);
    await expect(dialog.getByLabel("Rreshti i titujve në Excel")).toHaveValue(
      "3",
    );
    await expect(
      dialog.getByRole("button", { name: "Konfirmo importin", exact: true }),
    ).toBeEnabled();
    expect(await (await page.request.get("/api/prices")).json()).toEqual([]);
    await expect(dialog.getByLabel("Kontrolli i rreshtave")).toContainText(
      "Çelik për armim",
    );
    await dialog.getByLabel("Monedha kur mungon në skedar").selectOption("EUR");
    await expect(
      dialog.getByRole("button", { name: "Konfirmo importin", exact: true }),
    ).toBeDisabled();
    await dialog
      .getByRole("button", { name: "Rikontrollo importin", exact: true })
      .click();
    await expect(
      dialog.getByRole("button", { name: "Konfirmo importin", exact: true }),
    ).toBeEnabled();
    const response = page.waitForResponse(
      (r) =>
        r.url().endsWith("/api/prices/import/commit") &&
        r.request().method() === "POST",
    );
    await dialog
      .getByRole("button", { name: "Konfirmo importin", exact: true })
      .click();
    expect((await response).status()).toBe(200);
    await expect(dialog).not.toBeVisible();
    const prices = await (await page.request.get("/api/prices")).json();
    expect(prices.length).toBeGreaterThan(0);
    expect(prices[0].currency).toBe("EUR");
    expect(prices[0].description).toBe(prices[0].name);
    await expect(
      page.getByText("Çelik për armim", { exact: true }).first(),
    ).toBeVisible();
  });
}
