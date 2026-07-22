"use client";

// 静安定(Step 7)

import { useState } from "react";
import { useParams } from "next/navigation";
import { AnalysisRunLite, apiFetch } from "@/lib/api";
import { useProjectShell } from "@/lib/project-shell";
import { ExecutionBadge, sig4, WarningList } from "@/lib/ui";

type StabilityForm = { st: string; lt: string; xac: string; art: string };
const DEFAULT_FORM: StabilityForm = { st: "2.5", lt: "4", xac: "0.9", art: "8" };

export default function StabilityPage() {
  const params = useParams<{ id: string }>();
  const { data, refresh } = useProjectShell();
  const [form, setForm] = useState<StabilityForm>(DEFAULT_FORM);
  const [latest, setLatest] = useState<AnalysisRunLite | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const run = latest ?? data.stability;
  const ready = data.planform !== null && data.massItems.length > 0 && data.requirements !== null;

  const runStability = async () => {
    setBusy(true);
    setError(null);
    try {
      const result = await apiFetch<AnalysisRunLite>(
        `/api/projects/${params.id}/stability-analyses`,
        {
          method: "POST",
          body: JSON.stringify({
            horizontal_tail_area: { value: Number(form.st), unit: "m^2" },
            tail_arm: { value: Number(form.lt), unit: "m" },
            wing_ac_position: { value: Number(form.xac), unit: "m" },
            tail_aspect_ratio: Number(form.art),
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
      <h2>静安定(Step 7)</h2>
      <p className="note">
        翼幾何は平面形(Step 4)、重心は質量台帳(Step 9)から取得します。
        胴体・プロペラの寄与は含まない簡易推定です(A-131)。
      </p>
      {error && <p className="error">{error}</p>}
      {!ready && (
        <p className="note">
          実行には要求仕様・主翼平面形・質量部品(1件以上)が必要です。
        </p>
      )}
      <div className="card">
        <div className="grid2">
          <label>水平尾翼面積 S_t [m²]<input type="number" step="any" value={form.st} onChange={(e) => setForm({ ...form, st: e.target.value })} /></label>
          <label>尾翼モーメントアーム l_t [m]<input type="number" step="any" value={form.lt} onChange={(e) => setForm({ ...form, lt: e.target.value })} /></label>
          <label>主翼空力中心 x_ac [m](機首から)<input type="number" step="any" value={form.xac} onChange={(e) => setForm({ ...form, xac: e.target.value })} /></label>
          <label>尾翼アスペクト比<input type="number" step="any" value={form.art} onChange={(e) => setForm({ ...form, art: e.target.value })} /></label>
        </div>
        <button type="button" disabled={busy || !ready} onClick={runStability}>
          静安定を計算
        </button>
      </div>

      {run && (
        <div className="card">
          <ExecutionBadge execution={run.execution} />
          <WarningList warnings={run.outputs.warnings} />
          <table>
            <tbody>
              {[
                ["tail_volume_horizontal", "水平尾翼容積 V_H"],
                ["neutral_point_x", "中立点 x_np"],
                ["cg_x", "重心 x_cg"],
                ["static_margin", "静安定余裕 SM"],
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
