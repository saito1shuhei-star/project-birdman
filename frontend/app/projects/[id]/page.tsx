"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import {
  AeroAnalysisRun,
  apiFetch,
  Project,
  reportUrl,
  RequirementSpec,
  RequirementSpecOut,
  SizingRun,
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
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

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
      } catch (e) {
        setError(String(e));
      }
    })();
  }, [projectId, reloadProject]);

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
          {quantityField("パイロット質量", form.pilot_mass, ["kg", "lb"], (q) =>
            setForm({ ...form, pilot_mass: q }),
          )}
          {quantityField(
            "機体質量目標",
            form.airframe_mass_target,
            ["kg", "lb"],
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
            ["m/s", "km/h"],
            (q) => setForm({ ...form, target_cruise_speed: q }),
          )}
          {quantityField(
            "翼幅制限(※大会規則ではなくチーム独自の設計制約)",
            form.wingspan_limit,
            ["m", "mm"],
            (q) => setForm({ ...form, wingspan_limit: q }),
          )}
          {quantityField("空気密度", form.air_density, ["kg/m^3"], (q) =>
            setForm({ ...form, air_density: q }),
          )}
          {quantityField(
            "風速条件の上限(参考: 大会規則の競技中断基準 5 m/s)",
            form.wind_speed_limit,
            ["m/s", "km/h"],
            (q) => setForm({ ...form, wind_speed_limit: q }),
          )}
          {quantityField(
            "飛行制限高度(参考: 大会規則 10 m)",
            form.flight_altitude_limit,
            ["m"],
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
    </>
  );
}
