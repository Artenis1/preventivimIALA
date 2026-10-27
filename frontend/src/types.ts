export interface Price {
  id: number;
  code: string;
  name: string;
  description: string;
  synonyms: string;
  technical_specs: string;
  category: string;
  subcategory: string;
  unit: string;
  price: string;
  currency: string;
  supplier: string;
  price_date: string;
  valid_until: string | null;
  vat_included: boolean;
  vat_rate: string;
  material_cost: string;
  labor_cost: string;
  machinery_cost: string;
  transport_cost: string;
  other_cost: string;
  notes: string;
  active: boolean;
  price_kind: string;
  supply_included: boolean;
  installation_included: boolean;
  [key: string]: any;
}
export interface Project {
  id: number;
  name: string;
  client: string;
  location: string;
  project_type: string;
  currency: string;
  vat_rate: string;
  overhead_percent: string;
  profit_percent: string;
  discount_percent: string;
  other_charges: string;
  calculation_base: string;
  status: string;
  notes: string;
  [key: string]: any;
}
export interface BoqRow {
  id: number;
  item_number: string;
  code?: string;
  description: string;
  unit: string;
  quantity: string;
  unit_price: string | null;
  original_unit_price: string | null;
  total: string | null;
  item_id: number | null;
  decision: string;
  notes: string;
  match_result: any;
  [key: string]: any;
}
export type Page =
  | "dashboard"
  | "prices"
  | "materials"
  | "labor"
  | "import"
  | "review"
  | "projects"
  | "estimates"
  | "history"
  | "settings";
