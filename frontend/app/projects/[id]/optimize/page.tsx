"use client";

// 設計スイープ(Step 11)

import { useState } from "react";
import { useParams } from "next/navigation";
import { apiFetch, CalcWarning, Quantity, SolverExecution } from "@/lib/api";
import { useProjectShell } from "@/lib/project-shell";
import { sig4 } from "@/lib/ui";

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

type SweepRunFull = {
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

const DEFAULT_FORM: SweepForm = {
  spanMin: "26",
  spanMax: "34",
  spanSteps: "5",
  speedMin: "6.5",
  speedMax: "8.5",
  speedSteps: "5",
};

export default function OptimizePage() {
  const params = useParams<{ id: string }>();
  const { data, refresh } = useProjectShell();
  const [form, setForm] = useState<SweepForm>(DEFAULT_FORM);
  const [run, setRun] = useState<SweepRunFull | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const runSweep = async (ev: React.FormEvent) => {
    ev.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const result = await apiFetch<SweepRunFull>(
        `/api/projects/${params.id}/design-sweeps`,
        {
          method: "POST",
          body: JSON.stringify({
            variables: [
              {
                variable: "wingspan",
                minimum: Number(form.spanMin),
                maximum: Number(form.spanMax),
                steps: Number(form.spanSteps),
              },
              {
                variable: "cruise_speed",
                minimum: Number(form.speedMin),
                maximum: Number(form.speedMax),
                steps: Number(form.speedSteps),
              },
            ],
          }),
        },
      );
      setRun(result);
      await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <h2>設計スイープ(Step 11)</h2>
      <p className="note">
        翼幅×巡航速度のグリッドを初期サイジングで評価します(解析的推定)。
        <strong>PBMは最適解を自動採用しません。</strong>
        候補とパレートフロントを提示するので、採用判断はチームで行ってください。
      </p>
      {error && <p className="error">{error}</p>}
      <form className="card" onSubmit={runSweep}>
        <div className="grid2">
          <label>
            翼幅 最小/最大/分割 [m]
            <span style={{ display: "flex", gap: "0.4rem" }}>
              <input type="number" step="any" value={form.spanMin} onChange={(e) => setForm({ ...form, spanMin: e.target.value })} />
              <input type="number" step="any" value={form.spanMax} onChange={(e) => setForm({ ...form, spanMax: e.target.value })} />
              <input type="number" min={2} max={15} value={form.spanSteps} onChange={(e) => setForm({ ...form, spanSteps: e.target.value })} />
            </span>
          </label>
          <label>
            巡航速度 最小/最大/分割 [m/s]
            <span style={{ display: "flex", gap: "0.4rem" }}>
              <input type="number" step="any" value={form.speedMin} onChange={(e) => setForm({ ...form, speedMin: e.target.value })} />
              <input type="number" step="any" value={form.speedMax} onChange={(e) => setForm({ ...form, speedMax: e.target.value })} />
              <input type="number" min={2} max={15} value={form.speedSteps} onChange={(e) => setForm({ ...form, speedSteps: e.target.value })} />
            </span>
          </label>
        </div>
        <button type="submit" disabled={busy || data.requirements === null}>
          スイープを実行
        </button>
        {data.requirements === null && (
          <p className="note">先に要求仕様(Step 2)を入力してください。</p>
        )}
      </form>

      {run && (
        <div className="card">
          <p className="note">
            評価 {run.outputs.evaluated} 案 / 可行 {run.outputs.feasible_count} 案 /
            パレート {run.outputs.pareto_count} 案(必要出力の小さい順、上位15件表示)
          </p>
          {run.outputs.warnings.map((w) => (
            <p key={w.code} className={`warn-${w.severity}`}>
              [{w.code}] {w.message}
            </p>
          ))}
          <table>
            <thead>
              <tr>
                <th>翼幅 [m]</th><th>速度 [m/s]</th><th>必要出力 [W]</th><th>L/D</th>
                <th>翼面積 [m²]</th><th>可行</th><th>パレート</th>
              </tr>
            </thead>
            <tbody>
              {run.outputs.candidates.slice(0, 15).map((c, i) => (
                <tr
                  key={i}
                  className={!c.feasible ? "warn-violation" : c.pareto ? "warn-info" : ""}
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
        </div>
      )}
    </>
  );
}
