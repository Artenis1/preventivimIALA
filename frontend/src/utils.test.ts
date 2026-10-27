import { describe, expect, it } from "vitest";
import { duplicateMapping, excelColumn, money } from "./utils";
describe("Workbook mapping", () => {
  it("identifies Excel columns beyond Z", () => {
    expect([0, 25, 26, 51, 52, 701].map(excelColumn)).toEqual([
      "A",
      "Z",
      "AA",
      "AZ",
      "BA",
      "ZZ",
    ]);
  });
  it("requires a separate source column for each mapped field", () => {
    expect(duplicateMapping({ description: 1, quantity: 2, unit: 3 })).toBe(
      false,
    );
    expect(duplicateMapping({ description: 1, code: 1 })).toBe(true);
  });
  it("does not present missing monetary amounts as zero", () => {
    expect(money(null, "ALL")).toBe("—");
    expect(money("0", "ALL")).not.toBe("—");
  });
});
