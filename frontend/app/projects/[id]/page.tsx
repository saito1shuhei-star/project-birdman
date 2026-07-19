"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import {
  AeroAnalysisRun,
  AnalysisRunLite,
  API_BASE,
  apiFetch,
  CalcWarning,
  MassItem,
  MassProperties,
  Project,
  Quantity,
  reportUrl,
  RequirementSpec,
  RequirementSpecOut,
  SizingRun,
  SolverExecution,
  WingPlanformOut,
} from "@/lib/api";

// 入力フォームの状態(文字列で保持し、送信時に数値化する)
type QuantityForm = { value: string; unit: string };

type ReqForm = {
  pilot_mass: QuantityForm;
  airframe_mass_target: QuantityForm;
  pilot_power_sustained: QuantityForm;
  target_cruise_speed: QuantityForm;
  wingspan_limit: QuantityForm;
  air_density: QuantityForm;
  wind_speed_limit: QuantityForm;
  flight_altitude_limit: QuantityForm;
  pilot_age: string;
  cl_cruise: string;
  cl_max: string;
  cd0: string;
  oswald_efficiency: string;
  propeller_efficiency: string;
  drivetrain_efficiency: string;
};

const DEFAULT_FORM: ReqForm = {
  pilot_mass: { value: "60", unit: "kg" },
  airframe_mass_target: { value: "40", unit: "kg" },
  pilot_power_sustained: { value: "250", unit: "W" },
  target_cruise_speed: { value: "7.5", unit: "m/s" },
  wingspan_limit: { value: "30", unit: "m" },
  air_density: { value: "1.225", unit: "kg/m^3" },
  wind_speed_limit: { value: "5.0", unit: "m/s" },
  flight_altitude_limit: { value: "10.0", unit: "m" },
  pilot_age: "",
  cl_cruise: "1.0",
  cl_max: "1.4",
  cd0: "0.020",
  oswald_efficiency: "0.90",
  propeller_efficiency: "0.80",
  drivetrain_efficiency: "0.95",
};

// 結果表示の並びと日本語名(表示のみ。計算はバックエンド)
const RESULT_LABELS: [string, string][] = [
  ["total_mass", "全備質量"],
  ["required_lift", "必要揚力"],
  ["wing_area", "必要翼面積"],
  ["wing_loading", "翼面荷重"],
  ["aspect_ratio", "アスペクト比"],
  ["mean_chord", "平均翼弦"],
  ["stall_speed", "失速速度"],
  ["speed_to_stall_ratio", "速度余裕 V/V_stall"],
  ["drag_coefficient_total", "全機抗力係数 CD"],
  ["required_thrust", "必要推力"],
  ["lift_to_drag", "揚抗比 L/D"],
  ["required_pilot_power", "パイロット必要出力"],
  ["power_margin", "出力収支"],
  ["reynolds_number", "レイノルズ数"],
];

const sig4 = (v: number) => Number(v.toPrecision(4)).toString();

// 平面形エディタの行状態(文字列で保持し送信時に数値化)
type SectionForm = { y: string; chord: string; twist: string; airfoil: string };

const DEFAULT_SECTIONS: SectionForm[] = [
  { y: "0", chord: "1.2", twist: "0", airfoil: "DAE-11" },
  { y: "15", chord: "0.6", twist: "0", airfoil: "DAE-11" },
];

const PLANFORM_DERIVED_LABELS: [string, string][] = [
  ["span", "翼幅 b"],
  ["area", "翼面積 S"],
  ["aspect_ratio", "アスペクト比 AR"],
  ["mean_chord", "平均翼弦 c̄"],
  ["taper_ratio", "テーパー比 λ"],
];

// 要求仕様フィールドの日本語名(履歴差分の表示用)
const SPEC_FIELD_LABELS: Record<string, string> = {
  pilot_mass: "パイロット質量",
  airframe_mass_target: "機体質量目標",
  pilot_power_sustained: "パイロット持続出力",
  pilot_power_max: "パイロット最大出力",
  target_cruise_speed: "目標巡航速度",
  target_distance: "目標飛行距離",
  wingspan_limit: "翼幅制限",
  air_density: "空気密度",
  wind_speed_limit: "風速条件の上限",
  flight_altitude_limit: "飛行制限高度",
  pilot_age: "パイロット年齢",
  cl_cruise: "CL_cruise",
  cl_max: "CL_max",
  cd0: "CD0",
  oswald_efficiency: "オズワルド効率 e",
  propeller_efficiency: "プロペラ効率 η_prop",
  drivetrain_efficiency: "駆動系効率 η_drive",
};

const MASS_CATEGORIES: [string, string][] = [
  ["wing_structure", "主翼構造"],
  ["fuselage_structure", "胴体・フレーム"],
  ["tail_structure", "尾翼"],
  ["propulsion", "プロペラ・駆動系"],
  ["cockpit", "コックピット"],
  ["control", "操縦系統"],
  ["pilot", "パイロット"],
  ["contest_equipment", "大会搭載機材(カメラ等)"],
  ["other", "その他"],
];

type MassItemForm = {
  name: string;
  category: string;
  mass: string;
  x: string;
  y: string;
  z: string;
  source: string;
  owner: string;
};

const EMPTY_MASS_ITEM: MassItemForm = {
  name: "",
  category: "wing_structure",
  mass: "",
  x: "0",
  y: "0",
  z: "0",
  source: "estimated",
  owner: "",
};

type StabilityForm = { st: string; lt: string; xac: string; art: string };
const DEFAULT_STABILITY: StabilityForm = { st: "2.5", lt: "4", xac: "0.9", art: "8" };

type SparForm = {
  halfSpan: string;
  loadFactor: string;
  totalMass: string;
  distribution: string;
  d: string;
  t: string;
  tipD: string;
  tipT: string;
  e: string;
  sigmaAllow: string;
  requiredSf: string;
};

const DEFAULT_SPAR: SparForm = {
  halfSpan: "15",
  loadFactor: "",
  totalMass: "100",
  distribution: "elliptic",
  d: "0.1",
  t: "1",
  tipD: "",
  tipT: "",
  e: "",
  sigmaAllow: "",
  requiredSf: "",
};

