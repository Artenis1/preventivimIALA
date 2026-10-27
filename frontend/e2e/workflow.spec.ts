import { test, expect } from "@playwright/test";
import { randomUUID } from "node:crypto";

test("Albanian engineer workflow: registration, catalog, BOQ, approval and Excel export", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await page
    .getByRole("button", { name: "Regjistrohuni", exact: true })
    .click();
  await page.getByLabel("Emri i plotë").fill("Inxhinier Test");
  await page
    .getByLabel("Adresa e emailit")
    .fill(`smoke-${randomUUID()}@example.test`);
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
  await page.getByRole("button", { name: "Shto zë", exact: true }).click();
  await page.getByLabel("Kodi unik").fill("E2E-PV");
  await page.getByLabel("Emërtimi", { exact: true }).fill("Modul FV test");
  await page
    .getByLabel("Përshkrimi i standardizuar")
    .fill("Furnizim modul FV 550 Wp");
  await page.getByLabel("Njësia", { exact: true }).fill("copë");
  await page.getByLabel("Çmimi për njësi", { exact: true }).fill("100");
  await page.getByRole("button", { name: "Ruaj zërin", exact: true }).click();
  await expect(page.getByText("E2E-PV", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Projektet", exact: true }).click();
  await page.getByRole("button", { name: "Projekt i ri", exact: true }).click();
  await page.getByLabel("Emri i projektit").fill("Projekt FV test");
  await page
    .getByRole("button", { name: "Ruaj projektin", exact: true })
    .click();
  await expect(page.getByLabel("Projekti aktiv")).toContainText(
    "Projekt FV test",
  );
  const api = page.request;
  const projects = await (await api.get("/api/projects")).json();
  const project = projects.find((p: any) => p.name === "Projekt FV test");
  await page
    .getByRole("button", { name: "Importo preventivin", exact: true })
    .click();
  await page
    .getByLabel("Projekti", { exact: true })
    .selectOption(String(project.id));
  await page.locator("input[type=file]").setInputFiles("e2e/fixtures/boq.xlsx");
  await expect(
    page.getByRole("heading", { name: "Kontrolloni lidhjen e kolonave" }),
  ).toBeVisible();
  await page.getByLabel("Kodi i zërit", { exact: true }).selectOption("2");
  await page
    .getByLabel("Përshkrimi i punës *", { exact: true })
    .selectOption("1");
  await page.getByLabel("Njësia *", { exact: true }).selectOption("4");
  await page.getByLabel("Sasia *", { exact: true }).selectOption("3");
  await page
    .getByRole("button", { name: "Importo rreshtat", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Importi përfundoi" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Vazhdo te përputhjet", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Gjej përputhjet", exact: true })
    .click();
  // Approval is explicitly confirmed in the review dialog; no suggestion is a final price.
  await expect(
    page.getByRole("button", { name: "Gjej përputhjet", exact: true }),
  ).toBeEnabled();
  const current = await (await api.get(`/api/projects/${project.id}`)).json();
  expect(current.rows[0].unit_price).toBeNull();
  await page
    .getByRole("button", { name: "Rishiko zërin ", exact: false })
    .click();
  await page.getByLabel("Vendimi", { exact: true }).selectOption("approved");
  await page
    .getByRole("button", { name: "Ruaj vendimin", exact: true })
    .click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await page.getByRole("button", { name: "Preventivat", exact: true }).click();
  await expect(page.locator(".grand-total")).toContainText("300");
  await page
    .getByRole("button", { name: "Finalizo preventivin", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Po, konfirmoj", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Rihap për ndryshime", exact: true }),
  ).toBeVisible();
  const download = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "Excel standard", exact: true })
    .click();
  expect((await download).suggestedFilename()).toMatch(/\.xlsx$/);
  await page.screenshot({
    path: "test-results/estimate-desktop.png",
    fullPage: true,
    animations: "disabled",
  });
  await page.setViewportSize({ width: 768, height: 1024 });
  await page.getByRole("button", { name: "Hap menunë", exact: true }).click();
  await page
    .getByRole("button", { name: "Cilësimet", exact: true })
    .first()
    .click();
  await expect(
    page.getByRole("heading", { name: "Cilësimet", exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/settings-tablet.png",
    fullPage: true,
    animations: "disabled",
  });
  expect(errors).toEqual([]);
});
