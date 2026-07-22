"use client";

// 構造: 主桁の簡易梁解析(Step 8)

import { useState } from "react";
import { useParams } from "next/navigation";
import { AnalysisRunLite, apiFetch } from "@/lib/api";
import { useProjectShell } from "@/lib/project-shell";
import { ExecutionBadge, sig4, WarningList } from "@/lib/ui";

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

const DEFAULT_FORM: SparForm = {
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

export default function StructurePage() {
  const params = useParams<{ id: string }>();
  const { data, refresh } = useProjectShell();
  const [form, setForm] = useState<SparForm>(DEFAULT_FORM);
  const [latest, setLatest] = useState<AnalysisRunLite | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const run = latest ?? data.spar;

  const runSpar = async (ev: React.FormEvent) => {
    ev.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const hasTaper = form.tipD.trim() !== "" && form.tipT.trim() !== "";
      const result = await apiFetch<AnalysisRunLite>(
        `/api/projects/${params.id}/spar-analyses`,
        {
          method: "POST",
          body: JSON.stringify({
            half_span: { value: Number(form.halfSpan), unit: "m" },
            load_factor: Number(form.loadFactor),
            total_mass: { value: Number(form.totalMass), unit: "kg" },
            lift_distribution: form.distribution,
            spar_outer_diameter: { value: Number(form.d), unit: "m" },
            spar_wall_thickness: { value: Number(form.t), unit: "mm" },
            ...(hasTaper
              ? {
                  spar_tip_outer_diameter: { value: Number(form.tipD), unit: "m" },
                  spar_tip_wall_thickness: { value: Number(form.tipT), unit: "mm" },
                }
              : {}),
            elastic_modulus: { value: Number(form.e), unit: "GPa" },
            allowable_stress: { value: Number(form.sigmaAllow), unit: "MPa" },
            required_safety_factor: Number(form.requiredSf),
          }),
        },
      );
      setLatest(result);
      await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <h2>主桁の簡易梁解析(Step 8)</h2>
      <p className="note">
        片持ち梁モデル(翼根固定・円管断面・自重軽減なし=安全側)。座屈はスクリーニングのみ(A-144)。
        <strong>
          荷重倍数・材料定数・許容応力・要求安全率はチームが確定して入力してください(既定値なし)。
        </strong>
      </p>
      {error && <p className="error">{error}</p>}
      <form className="card" onSubmit={runSpar}>
        <div className="grid2">
          <label>半翼幅 [m]<input type="number" step="any" value={form.halfSpan} onChange={(e) => setForm({ ...form, halfSpan: e.target.value })} /></label>
          <label>荷重倍数 n(要チーム確定)<input required type="number" step="any" value={form.loadFactor} onChange={(e) => setForm({ ...form, loadFactor: e.target.value })} /></label>
          <label>全備質量 [kg]<input type="number" step="any" value={form.totalMass} onChange={(e) => setForm({ ...form, totalMass: e.target.value })} /></label>
          <label>揚力分布
            <select value={form.distribution} onChange={(e) => setForm({ ...form, distribution: e.target.value })}>
              <option value="elliptic">楕円分布</option>
              <option value="uniform">一様分布(保守側)</option>
            </select>
          </label>
          <label>桁外径 D [m]<input type="number" step="any" value={form.d} onChange={(e) => setForm({ ...form, d: e.target.value })} /></label>
          <label>肉厚 t [mm]<input type="number" step="any" value={form.t} onChange={(e) => setForm({ ...form, t: e.target.value })} /></label>
          <label>翼端外径 [m](任意・テーパー桁)<input type="number" step="any" value={form.tipD} onChange={(e) => setForm({ ...form, tipD: e.target.value })} /></label>
          <label>翼端肉厚 [mm](任意・テーパー桁)<input type="number" step="any" value={form.tipT} onChange={(e) => setForm({ ...form, tipT: e.target.value })} /></label>
          <label>ヤング率 E [GPa](要チーム確定)<input required type="number" step="any" value={form.e} onChange={(e) => setForm({ ...form, e: e.target.value })} /></label>
          <label>許容応力 [MPa](要チーム確定)<input required type="number" step="any" value={form.sigmaAllow} onChange={(e) => setForm({ ...form, sigmaAllow: e.target.value })} /></label>
          <label>要求安全率(要チーム確定)<input required type="number" step="any" value={form.requiredSf} onChange={(e) => setForm({ ...form, requiredSf: e.target.value })} /></label>
        </div>
        <button type="submit" disabled={busy}>梁解析を実行</button>
      </form>

      {run && (
        <div className="card">
          <ExecutionBadge execution={run.execution} />
          <WarningList warnings={run.outputs.warnings} />
          <table>
            <tbody>
              {[
                ["root_shear", "翼根せん断力"],
                ["root_bending_moment", "翼根曲げモーメント"],
                ["max_bending_stress", "最大曲げ応力"],
                ["max_stress_position", "最大応力位置"],
                ["tip_deflection", "翼端たわみ"],
                ["tip_deflection_ratio", "たわみ比 δ/s"],
                ["safety_factor", "安全率 SF"],
                ["buckling_stress_ratio_max", "座屈応力比(最大)"],
              ]
                .filter(([k]) => run.outputs.quantities[k])
                .map(([k, label]) => {
                  const q = run.outputs.quantities[k];
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
        </div>
      )}
    </>
  );
}