type TransitionsInfo = {
  current: string;
  allowed: string[];
  actor_required: string[];
};

type ApprovalEntry = {
  id: string;
  from_state: string;
  to_state: string;
  actor: string | null;
  comment: string | null;
  created_at: string;
};

type SweepCandidateOut = {
  values: Record<string, number>;
  feasible: boolean;
  pareto: boolean;
  violation_codes: string[];
  required_pilot_power: Quantity;
  lift_to_drag: Quantity;
  wing_area: Quantity;
  power_margin: Quantity;
};

type SweepRun = {
  id: string;
  outputs: {
    candidates: SweepCandidateOut[];
    evaluated: number;
    feasible_count: number;
    pareto_count: number;
    warnings: CalcWarning[];
  };
  execution: SolverExecution;
};

type SweepForm = {
  spanMin: string;
  spanMax: string;
  spanSteps: string;
  speedMin: string;
  speedMax: string;
  speedSteps: string;
};

const DEFAULT_SWEEP: SweepForm = {
  spanMin: "26",
  spanMax: "34",
  spanSteps: "5",
  speedMin: "6.5",
  speedMax: "8.5",
  speedSteps: "5",
};

// リビジョン間の変更点を「項目: 旧 → 新」の文字列リストで返す(表示用。計算はしない)
function specDiff(prev: RequirementSpec, curr: RequirementSpec): string[] {
  const fmt = (v: unknown): string => {
    if (v == null) return "—";
    if (typeof v === "object" && "value" in (v as object)) {
      const q = v as { value: number; unit: string };
      return `${q.value} ${q.unit}`;
    }
    return String(v);
  };
  const keys = Object.keys(SPEC_FIELD_LABELS) as (keyof RequirementSpec)[];
  const lines: string[] = [];
  for (const k of keys) {
    const a = prev[k];
    const b = curr[k];
    if (JSON.stringify(a ?? null) !== JSON.stringify(b ?? null)) {
      lines.push(`${SPEC_FIELD_LABELS[k]}: ${fmt(a)} → ${fmt(b)}`);
    }
  }
  return lines;
}

function quantityField(
  label: string,
  field: QuantityForm,
  units: string[],
  onChange: (q: QuantityForm) => void,
) {
  return (
    <label>
      {label}
      <span style={{ display: "flex", gap: "0.4rem" }}>
        <input
          required
          type="number"
          step="any"
          value={field.value}
          onChange={(e) => onChange({ ...field, value: e.target.value })}
        />
        <select
          value={field.unit}
          onChange={(e) => onChange({ ...field, unit: e.target.value })}
        >
          {units.map((u) => (
            <option key={u} value={u}>
              {u}
            </option>
          ))}
        </select>
      </span>
    </label>
  );
}

