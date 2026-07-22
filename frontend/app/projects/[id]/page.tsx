"use client";

// 概要ダッシュボード(案B): KPI・違反の集約・次にやること・工程の状態一覧

import Link from "next/link";
import { useParams } from "next/navigation";
import { CalcWarning, reportUrl } from "@/lib/api";
import { computeStepStates, useProjectShell } from "@/lib/project-shell";
import { PROJECT_STEPS } from "@/lib/steps";

const sig4 = (v: number) => Number(v.toPrecision(4)).toString();

export default function ProjectOverviewPage() {
  const params = useParams<{ id: string }>();
  const { project, data, loading } = useProjectShell();
  if (loading || !project) return null;

  const base = `/projects/${params.id}`;
  const states = computeStepStates(data);
  const sizingQ = data.sizing?.outputs.quantities;

  // 全工程の違反・警告を集約(案Bの中核)
  const collected: { source: string; slug: string; w: CalcWarning }[] = [];
  const push = (source: string, slug: string, warnings?: CalcWarning[]) => {
    for (const w of warnings ?? []) collected.push({ source, slug, w });
  };
  push("初期サイジング", "sizing", data.sizing?.outputs.warnings);
  push("空力解析", "aero", data.aero?.outputs.warnings);
  push("質量・重心", "mass", data.massProps?.warnings);
  push("安定性", "stability", data.stability?.outputs.warnings);
  push("構造", "structure", data.spar?.outputs.warnings);
  const violations = collected.filter((c) => c.w.severity === "violation");
  const warnings = collected.filter((c) => c.w.severity === "warning");

  // 次にやること(未完了の最初の工程 or 違反対応)
  let nextAction: { label: string; href: string };
  if (!states.requirements.done) {
    nextAction = { label: "要求仕様を入力する(Step 2)", href: `${base}/requirements` };
  } else if (!states.sizing.done) {
    nextAction = { label: "初期サイジングを実行する(Step 3)", href: `${base}/sizing` };
  } else if (violations.length > 0) {
    nextAction = {
      label: `違反の解消: ${violations[0].w.code}(${violations[0].source})`,
      href: `${base}/${violations[0].slug}`,
    };
  } else if (!states.aero.done) {
    nextAction = { label: "主翼平面形と空力解析(Step 4–5)", href: `${base}/aero` };
  } else if (!states.mass.done) {
    nextAction = { label: "質量台帳に部品を登録する(Step 9)", href: `${base}/mass` };
  } else if (!states.stability.done) {
    nextAction = { label: "静安定を計算する(Step 7)", href: `${base}/stability` };
  } else if (!states.structure.done) {
    nextAction = { label: "主桁の梁解析を実行する(Step 8)", href: `${base}/structure` };
  } else if (!states.approval.done) {
    nextAction = { label: "レビューと承認へ進む", href: `${base}/approval` };
  } else {
    nextAction = { label: "設計レポートを確認する", href: `${base}/approval` };
  }

  return (
    <>
      <h2>概要</h2>
      <p className="note">
        計算結果は解析的推定・モックを含みます。実機の飛行安全を保証しません。
      </p>

      <div className="kpi-grid">
        <div className="kpi-card">
          <small>必要出力</small>
          <strong>{sizingQ ? `${sig4(sizingQ["required_pilot_power"].value)} W` : "—"}</strong>
        </div>
        <div className="kpi-card">
          <small>出力余裕</small>
          <strong className={sizingQ && sizingQ["power_margin"].value < 0 ? "kpi-bad" : ""}>
            {sizingQ ? `${sig4(sizingQ["power_margin"].value)} W` : "—"}
          </strong>
        </div>
        <div className="kpi-card">
          <small>揚抗比 L/D</small>
          <strong>{sizingQ ? sig4(sizingQ["lift_to_drag"].value) : "—"}</strong>
        </div>
        <div className="kpi-card">
          <small>機体質量(目標{data.requirements ? " " + data.requirements.spec.airframe_mass_target.value + data.requirements.spec.airframe_mass_target.unit : ""})</small>
          <strong>
            {data.massProps
              ? `${sig4(data.massProps.quantities["airframe_mass"].value)} kg`
              : "—"}
          </strong>
        </div>
        <div className="kpi-card">
          <small>静安定余裕 SM</small>
          <strong>
            {data.stability
              ? `${sig4(data.stability.outputs.quantities["static_margin"].value * 100)} %`
              : "—"}
          </strong>
        </div>
        <div className="kpi-card">
          <small>桁の安全率</small>
          <strong>
            {data.spar
              ? sig4(data.spar.outputs.quantities["safety_factor"].value)
              : "—"}
          </strong>
        </div>
      </div>

      <div className="card next-action">
        <strong>次にやること:</strong>{" "}
        <Link href={nextAction.href}>{nextAction.label} →</Link>
      </div>

      {states.approval.done && data.sizing && (
        <div className="card">
          <strong>承認済み。</strong>{" "}
          <a href={reportUrl(data.sizing.id)} target="_blank" rel="noreferrer">
            設計レポートを確認する(全工程の現況・式・仮定・承認履歴・免責を含む)
          </a>
          {violations.length > 0 && (
            <p className="note">
              ※ 承認済みですが未解消の違反が {violations.length} 件あります。下記を確認してください。
            </p>
          )}
        </div>
      )}

      {violations.length > 0 && (
        <>
          <h3>違反({violations.length}件)</h3>
          <table>
            <tbody>
              {violations.map((c, i) => (
                <tr key={i} className="warn-violation">
                  <td>
                    <Link href={`${base}/${c.slug}`}>{c.source}</Link>
                  </td>
                  <td>{c.w.code}</td>
                  <td>{c.w.message}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {warnings.length > 0 && (
        <>
          <h3>警告({warnings.length}件)</h3>
          <table>
            <tbody>
              {warnings.map((c, i) => (
                <tr key={i} className="warn-warning">
                  <td>
                    <Link href={`${base}/${c.slug}`}>{c.source}</Link>
                  </td>
                  <td>{c.w.code}</td>
                  <td>{c.w.message}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      <h3>工程の状態</h3>
      <table>
        <tbody>
          {PROJECT_STEPS.filter((s) => s.slug).map((step) => {
            const st = states[step.slug];
            return (
              <tr key={step.slug}>
                <td>
                  <Link href={`${base}/${step.slug}`}>{step.label}</Link>{" "}
                  <span className="note">({step.brief})</span>
                </td>
                <td>{st.done ? "✓ 完了" : "未着手"}</td>
                <td>
                  {st.violations > 0 && (
                    <span className="step-flag step-flag-bad">違反 {st.violations}</span>
                  )}{" "}
                  {st.warnings > 0 && (
                    <span className="step-flag step-flag-warn">警告 {st.warnings}</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </>
  );
}
