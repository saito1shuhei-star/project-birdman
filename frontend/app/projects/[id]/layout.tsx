"use client";

import Link from "next/link";
import { useParams, usePathname } from "next/navigation";
import {
  computeStepStates,
  ProjectShellProvider,
  useProjectShell,
} from "@/lib/project-shell";
import { PROJECT_STEPS } from "@/lib/steps";

const sig4 = (v: number) => Number(v.toPrecision(4)).toString();

function ShellFrame({ children }: { children: React.ReactNode }) {
  const params = useParams<{ id: string }>();
  const pathname = usePathname();
  const { project, data, loading } = useProjectShell();

  if (loading && !project) {
    return <p>読み込み中…</p>;
  }
  if (!project) {
    return (
      <>
        <p>
          <Link href="/">← プロジェクト一覧</Link>
        </p>
        <p className="error">プロジェクトを取得できません(バックエンドは起動していますか?)</p>
      </>
    );
  }

  const states = computeStepStates(data);
  const basePath = `/projects/${params.id}`;
  const sizingQ = data.sizing?.outputs.quantities;

  return (
    <div className="shell">
      <header className="shell-header">
        <div className="shell-title">
          <Link href="/">← 一覧</Link>
          <h1>
            {project.aircraft_name}{" "}
            <span className={`badge ${project.status}`}>{project.status}</span>
          </h1>
          <span className="note">
            {project.team_name} / {project.design_year}年度 / {project.category}
          </span>
        </div>
        {sizingQ && (
          <div className="shell-kpis">
            <div className="kpi">
              <small>必要出力</small>
              <strong>{sig4(sizingQ["required_pilot_power"].value)} W</strong>
            </div>
            <div className="kpi">
              <small>出力余裕</small>
              <strong
                className={sizingQ["power_margin"].value < 0 ? "kpi-bad" : "kpi-good"}
              >
                {sig4(sizingQ["power_margin"].value)} W
              </strong>
            </div>
            <div className="kpi">
              <small>翼面積</small>
              <strong>{sig4(sizingQ["wing_area"].value)} m²</strong>
            </div>
            {data.massProps && (
              <div className="kpi">
                <small>機体質量</small>
                <strong>
                  {sig4(data.massProps.quantities["airframe_mass"].value)} kg
                </strong>
              </div>
            )}
            {data.stability && (
              <div className="kpi">
                <small>静安定余裕</small>
                <strong>
                  {sig4(
                    data.stability.outputs.quantities["static_margin"].value * 100,
                  )}{" "}
                  %
                </strong>
              </div>
            )}
          </div>
        )}
      </header>

      <div className="shell-body">
        <nav className="stepper" aria-label="設計工程">
          {PROJECT_STEPS.map((step, index) => {
            const href = step.slug ? `${basePath}/${step.slug}` : basePath;
            const active =
              step.slug === ""
                ? pathname === basePath
                : pathname.startsWith(`${basePath}/${step.slug}`);
            const state = step.slug ? states[step.slug] : undefined;
            return (
              <Link
                key={step.slug || "overview"}
                href={href}
                className={`step ${active ? "step-active" : ""}`}
              >
                <span className="step-no">
                  {step.slug === "" ? "◉" : state?.done ? "✓" : index}
                </span>
                <span className="step-label">
                  {step.label}
                  <small>{step.brief}</small>
                </span>
                {state && state.violations > 0 && (
                  <span className="step-flag step-flag-bad">!{state.violations}</span>
                )}
                {state && state.violations === 0 && state.warnings > 0 && (
                  <span className="step-flag step-flag-warn">{state.warnings}</span>
                )}
              </Link>
            );
          })}
        </nav>
        <div className="shell-content">{children}</div>
      </div>
    </div>
  );
}

export default function ProjectLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const params = useParams<{ id: string }>();
  return (
    <ProjectShellProvider projectId={params.id}>
      <ShellFrame>{children}</ShellFrame>
    </ProjectShellProvider>
  );
}