export default function ProjectPage() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;

  const [project, setProject] = useState<Project | null>(null);
  const [form, setForm] = useState<ReqForm>(DEFAULT_FORM);
  const [revision, setRevision] = useState<number | null>(null);
  const [latestRun, setLatestRun] = useState<SizingRun | null>(null);
  const [sections, setSections] = useState<SectionForm[]>(DEFAULT_SECTIONS);
  const [planformOut, setPlanformOut] = useState<WingPlanformOut | null>(null);
  const [latestAero, setLatestAero] = useState<AeroAnalysisRun | null>(null);
  const [history, setHistory] = useState<RequirementSpecOut[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [massItems, setMassItems] = useState<MassItem[]>([]);
  const [massProps, setMassProps] = useState<MassProperties | null>(null);
  const [newMassItem, setNewMassItem] = useState<MassItemForm>(EMPTY_MASS_ITEM);
  const [stabilityForm, setStabilityForm] = useState<StabilityForm>(DEFAULT_STABILITY);
  const [stabilityRun, setStabilityRun] = useState<AnalysisRunLite | null>(null);
  const [sparForm, setSparForm] = useState<SparForm>(DEFAULT_SPAR);
  const [sparRun, setSparRun] = useState<AnalysisRunLite | null>(null);
  const [transitions, setTransitions] = useState<TransitionsInfo | null>(null);
  const [approvals, setApprovals] = useState<ApprovalEntry[]>([]);
  const [transitionActor, setTransitionActor] = useState("");
  const [transitionComment, setTransitionComment] = useState("");
  const [sweepForm, setSweepForm] = useState<SweepForm>(DEFAULT_SWEEP);
  const [sweepRun, setSweepRun] = useState<SweepRun | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const reloadApprovals = useCallback(async () => {
    try {
      setTransitions(
        await apiFetch<TransitionsInfo>(`/api/projects/${projectId}/transitions`),
      );
      setApprovals(
        await apiFetch<ApprovalEntry[]>(`/api/projects/${projectId}/approvals`),
      );
    } catch {
      // 未取得は無視
    }
  }, [projectId]);

  const doTransition = async (to: string) => {
    setBusy(true);
    setError(null);
    try {
      await apiFetch(`/api/projects/${projectId}/transition`, {
        method: "POST",
        body: JSON.stringify({
          to,
          actor: transitionActor.trim() || null,
          comment: transitionComment.trim() || null,
        }),
      });
      await reloadProject();
      await reloadApprovals();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const runSweep = async (ev: React.FormEvent) => {
    ev.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const run = await apiFetch<SweepRun>(
        `/api/projects/${projectId}/design-sweeps`,
        {
          method: "POST",
          body: JSON.stringify({
            variables: [
              {
                variable: "wingspan",
                minimum: Number(sweepForm.spanMin),
                maximum: Number(sweepForm.spanMax),
                steps: Number(sweepForm.spanSteps),
              },
              {
                variable: "cruise_speed",
                minimum: Number(sweepForm.speedMin),
                maximum: Number(sweepForm.speedMax),
                steps: Number(sweepForm.speedSteps),
              },
            ],
          }),
        },
      );
      setSweepRun(run);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const reloadMass = useCallback(async () => {
    try {
      const items = await apiFetch<MassItem[]>(
        `/api/projects/${projectId}/mass-items`,
      );
      setMassItems(items);
      if (items.length > 0) {
        setMassProps(
          await apiFetch<MassProperties>(
            `/api/projects/${projectId}/mass-properties`,
          ),
        );
      } else {
        setMassProps(null);
      }
    } catch {
      // 台帳未登録は無視
    }
  }, [projectId]);

  const reloadHistory = useCallback(async () => {
    try {
      setHistory(
        await apiFetch<RequirementSpecOut[]>(
          `/api/projects/${projectId}/requirements/history`,
        ),
      );
    } catch {
      // 履歴なしは無視
    }
  }, [projectId]);

  const reloadProject = useCallback(async () => {
    setProject(await apiFetch<Project>(`/api/projects/${projectId}`));
  }, [projectId]);

  useEffect(() => {
    (async () => {
      try {
        await reloadProject();
        try {
          const req = await apiFetch<RequirementSpecOut>(
            `/api/projects/${projectId}/requirements`,
          );
          setRevision(req.revision);
          const s = req.spec;
          setForm({
            pilot_mass: {
              value: String(s.pilot_mass.value),
              unit: s.pilot_mass.unit,
            },
            airframe_mass_target: {
              value: String(s.airframe_mass_target.value),
              unit: s.airframe_mass_target.unit,
            },
            pilot_power_sustained: {
              value: String(s.pilot_power_sustained.value),
              unit: s.pilot_power_sustained.unit,
            },
            target_cruise_speed: {
              value: String(s.target_cruise_speed.value),
              unit: s.target_cruise_speed.unit,
            },
            wingspan_limit: {
              value: String(s.wingspan_limit.value),
              unit: s.wingspan_limit.unit,
            },
            air_density: {
              value: String(s.air_density.value),
              unit: s.air_density.unit,
            },
            wind_speed_limit: {
              value: String(s.wind_speed_limit.value),
              unit: s.wind_speed_limit.unit,
            },
            flight_altitude_limit: {
              value: String(s.flight_altitude_limit.value),
              unit: s.flight_altitude_limit.unit,
            },
            pilot_age: s.pilot_age != null ? String(s.pilot_age) : "",
            cl_cruise: String(s.cl_cruise),
            cl_max: String(s.cl_max),
            cd0: String(s.cd0),
            oswald_efficiency: String(s.oswald_efficiency),
            propeller_efficiency: String(s.propeller_efficiency),
            drivetrain_efficiency: String(s.drivetrain_efficiency),
          });
        } catch {
          // 要求仕様が未入力(404)の場合は既定値のまま
        }
        try {
          const pf = await apiFetch<WingPlanformOut>(
            `/api/projects/${projectId}/planform`,
          );
          setPlanformOut(pf);
          setSections(
            pf.planform.sections.map((s) => ({
              y: String(s.spanwise_position.value),
              chord: String(s.chord.value),
              twist: String(s.twist_deg),
              airfoil: s.airfoil,
            })),
          );
        } catch {
          // 平面形が未入力(404)の場合は既定値のまま
        }
        try {
          const aeroRuns = await apiFetch<AeroAnalysisRun[]>(
            `/api/projects/${projectId}/aero-analyses`,
          );
          if (aeroRuns.length > 0) setLatestAero(aeroRuns[0]);
        } catch {
          // 解析履歴なしは無視
        }
        await reloadHistory();
        await reloadMass();
        await reloadApprovals();
      } catch (e) {
        setError(String(e));
      }
    })();
  }, [projectId, reloadProject, reloadHistory, reloadMass, reloadApprovals]);

  const addMassItem = async (ev: React.FormEvent) => {
    ev.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await apiFetch<MassItem>(`/api/projects/${projectId}/mass-items`, {
        method: "POST",
        body: JSON.stringify({
          name: newMassItem.name,
          category: newMassItem.category,
          mass: { value: Number(newMassItem.mass), unit: "kg" },
          position_x: { value: Number(newMassItem.x), unit: "m" },
          position_y: { value: Number(newMassItem.y), unit: "m" },
          position_z: { value: Number(newMassItem.z), unit: "m" },
          source: newMassItem.source,
          owner: newMassItem.owner,
        }),
      });
      setNewMassItem(EMPTY_MASS_ITEM);
      await reloadMass();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const removeMassItem = async (itemId: string) => {
    setBusy(true);
    try {
      await fetch(`${API_BASE}/api/mass-items/${itemId}`, { method: "DELETE" });
      await reloadMass();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const runStability = async () => {
    setBusy(true);
    setError(null);
    try {
      const run = await apiFetch<AnalysisRunLite>(
        `/api/projects/${projectId}/stability-analyses`,
        {
          method: "POST",
          body: JSON.stringify({
            horizontal_tail_area: {
              value: Number(stabilityForm.st),
              unit: "m^2",
            },
            tail_arm: { value: Number(stabilityForm.lt), unit: "m" },
            wing_ac_position: { value: Number(stabilityForm.xac), unit: "m" },
            tail_aspect_ratio: Number(stabilityForm.art),
          }),
        },
      );
      setStabilityRun(run);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const runSpar = async (ev: React.FormEvent) => {
    ev.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const hasTaper =
        sparForm.tipD.trim() !== "" && sparForm.tipT.trim() !== "";
      const run = await apiFetch<AnalysisRunLite>(
        `/api/projects/${projectId}/spar-analyses`,
        {
          method: "POST",
          body: JSON.stringify({
            half_span: { value: Number(sparForm.halfSpan), unit: "m" },
            load_factor: Number(sparForm.loadFactor),
            total_mass: { value: Number(sparForm.totalMass), unit: "kg" },
            lift_distribution: sparForm.distribution,
            spar_outer_diameter: { value: Number(sparForm.d), unit: "m" },
            spar_wall_thickness: { value: Number(sparForm.t), unit: "mm" },
            ...(hasTaper
              ? {
                  spar_tip_outer_diameter: {
                    value: Number(sparForm.tipD),
                    unit: "m",
                  },
                  spar_tip_wall_thickness: {
                    value: Number(sparForm.tipT),
                    unit: "mm",
                  },
                }
              : {}),
            elastic_modulus: { value: Number(sparForm.e), unit: "GPa" },
            allowable_stress: {
              value: Number(sparForm.sigmaAllow),
              unit: "MPa",
            },
            required_safety_factor: Number(sparForm.requiredSf),
          }),
        },
      );
      setSparRun(run);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const savePlanform = async () => {
    setBusy(true);
    setError(null);
    try {
      const payload = {
        sections: sections.map((s) => ({
          spanwise_position: { value: Number(s.y), unit: "m" },
          chord: { value: Number(s.chord), unit: "m" },
          twist_deg: Number(s.twist),
          airfoil: s.airfoil,
        })),
      };
      const saved = await apiFetch<WingPlanformOut>(
        `/api/projects/${projectId}/planform`,
        { method: "PUT", body: JSON.stringify(payload) },
      );
      setPlanformOut(saved);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const runAeroAnalysis = async () => {
    setBusy(true);
    setError(null);
    try {
      const run = await apiFetch<AeroAnalysisRun>(
        `/api/projects/${projectId}/aero-analyses`,
        { method: "POST" },
      );
      setLatestAero(run);
      await reloadProject();
      await reloadApprovals();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const toSpec = (): RequirementSpec => ({
    pilot_mass: {
      value: Number(form.pilot_mass.value),
      unit: form.pilot_mass.unit,
    },
    airframe_mass_target: {
      value: Number(form.airframe_mass_target.value),
      unit: form.airframe_mass_target.unit,
    },
    pilot_power_sustained: {
      value: Number(form.pilot_power_sustained.value),
      unit: form.pilot_power_sustained.unit,
    },
    target_cruise_speed: {
      value: Number(form.target_cruise_speed.value),
      unit: form.target_cruise_speed.unit,
    },
    wingspan_limit: {
      value: Number(form.wingspan_limit.value),
      unit: form.wingspan_limit.unit,
    },
    air_density: {
      value: Number(form.air_density.value),
      unit: form.air_density.unit,
    },
    wind_speed_limit: {
      value: Number(form.wind_speed_limit.value),
      unit: form.wind_speed_limit.unit,
    },
    flight_altitude_limit: {
      value: Number(form.flight_altitude_limit.value),
      unit: form.flight_altitude_limit.unit,
    },
    pilot_age: form.pilot_age.trim() === "" ? null : Number(form.pilot_age),
    cl_cruise: Number(form.cl_cruise),
    cl_max: Number(form.cl_max),
    cd0: Number(form.cd0),
    oswald_efficiency: Number(form.oswald_efficiency),
    propeller_efficiency: Number(form.propeller_efficiency),
    drivetrain_efficiency: Number(form.drivetrain_efficiency),
  });

  const saveRequirements = async (ev: React.FormEvent) => {
    ev.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const saved = await apiFetch<RequirementSpecOut>(
        `/api/projects/${projectId}/requirements`,
        { method: "PUT", body: JSON.stringify(toSpec()) },
      );
      setRevision(saved.revision);
      setLatestRun(null);
      await reloadProject();
      await reloadHistory();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const runSizing = async () => {
    setBusy(true);
    setError(null);
    try {
      const run = await apiFetch<SizingRun>(
        `/api/projects/${projectId}/sizing-runs`,
        { method: "POST" },
      );
      setLatestRun(run);
      await reloadProject();
      await reloadApprovals();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  if (!project) {
    return (
      <>
        <p>
          <Link href="/">← プロジェクト一覧</Link>
        </p>
        {error ? <p className="error">{error}</p> : <p>読み込み中…</p>}
      </>
    );
  }

  return (
    <>
      <p>
        <Link href="/">← プロジェクト一覧</Link>
      </p>
      <h1>
        {project.aircraft_name}{" "}
        <span className={`badge ${project.status}`}>{project.status}</span>
      </h1>
      <p className="note">
        {project.team_name} / {project.design_year}年度 / {project.category} /
        設計責任者: {project.design_lead}
        {revision !== null && ` / 要求仕様 rev.${revision}`}
      </p>
      {error && <p className="error">{error}</p>}

      <h2>要求仕様(Step 2)</h2>
      <form className="card" onSubmit={saveRequirements}>
        <div className="grid2">
          {quantityField(
            "パイロット質量",
            form.pilot_mass,
            ["kg", "g", "lb"],
            (q) => setForm({ ...form, pilot_mass: q }),
          )}
          {quantityField(
            "機体質量目標",
            form.airframe_mass_target,
            ["kg", "g", "lb"],
            (q) => setForm({ ...form, airframe_mass_target: q }),
          )}
          {quantityField(
            "パイロット持続出力",
            form.pilot_power_sustained,
            ["W", "kW"],
            (q) => setForm({ ...form, pilot_power_sustained: q }),
          )}
          {quantityField(
            "目標巡航速度",
            form.target_cruise_speed,
            ["m/s", "km/h", "knot"],
            (q) => setForm({ ...form, target_cruise_speed: q }),
          )}
          {quantityField(
            "翼幅制限(※大会規則ではなくチーム独自の設計制約)",
            form.wingspan_limit,
            ["m", "cm", "mm", "ft"],
            (q) => setForm({ ...form, wingspan_limit: q }),
          )}
          {quantityField("空気密度", form.air_density, ["kg/m^3", "g/L"], (q) =>
            setForm({ ...form, air_density: q }),
          )}
          {quantityField(
            "風速条件の上限(参考: 大会規則の競技中断基準 5 m/s)",
            form.wind_speed_limit,
            ["m/s", "km/h", "knot"],
            (q) => setForm({ ...form, wind_speed_limit: q }),
          )}
          {quantityField(
            "飛行制限高度(参考: 大会規則 10 m)",
            form.flight_altitude_limit,
            ["m", "ft"],
            (q) => setForm({ ...form, flight_altitude_limit: q }),
          )}
        </div>
        <label>
          パイロット年齢(任意・記録のみ。大会規則の適合判定はチーム自身で行ってください)
          <input
            type="number"
            min={10}
            max={100}
            value={form.pilot_age}
            onChange={(e) => setForm({ ...form, pilot_age: e.target.value })}
          />
        </label>
        <p className="note">
          係数(無次元)— 既定値は仮定(ASSUMPTIONS.md A-102〜A-107)。根拠なく変更しないこと。
        </p>
        <div className="grid2">
          <label>
            巡航揚力係数 CL_cruise
            <input
              type="number"
              step="any"
              value={form.cl_cruise}
              onChange={(e) => setForm({ ...form, cl_cruise: e.target.value })}
            />
          </label>
          <label>
            最大揚力係数 CL_max
            <input
              type="number"
              step="any"
              value={form.cl_max}
              onChange={(e) => setForm({ ...form, cl_max: e.target.value })}
            />
          </label>
          <label>
            有害抗力係数 CD0
            <input
              type="number"
              step="any"
              value={form.cd0}
              onChange={(e) => setForm({ ...form, cd0: e.target.value })}
            />
          </label>
          <label>
            オズワルド効率 e
            <input
              type="number"
              step="any"
              value={form.oswald_efficiency}
              onChange={(e) =>
                setForm({ ...form, oswald_efficiency: e.target.value })
              }
            />
          </label>
          <label>
            プロペラ効率 η_prop
            <input
              type="number"
              step="any"
              value={form.propeller_efficiency}
              onChange={(e) =>
                setForm({ ...form, propeller_efficiency: e.target.value })
              }
            />
          </label>
          <label>
            駆動系効率 η_drive
            <input
              type="number"
              step="any"
              value={form.drivetrain_efficiency}
              onChange={(e) =>
                setForm({ ...form, drivetrain_efficiency: e.target.value })
              }
            />
          </label>
        </div>
        <button type="submit" disabled={busy}>
          要求仕様を保存
        </button>{" "}
        <button
          type="button"
          disabled={busy || revision === null}
          onClick={runSizing}
        >
          初期サイジングを実行(Step 3)
        </button>
      </form>

      {history.length > 1 && (
        <div className="card">
          <button type="button" onClick={() => setShowHistory(!showHistory)}>
            要求仕様の変更履歴({history.length}リビジョン){showHistory ? "を閉じる" : "を表示"}
          </button>
          {showHistory && (
            <table>
              <thead>
                <tr>
                  <th>rev</th>
                  <th>日時</th>
                  <th>前リビジョンからの変更点</th>
                </tr>
              </thead>
              <tbody>
                {history.map((h, i) => {
                  const older = history[i + 1]; // 降順のため次要素が1つ前のリビジョン
                  const changes = older ? specDiff(older.spec, h.spec) : null;
                  return (
                    <tr key={h.id}>
                      <td>{h.revision}</td>
                      <td>{new Date(h.created_at).toLocaleString("ja-JP")}</td>
                      <td>
                        {changes === null
                          ? "(初版)"
                          : changes.length === 0
                            ? "変更なし(再保存)"
                            : changes.map((c) => <div key={c}>{c}</div>)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      )}

      {latestRun && (
        <>
          <h2>初期サイジング結果</h2>
          <p className="note">
            実行モード:{" "}
            <span className={`badge ${latestRun.execution.execution_mode}`}>
              {latestRun.execution.execution_mode}
            </span>{" "}
            (理論式による解析的推定 — 外部解析ソフトは実行していません) / ソルバー:{" "}
            {latestRun.execution.solver_name} v
            {latestRun.execution.solver_version} / 入力ハッシュ:{" "}
            <code>{latestRun.input_hash.slice(0, 12)}…</code>
          </p>

          {latestRun.outputs.warnings.length > 0 && (
            <table>
              <thead>
                <tr>
                  <th>警告</th>
                  <th>重要度</th>
                  <th>内容</th>
                </tr>
              </thead>
              <tbody>
                {latestRun.outputs.warnings.map((w) => (
                  <tr key={w.code} className={`warn-${w.severity}`}>
                    <td>{w.code}</td>
                    <td>{w.severity}</td>
                    <td>{w.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <table>
            <thead>
              <tr>
                <th>項目</th>
                <th>値(有効4桁)</th>
                <th>単位</th>
              </tr>
            </thead>
            <tbody>
              {RESULT_LABELS.filter(
                ([key]) => latestRun.outputs.quantities[key],
              ).map(([key, label]) => {
                const q = latestRun.outputs.quantities[key];
                return (
                  <tr key={key}>
                    <td>{label}</td>
                    <td>{sig4(q.value)}</td>
                    <td>{q.unit}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          <p>
            <a href={reportUrl(latestRun.id)} target="_blank" rel="noreferrer">
              📄 詳細レポートを開く(使用した式・仮定・免責を含む)
            </a>
          </p>
        </>
      )}

      <h2>主翼平面形(Step 4)</h2>
      <div className="card">
        <p className="note">
          左右対称翼の片翼を翼根(y=0)から翼端へ定義します。単位: m。
        </p>
        <table>
          <thead>
            <tr>
              <th>y [m](翼根からの距離)</th>
              <th>翼弦 [m]</th>
              <th>ねじり [deg]</th>
              <th>翼型</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {sections.map((s, i) => (
              <tr key={i}>
                <td>
                  <input
                    type="number"
                    step="any"
                    value={s.y}
                    onChange={(e) => {
                      const next = [...sections];
                      next[i] = { ...s, y: e.target.value };
                      setSections(next);
                    }}
                  />
                </td>
                <td>
                  <input
                    type="number"
                    step="any"
                    value={s.chord}
                    onChange={(e) => {
                      const next = [...sections];
                      next[i] = { ...s, chord: e.target.value };
                      setSections(next);
                    }}
                  />
                </td>
                <td>
                  <input
                    type="number"
                    step="any"
                    value={s.twist}
                    onChange={(e) => {
                      const next = [...sections];
                      next[i] = { ...s, twist: e.target.value };
                      setSections(next);
                    }}
                  />
                </td>
                <td>
                  <input
                    value={s.airfoil}
                    onChange={(e) => {
                      const next = [...sections];
                      next[i] = { ...s, airfoil: e.target.value };
                      setSections(next);
                    }}
                  />
                </td>
                <td>
                  <button
                    type="button"
                    disabled={sections.length <= 2}
                    onClick={() =>
                      setSections(sections.filter((_, j) => j !== i))
                    }
                  >
                    削除
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <button
          type="button"
          onClick={() => {
            const last = sections[sections.length - 1];
            setSections([
              ...sections,
              { ...last, y: String(Number(last.y) + 1) },
            ]);
          }}
        >
          セクション追加
        </button>{" "}
        <button type="button" disabled={busy} onClick={savePlanform}>
          平面形を保存
        </button>{" "}
        <button
          type="button"
          disabled={busy || !planformOut || revision === null}
          onClick={runAeroAnalysis}
        >
          モック空力解析を実行(Step 5)
        </button>
        {planformOut && (
          <>
            <p className="note">
              保存済み rev.{planformOut.revision} — 導出量(台形積分):
            </p>
            <table>
              <tbody>
                {PLANFORM_DERIVED_LABELS.filter(
                  ([key]) => planformOut.derived[key],
                ).map(([key, label]) => {
                  const q = planformOut.derived[key];
                  return (
                    <tr key={key}>
                      <td>{label}</td>
                      <td>{sig4(q.value)}</td>
                      <td>{q.unit === "dimensionless" ? "−" : q.unit}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </>
        )}
      </div>

      {latestAero && (
        <>
          <h2>空力解析結果(Step 5)</h2>
          <p className="note">
            実行モード:{" "}
            <span className={`badge ${latestAero.execution.execution_mode}`}>
              {latestAero.execution.execution_mode}
            </span>{" "}
            {latestAero.execution.execution_mode === "mock" && (
              <strong>
                — これは揚力線理論による近似(モック)であり、実際のXFLR5解析ではありません。
                設計判断には実解析が必要です。
              </strong>
            )}{" "}
            / ソルバー: {latestAero.solver_name} / 平面形 rev.
            {latestAero.planform_revision} / 要求仕様 rev.
            {latestAero.requirement_revision}
          </p>
          <p>
            最大揚抗比 (L/D)max = <strong>{sig4(latestAero.outputs.max_lift_to_drag)}</strong>{" "}
            (CL = {sig4(latestAero.outputs.cl_at_max_lift_to_drag)})
          </p>
          {latestAero.outputs.warnings.length > 0 && (
            <ul className="note">
              {latestAero.outputs.warnings.map((w) => (
                <li key={w.code}>
                  [{w.code}] {w.message}
                </li>
              ))}
            </ul>
          )}
          <table>
            <thead>
              <tr>
                <th>迎角 α [deg]</th>
                <th>CL</th>
                <th>CD</th>
                <th>L/D</th>
                <th>失速</th>
              </tr>
            </thead>
            <tbody>
              {latestAero.outputs.polar.map((p) => (
                <tr key={p.alpha_deg} className={p.stalled ? "warn-warning" : ""}>
                  <td>{p.alpha_deg}</td>
                  <td>{sig4(p.cl)}</td>
                  <td>{sig4(p.cd)}</td>
                  <td>{p.cd > 0 ? sig4(p.cl / p.cd) : "−"}</td>
                  <td>{p.stalled ? "⚠" : ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      <h2>質量・重心台帳(Step 9)</h2>
      <div className="card">
        <p className="note">
          座標系: 原点=機首先端、x=後方+、y=右+、z=上+(A-135)。点質量近似(A-136)。
        </p>
        {massItems.length > 0 && (
          <table>
            <thead>
              <tr>
                <th>部品名</th>
                <th>カテゴリ</th>
                <th>質量</th>
                <th>x / y / z [m]</th>
                <th>出所</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {massItems.map((it) => (
                <tr key={it.id}>
                  <td>{it.name}</td>
                  <td>
                    {MASS_CATEGORIES.find(([v]) => v === it.category)?.[1] ??
                      it.category}
                  </td>
                  <td>
                    {it.mass.value} {it.mass.unit}
                  </td>
                  <td>
                    {it.position_x.value} / {it.position_y.value} /{" "}
                    {it.position_z.value}
                  </td>
                  <td>{it.source === "measured" ? "実測" : "推定"}</td>
                  <td>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => removeMassItem(it.id)}
                    >
                      削除
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <form onSubmit={addMassItem}>
          <div className="grid2">
            <label>
              部品名
              <input
                required
                value={newMassItem.name}
                onChange={(e) =>
                  setNewMassItem({ ...newMassItem, name: e.target.value })
                }
              />
            </label>
            <label>
              カテゴリ
              <select
                value={newMassItem.category}
                onChange={(e) =>
                  setNewMassItem({ ...newMassItem, category: e.target.value })
                }
              >
                {MASS_CATEGORIES.map(([v, label]) => (
                  <option key={v} value={v}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              質量 [kg]
              <input
                required
                type="number"
                step="any"
                value={newMassItem.mass}
                onChange={(e) =>
                  setNewMassItem({ ...newMassItem, mass: e.target.value })
                }
              />
            </label>
            <label>
              出所
              <select
                value={newMassItem.source}
                onChange={(e) =>
                  setNewMassItem({ ...newMassItem, source: e.target.value })
                }
              >
                <option value="estimated">推定値</option>
                <option value="measured">実測値</option>
              </select>
            </label>
            <label>
              x [m](機首から後方+)
              <input
                type="number"
                step="any"
                value={newMassItem.x}
                onChange={(e) =>
                  setNewMassItem({ ...newMassItem, x: e.target.value })
                }
              />
            </label>
            <label>
              z [m](上方+)
              <input
                type="number"
                step="any"
                value={newMassItem.z}
                onChange={(e) =>
                  setNewMassItem({ ...newMassItem, z: e.target.value })
                }
              />
            </label>
          </div>
          <button type="submit" disabled={busy}>
            部品を追加
          </button>
        </form>

        {massProps && (
          <>
            <p className="note">
              質量特性(推定 {massProps.estimated_item_count} 件 / 実測{" "}
              {massProps.measured_item_count} 件):
            </p>
            {massProps.warnings.length > 0 && (
              <table>
                <tbody>
                  {massProps.warnings.map((w) => (
                    <tr key={w.code} className={`warn-${w.severity}`}>
                      <td>{w.code}</td>
                      <td>{w.message}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            <table>
              <tbody>
                {[
                  ["total_mass", "総質量"],
                  ["airframe_mass", "機体質量(パイロット除く)"],
                  ["airframe_mass_target", "機体質量目標"],
                  ["airframe_mass_delta", "目標との差"],
                  ["cg_x", "重心 x"],
                  ["cg_z", "重心 z"],
                  ["inertia_yy", "ピッチ慣性 Iyy"],
                ]
                  .filter(([k]) => massProps.quantities[k])
                  .map(([k, label]) => {
                    const q = massProps.quantities[k];
                    return (
                      <tr key={k}>
                        <td>{label}</td>
                        <td>{sig4(q.value)}</td>
                        <td>{q.unit}</td>
                      </tr>
                    );
                  })}
              </tbody>
            </table>
          </>
        )}
      </div>

      <h2>静安定(Step 7)</h2>
      <div className="card">
        <p className="note">
          翼幾何は平面形(Step 4)、重心は質量台帳(Step 9)から取得します。
          胴体・プロペラの寄与は含まない簡易推定です(A-131)。
        </p>
        <div className="grid2">
          <label>
            水平尾翼面積 S_t [m²]
            <input
              type="number"
              step="any"
              value={stabilityForm.st}
              onChange={(e) =>
                setStabilityForm({ ...stabilityForm, st: e.target.value })
              }
            />
          </label>
          <label>
            尾翼モーメントアーム l_t [m]
            <input
              type="number"
              step="any"
              value={stabilityForm.lt}
              onChange={(e) =>
                setStabilityForm({ ...stabilityForm, lt: e.target.value })
              }
            />
          </label>
          <label>
            主翼空力中心 x_ac [m](機首から)
            <input
              type="number"
              step="any"
              value={stabilityForm.xac}
              onChange={(e) =>
                setStabilityForm({ ...stabilityForm, xac: e.target.value })
              }
            />
          </label>
          <label>
            尾翼アスペクト比
            <input
              type="number"
              step="any"
              value={stabilityForm.art}
              onChange={(e) =>
                setStabilityForm({ ...stabilityForm, art: e.target.value })
              }
            />
          </label>
        </div>
        <button
          type="button"
          disabled={busy || !planformOut || massItems.length === 0}
          onClick={runStability}
        >
          静安定を計算
        </button>
        {stabilityRun && (
          <>
            <p className="note">
              実行モード:{" "}
              <span className={`badge ${stabilityRun.execution.execution_mode}`}>
                {stabilityRun.execution.execution_mode}
              </span>
            </p>
            {stabilityRun.outputs.warnings.map((w) => (
              <p key={w.code} className={`warn-${w.severity}`}>
                [{w.code}] {w.message}
              </p>
            ))}
            <table>
              <tbody>
                {[
                  ["tail_volume_horizontal", "水平尾翼容積 V_H"],
                  ["neutral_point_x", "中立点 x_np"],
                  ["cg_x", "重心 x_cg"],
                  ["static_margin", "静安定余裕 SM"],
                ].map(([k, label]) => {
                  const q = stabilityRun.outputs.quantities[k];
                  return (
                    <tr key={k}>
                      <td>{label}</td>
                      <td>{sig4(q.value)}</td>
                      <td>{q.unit === "dimensionless" ? "−" : q.unit}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </>
        )}
      </div>

      <h2>主桁の簡易梁解析(Step 8)</h2>
      <form className="card" onSubmit={runSpar}>
        <p className="note">
          片持ち梁モデル(翼根固定・円管断面・自重軽減なし=安全側)。
          <strong>
            荷重倍数・材料定数・許容応力・要求安全率はチームが確定して入力してください(既定値なし)。
          </strong>
        </p>
        <div className="grid2">
          <label>
            半翼幅 [m]
            <input
              type="number"
              step="any"
              value={sparForm.halfSpan}
              onChange={(e) =>
                setSparForm({ ...sparForm, halfSpan: e.target.value })
              }
            />
          </label>
          <label>
            荷重倍数 n(要チーム確定)
            <input
              required
              type="number"
              step="any"
              value={sparForm.loadFactor}
              onChange={(e) =>
                setSparForm({ ...sparForm, loadFactor: e.target.value })
              }
            />
          </label>
          <label>
            全備質量 [kg]
            <input
              type="number"
              step="any"
              value={sparForm.totalMass}
              onChange={(e) =>
                setSparForm({ ...sparForm, totalMass: e.target.value })
              }
            />
          </label>
          <label>
            揚力分布
            <select
              value={sparForm.distribution}
              onChange={(e) =>
                setSparForm({ ...sparForm, distribution: e.target.value })
              }
            >
              <option value="elliptic">楕円分布</option>
              <option value="uniform">一様分布(保守側)</option>
            </select>
          </label>
          <label>
            桁外径 D [m]
            <input
              type="number"
              step="any"
              value={sparForm.d}
              onChange={(e) => setSparForm({ ...sparForm, d: e.target.value })}
            />
          </label>
          <label>
            肉厚 t [mm]
            <input
              type="number"
              step="any"
              value={sparForm.t}
              onChange={(e) => setSparForm({ ...sparForm, t: e.target.value })}
            />
          </label>
          <label>
            翼端外径 [m](任意・テーパー桁)
            <input
              type="number"
              step="any"
              value={sparForm.tipD}
              onChange={(e) =>
                setSparForm({ ...sparForm, tipD: e.target.value })
              }
            />
          </label>
          <label>
            翼端肉厚 [mm](任意・テーパー桁)
            <input
              type="number"
              step="any"
              value={sparForm.tipT}
              onChange={(e) =>
                setSparForm({ ...sparForm, tipT: e.target.value })
              }
            />
          </label>
          <label>
            ヤング率 E [GPa](要チーム確定)
            <input
              required
              type="number"
              step="any"
              value={sparForm.e}
              onChange={(e) => setSparForm({ ...sparForm, e: e.target.value })}
            />
          </label>
          <label>
            許容応力 [MPa](要チーム確定)
            <input
              required
              type="number"
              step="any"
              value={sparForm.sigmaAllow}
              onChange={(e) =>
                setSparForm({ ...sparForm, sigmaAllow: e.target.value })
              }
            />
          </label>
          <label>
            要求安全率(要チーム確定)
            <input
              required
              type="number"
              step="any"
              value={sparForm.requiredSf}
              onChange={(e) =>
                setSparForm({ ...sparForm, requiredSf: e.target.value })
              }
            />
          </label>
        </div>
        <button type="submit" disabled={busy}>
          梁解析を実行
        </button>
        {sparRun && (
          <>
            <p className="note">
              実行モード:{" "}
              <span className={`badge ${sparRun.execution.execution_mode}`}>
                {sparRun.execution.execution_mode}
              </span>
            </p>
            {sparRun.outputs.warnings.map((w) => (
              <p key={w.code} className={`warn-${w.severity}`}>
                [{w.code}] {w.message}
              </p>
            ))}
            <table>
              <tbody>
                {[
                  ["root_shear", "翼根せん断力"],
                  ["root_bending_moment", "翼根曲げモーメント"],
                  ["root_bending_stress", "翼根曲げ応力"],
                  ["tip_deflection", "翼端たわみ"],
                  ["tip_deflection_ratio", "たわみ比 δ/s"],
                  ["safety_factor", "安全率 SF"],
                ].map(([k, label]) => {
                  const q = sparRun.outputs.quantities[k];
                  return (
                    <tr key={k}>
                      <td>{label}</td>
                      <td>{sig4(q.value)}</td>
                      <td>{q.unit === "dimensionless" ? "−" : q.unit}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </>
        )}
      </form>

      <h2>設計スイープ(Step 11)</h2>
      <form className="card" onSubmit={runSweep}>
        <p className="note">
          翼幅×巡航速度のグリッドを初期サイジングで評価します(解析的推定)。
          <strong>PBMは最適解を自動採用しません。</strong>
          候補とパレートフロントを提示するので、採用判断はチームで行ってください。
        </p>
        <div className="grid2">
          <label>
            翼幅 最小/最大/分割 [m]
            <span style={{ display: "flex", gap: "0.4rem" }}>
              <input
                type="number"
                step="any"
                value={sweepForm.spanMin}
                onChange={(e) =>
                  setSweepForm({ ...sweepForm, spanMin: e.target.value })
                }
              />
              <input
                type="number"
                step="any"
                value={sweepForm.spanMax}
                onChange={(e) =>
                  setSweepForm({ ...sweepForm, spanMax: e.target.value })
                }
              />
              <input
                type="number"
                min={2}
                max={15}
                value={sweepForm.spanSteps}
                onChange={(e) =>
                  setSweepForm({ ...sweepForm, spanSteps: e.target.value })
                }
              />
            </span>
          </label>
          <label>
            巡航速度 最小/最大/分割 [m/s]
            <span style={{ display: "flex", gap: "0.4rem" }}>
              <input
                type="number"
                step="any"
                value={sweepForm.speedMin}
                onChange={(e) =>
                  setSweepForm({ ...sweepForm, speedMin: e.target.value })
                }
              />
              <input
                type="number"
                step="any"
                value={sweepForm.speedMax}
                onChange={(e) =>
                  setSweepForm({ ...sweepForm, speedMax: e.target.value })
                }
              />
              <input
                type="number"
                min={2}
                max={15}
                value={sweepForm.speedSteps}
                onChange={(e) =>
                  setSweepForm({ ...sweepForm, speedSteps: e.target.value })
                }
              />
            </span>
          </label>
        </div>
        <button type="submit" disabled={busy || revision === null}>
          スイープを実行
        </button>
        {sweepRun && (
          <>
            <p className="note">
              評価 {sweepRun.outputs.evaluated} 案 / 可行{" "}
              {sweepRun.outputs.feasible_count} 案 / パレート{" "}
              {sweepRun.outputs.pareto_count} 案(必要出力の小さい順、上位15件表示)
            </p>
            {sweepRun.outputs.warnings.map((w) => (
              <p key={w.code} className={`warn-${w.severity}`}>
                [{w.code}] {w.message}
              </p>
            ))}
            <table>
              <thead>
                <tr>
                  <th>翼幅 [m]</th>
                  <th>速度 [m/s]</th>
                  <th>必要出力 [W]</th>
                  <th>L/D</th>
                  <th>翼面積 [m²]</th>
                  <th>可行</th>
                  <th>パレート</th>
                </tr>
              </thead>
              <tbody>
                {sweepRun.outputs.candidates.slice(0, 15).map((c, i) => (
                  <tr
                    key={i}
                    className={
                      !c.feasible ? "warn-violation" : c.pareto ? "warn-info" : ""
                    }
                  >
                    <td>{sig4(c.values["wingspan"] ?? 0)}</td>
                    <td>{sig4(c.values["cruise_speed"] ?? 0)}</td>
                    <td>{sig4(c.required_pilot_power.value)}</td>
                    <td>{sig4(c.lift_to_drag.value)}</td>
                    <td>{sig4(c.wing_area.value)}</td>
                    <td>{c.feasible ? "○" : `✗ (${c.violation_codes.join(",")})`}</td>
                    <td>{c.pareto ? "★" : ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </form>

      <h2>設計状態・承認(T-304)</h2>
      <div className="card">
        <p className="note">
          現在の状態:{" "}
          <span className={`badge ${project.status}`}>{project.status}</span>。
          approved / rejected への遷移には判断者名が必要です。全遷移は監査ログに記録されます。
        </p>
        <div className="grid2">
          <label>
            判断者(actor)
            <input
              value={transitionActor}
              onChange={(e) => setTransitionActor(e.target.value)}
            />
          </label>
          <label>
            コメント
            <input
              value={transitionComment}
              onChange={(e) => setTransitionComment(e.target.value)}
            />
          </label>
        </div>
        {transitions &&
          transitions.allowed.map((to) => (
            <button
              key={to}
              type="button"
              disabled={
                busy ||
                (transitions.actor_required.includes(to) &&
                  transitionActor.trim() === "")
              }
              onClick={() => doTransition(to)}
              style={{ marginRight: "0.5rem" }}
            >
              {to} へ遷移
              {transitions.actor_required.includes(to) ? "(判断者名必須)" : ""}
            </button>
          ))}
        {approvals.length > 0 && (
          <table>
            <thead>
              <tr>
                <th>日時</th>
                <th>遷移</th>
                <th>判断者</th>
                <th>コメント</th>
              </tr>
            </thead>
            <tbody>
              {approvals.map((a) => (
                <tr key={a.id}>
                  <td>{new Date(a.created_at).toLocaleString("ja-JP")}</td>
                  <td>
                    {a.from_state} → {a.to_state}
                  </td>
                  <td>{a.actor ?? "(自動遷移)"}</td>
                  <td>{a.comment ?? ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}
