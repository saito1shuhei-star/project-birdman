// 型付きAPIクライアント(API_SPEC.md)。物理計算はここに書かない(計算はすべてバックエンド)。

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export type Quantity = { value: number; unit: string };

export type Project = {
  id: string;
  team_name: string;
  aircraft_name: string;
  design_year: number;
  category: string;
  design_lead: string;
  unit_system: string;
  version: string;
  design_goal: string;
  status: string;
  created_at: string;
  updated_at: string;
};

export type ProjectCreate = Omit<
  Project,
  "id" | "status" | "created_at" | "updated_at"
>;

export type RequirementSpec = {
  pilot_mass: Quantity;
  airframe_mass_target: Quantity;
  pilot_power_sustained: Quantity;
  pilot_power_max?: Quantity | null;
  target_cruise_speed: Quantity;
  target_distance?: Quantity | null;
  wingspan_limit: Quantity;
  air_density: Quantity;
  wind_speed_limit: Quantity;
  flight_altitude_limit: Quantity;
  pilot_age?: number | null;
  cl_cruise: number;
  cl_max: number;
  cd0: number;
  oswald_efficiency: number;
  propeller_efficiency: number;
  drivetrain_efficiency: number;
};

export type RequirementSpecOut = {
  id: string;
  project_id: string;
  revision: number;
  created_at: string;
  spec: RequirementSpec;
};

export type CalcWarning = {
  code: string;
  severity: "info" | "warning" | "violation";
  message: string;
};

export type FormulaRecord = {
  symbol: string;
  name: string;
  expression: string;
  substitutions: Record<string, string>;
  result: Quantity;
  source: string;
};

export type AssumptionRecord = {
  id: string;
  name: string;
  value: string;
  rationale: string;
};

export type SolverExecution = {
  solver_name: string;
  solver_version: string;
  execution_mode: "real" | "mock" | "imported" | "analytical_estimate";
  input_hash: string;
  started_at: string;
  finished_at: string;
  result_status: string;
};

export type SizingRun = {
  id: string;
  project_id: string;
  requirement_revision: number;
  input_hash: string;
  outputs: {
    quantities: Record<string, Quantity>;
    formulas: FormulaRecord[];
    assumptions: AssumptionRecord[];
    warnings: CalcWarning[];
  };
  execution: SolverExecution;
  created_at: string;
};

export type WingSection = {
  spanwise_position: Quantity;
  chord: Quantity;
  twist_deg: number;
  airfoil: string;
};

export type WingPlanform = { sections: WingSection[] };

export type WingPlanformOut = {
  id: string;
  project_id: string;
  revision: number;
  created_at: string;
  planform: WingPlanform;
  derived: Record<string, Quantity>;
};

export type AeroPolarPoint = {
  alpha_deg: number;
  cl: number;
  cd: number;
  cm: number;
  stalled: boolean;
};

export type AeroAnalysisRun = {
  id: string;
  project_id: string;
  solver_name: string;
  planform_revision: number | null;
  requirement_revision: number | null;
  input_hash: string;
  request: {
    airfoil_name: string;
    aspect_ratio: number;
    oswald_efficiency: number;
    parasite_drag_coefficient: number;
    cl_max: number;
    alpha_min_deg: number;
    alpha_max_deg: number;
    alpha_step_deg: number;
  };
  outputs: {
    polar: AeroPolarPoint[];
    max_lift_to_drag: number;
    cl_at_max_lift_to_drag: number;
    warnings: CalcWarning[];
  };
  execution: SolverExecution;
  created_at: string;
};

export type MassItem = {
  id: string;
  project_id: string;
  name: string;
  category: string;
  mass: Quantity;
  position_x: Quantity;
  position_y: Quantity;
  position_z: Quantity;
  material: string;
  source: "estimated" | "measured";
  uncertainty?: Quantity | null;
  owner: string;
  created_at: string;
  updated_at: string;
};

export type MassProperties = {
  quantities: Record<string, Quantity>;
  breakdown: {
    category: string;
    mass: Quantity;
    fraction: number;
    item_count: number;
  }[];
  warnings: CalcWarning[];
  estimated_item_count: number;
  measured_item_count: number;
};

export type AnalysisRunLite = {
  id: string;
  outputs: {
    quantities: Record<string, Quantity>;
    warnings: CalcWarning[];
  };
  execution: SolverExecution;
  created_at: string;
};

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail =
        typeof body.detail === "string"
          ? body.detail
          : JSON.stringify(body.detail);
    } catch {
      // レスポンスがJSONでない場合はstatusTextのまま
    }
    throw new Error(`HTTP ${res.status}: ${detail}`);
  }
  return (await res.json()) as T;
}

export const reportUrl = (runId: string) =>
  `${API_BASE}/api/sizing-runs/${runId}/report`;
