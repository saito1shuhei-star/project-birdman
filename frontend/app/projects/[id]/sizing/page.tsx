"use client";

// 初期サイジング(Step 3): 実行・結果・式レポートリンク

import { useState } from "react";
import { useParams } from "next/navigation";
import { apiFetch, reportUrl, SizingRun } from "@/lib/api";
import { useProjectShell } from "@/lib/project-shell";
import { ExecutionBadge, sig4, WarningList } from "@/lib/ui";

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

export default function SizingPage() {
  const params = useParams<{ id: string }>();
  const { data, refresh } = useProjectShell();
  const [latestRun, setLatestRun] = useState<SizingRun | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const run = latestRun ?? data.sizing;

  const runSizing = async () => {
    setBusy(true);
    setError(null);
    try {
      const result = await apiFetch<SizingRun>(
        `/api/projects/${params.id}/sizing-runs`,
        { method: "POST" },
      );
      setLatestRun(result);
      await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <h2>初期サイジング(Step 3)</h2>
      <p className="note">
        最新の要求仕様(rev.{data.requirements?.revision ?? "—"})で定常水平飛行の
        理論式16本を計算します(解析的推定)。
      </p>
      {error && <p className="error">{error}</p>}
      <button
        type="button"
        disabled={busy || data.requirements === null}
        onClick={runSizing}
      >
        初期サイジングを実行(Step 3)
      </button>
      {data.requirements === null && (
        <p className="note">先に要求仕様(Step 2)を入力してください。</p>
      )}

      {run && (
        <>
          <h3>初期サイジング結果</h3>
          <ExecutionBadge execution={run.execution} />
          <p className="note">
            入力ハッシュ: <code>{run.input_hash.slice(0, 12)}…</code> / 要求仕様
            rev.{run.requirement_revision}
          </p>
          <WarningList warnings={run.outputs.warnings} />
          <table>
            <thead>
              <tr><th>項目</th><th>値(有効4桁)</th><th>単位</th></tr>
            </thead>
            <tbody>
              {RESULT_LABELS.filter(([key]) => run.outputs.quantities[key]).map(
                ([key, label]) => {
                  const q = run.outputs.quantities[key];
                  return (
                    <tr key={key}>
                      <td>{label}</td>
                      <td>{sig4(q.value)}</td>
                      <td>{q.unit === "dimensionless" ? "−" : q.unit}</td>
                    </tr>
                  );
                },
              )}
            </tbody>
          </table>
          <p>
            <a href={reportUrl(run.id)} target="_blank" rel="noreferrer">
              詳細レポートを開く(使用した式・仮定・免責を含む)
            </a>
          </p>
        </>
      )}
    </>
  );
}
