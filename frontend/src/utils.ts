export const money = (value: unknown, currency = "EUR") =>
  value === null || value === undefined || value === ""
    ? "—"
    : new Intl.NumberFormat("sq-AL", { style: "currency", currency }).format(
        Number(value),
      );
export const number = (value: unknown) =>
  value === null || value === undefined
    ? "—"
    : new Intl.NumberFormat("sq-AL", { maximumFractionDigits: 4 }).format(
        Number(value),
      );
export const list = <T>(value: T[] | { items?: T[]; results?: T[] }): T[] =>
  Array.isArray(value) ? value : value?.items || value?.results || [];
export function eligibleRows(rows: any[]) {
  return rows.filter(
    (r) =>
      r.decision !== "approved" &&
      r.match_result?.classification === "high" &&
      r.match_result?.unit_compatible !== false &&
      !r.match_result?.discrepancies?.length,
  );
}
export function projectPayload(form: Record<string, any>) {
  return Object.fromEntries(
    Object.entries(form).filter(
      ([key]) => !["id", "status", "created_at", "owner_id"].includes(key),
    ),
  );
}

export function excelColumn(index: number): string {
  let label = "";
  for (let n = index + 1; n > 0; n = Math.floor((n - 1) / 26)) {
    label = String.fromCharCode(65 + ((n - 1) % 26)) + label;
  }
  return label;
}
export function duplicateMapping(mapping: Record<string, number>): boolean {
  const columns = Object.values(mapping);
  return new Set(columns).size !== columns.length;
}
