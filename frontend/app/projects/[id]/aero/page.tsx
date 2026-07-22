"use client";

// 主翼平面形(Step 4)+空力解析(Step 5)

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { AeroAnalysisRun, apiFetch, WingPlanformOut } from "@/lib/api";
import { useProjectShell } from "@/lib/project-shell";
import { sig4 } from "@/lib/ui";

type SectionForm = { y: string; chord: string; twist: string; airfoil: string };

const DEFAULT_SECTIONS: SectionForm[] = [
  { y: "0", chord: "1.2", twist: "0", airfoil: "DAE-11" },
  { y: "15", chord: "0.6", twist: "0", airfoil: "DAE-11" },
];

const DERIVED_LABELS: [string, string][] = [
  ["span", "翼幅 b"],
  ["area", "翼面積 S"],
  ["aspect_ratio", "アスペクト比 AR"],
  ["mean_chord", "平均翼弦 c̄"],
  ["taper_ratio", "テーパー比 λ"],
];

export default function AeroPage() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;
  const { data, refresh } = useProjectShell();
  const [sections, setSections] = useState<SectionForm[]>(DEFAULT_SECTIONS);
  const [planformOut, setPlanformOut] = useState<WingPlanformOut | null>(null);
  const [latestAero, setLatestAero] = useState<AeroAnalysisRun | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (data.planform) {
      setPlanformOut(data.planform);
      setSections(
        data.planform.planform.sections.map((s) => ({
          y: String(s.spanwise_position.value),
          chord: String(s.chord.value),
          twist: String(s.twist_deg),
          airfoil: s.airfoil,
        })),
      );
    }
    if (data.aero) setLatestAero(data.aero);
  }, [data.planform, data.aero]);

  const savePlanform = async () => {
    setBusy(true);
    setError(null);
    try {
      const saved = await apiFetch<WingPlanformOut>(
        `/api/projects/${projectId}/planform`,
        {
          method: "PUT",
          body: JSON.stringify({
            sections: sections.map((s) => ({
              spanwise_position: { value: Number(s.y), unit: "m" },
              chord: { value: Number(s.chord), unit: "m" },
              twist_deg: Number(s.twist),
              airfoil: s.airfoil,
            })),
          }),
        },
      );
      setPlanformOut(saved);
      await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const runAero = async () => {
    setBusy(true);
    setError(null);
    try {
      const run = await apiFetch<AeroAnalysisRun>(
        `/api/projects/${projectId}/aero-analyses`,
        { method: "POST" },
      );
      setLatestAero(run);
      await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <h2>主翼平面形(Step 4)</h2>
      {error && <p className="error">{error}</p>}
      <div className="card">
        <p className="note">左右対称翼の片翼を翼根(y=0)から翼端へ定義します。単位: m。</p>
        <table>
          <thead>
            <tr>
              <th>y [m](翼根からの距離)</th><th>翼弦 [m]</th><th>ねじり [deg]</th><th>翼型</th><th></th>
            </tr>
          </thead>
          <tbody>
            {sections.map((s, i) => (
              <tr key={i}>
                <td><input type="number" step="any" value={s.y} onChange={(e) => { const next = [...sections]; next[i] = { ...s, y: e.target.value }; setSections(next); }} /></td>
                <td><input type="number" step="any" value={s.chord} onChange={(e) => { const next = [...sections]; next[i] = { ...s, chord: e.target.value }; setSections(next); }} /></td>
                <td><input type="number" step="any" value={s.twist} onChange={(e) => { const next = [...sections]; next[i] = { ...s, twist: e.target.value }; setSections(next); }} /></td>
                <td><input value={s.airfoil} onChange={(e) => { const next = [...sections]; next[i] = { ...s, airfoil: e.target.value }; setSections(next); }} /></td>
                <td>
                  <button type="button" disabled={sections.length <= 2} onClick={() => setSections(sections.filter((_, j) => j !== i))}>削除</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <button
          type="button"
          onClick={() => {
            const last = sections[sections.length - 1];
            setSections([...sections, { ...last, y: String(Number(last.y) + 1) }]);
          }}
        >
          セクション追加
        </button>{" "}
        <button type="button" disabled={busy} onClick={savePlanform}>平面形を保存</button>
        {planformOut && (
          <>
            <p className="note">保存済み rev.{planformOut.revision} — 導出量(台形積分):</p>
            <table>
              <tbody>
                {DERIVED_LABELS.filter(([key]) => planformOut.derived[key]).map(([key, label]) => {
                  const q = planformOut.derived[key];
                  return (
                    <tr key={key}>
                      <td>{label}</td><td>{sig4(q.value)}</td>
                      <td>{q.unit === "dimensionless" ? "−" : q.unit}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </>
        )}
      </div>

      <h2>空力解析(Step 5)</h2>
      <div className="card">
        <p className="note">
          平面形のARと要求仕様の係数からモック解析(揚力線理論の近似)を実行します。
          XFLR5の実解析・取込はAPIから利用できます(API_SPEC参照)。
        </p>
        <button
          type="button"
          disabled={busy || !planformOut || data.requirements === null}
          onClick={runAero}
        >
          モック空力解析を実行(Step 5)
        </button>
        {latestAero && (
          <>
            <h3>空力解析結果(Step 5)</h3>
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
              )}
            </p>
            <p>
              最大揚抗比 (L/D)max ={" "}
              <strong>{sig4(latestAero.outputs.max_lift_to_drag)}</strong>(CL ={" "}
              {sig4(latestAero.outputs.cl_at_max_lift_to_drag)})
            </p>
            <table>
              <thead>
                <tr><th>迎角 α [deg]</th><th>CL</th><th>CD</th><th>L/D</th><th>失速</th></tr>
              </thead>
              <tbody>
                {latestAero.outputs.polar.map((p) => (
                  <tr key={p.alpha_deg} className={p.stalled ? "warn-warning" : ""}>
                    <td>{p.alpha_deg}</td>
                    <td>{sig4(p.cl)}</td>
                    <td>{sig4(p.cd)}</td>
                    <td>{p.cd > 0 ? sig4(p.cl / p.cd) : "−"}</td>
                    <td>{p.stalled ? "!" : ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </div>
    </>
  );
}
