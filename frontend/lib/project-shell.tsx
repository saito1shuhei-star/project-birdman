"use client";

// プロジェクトシェル(案A+Bハイブリッドの共通枠)。
// ヘッダー・工程ステッパー・概要ダッシュボードが使う「最新状態のサマリー」を
// 一括ロードし、各工程ページは変更後に refresh() を呼ぶ。

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import {
  AeroAnalysisRun,
  AnalysisRunLite,
  apiFetch,
  CalcWarning,
  MassItem,
  MassProperties,
  Project,
  RequirementSpecOut,
  SizingRun,
  WingPlanformOut,
} from "@/lib/api";

export type SweepRunLite = {
  id: string;
  outputs: {
    evaluated: number;
    feasible_count: number;
    pareto_count: number;
  };
  created_at: string;
};

export type TransitionsInfo = {
  current: string;
  allowed: string[];
  actor_required: string[];
};

export type ApprovalEntry = {
  id: string;
  from_state: string;
  to_state: string;
  actor: string | null;
  comment: string | null;
  created_at: string;
};

export type ProjectShellData = {
  requirements: RequirementSpecOut | null;
  sizing: SizingRun | null;
  planform: WingPlanformOut | null;
  aero: AeroAnalysisRun | null;
  massItems: MassItem[];
  massProps: MassProperties | null;
  stability: AnalysisRunLite | null;
  spar: AnalysisRunLite | null;
  sweep: SweepRunLite | null;
  transitions: TransitionsInfo | null;
  approvals: ApprovalEntry[];
};

type ShellState = {
  project: Project | null;
  data: ProjectShellData;
  loading: boolean;
  refresh: () => Promise<void>;
};

const EMPTY: ProjectShellData = {
  requirements: null,
  sizing: null,
  planform: null,
  aero: null,
  massItems: [],
  massProps: null,
  stability: null,
  spar: null,
  sweep: null,
  transitions: null,
  approvals: [],
};

const ShellContext = createContext<ShellState>({
  project: null,
  data: EMPTY,
  loading: true,
  refresh: async () => {},
});

async function tryFetch<T>(path: string): Promise<T | null> {
  try {
    return await apiFetch<T>(path);
  } catch {
    return null; // 404(未入力)・409(前提不足)はnull扱い
  }
}

export function ProjectShellProvider({
  projectId,
  children,
}: {
  projectId: string;
  children: React.ReactNode;
}) {
  const [project, setProject] = useState<Project | null>(null);
  const [data, setData] = useState<ProjectShellData>(EMPTY);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    const p = await tryFetch<Project>(`/api/projects/${projectId}`);
    setProject(p);
    if (!p) {
      setLoading(false);
      return;
    }
    const base = `/api/projects/${projectId}`;
    const [
      requirements,
      sizingRuns,
      planform,
      aeroRuns,
      massItems,
      massProps,
      stabilityRuns,
      sparRuns,
      sweepRuns,
      transitions,
      approvals,
    ] = await Promise.all([
      tryFetch<RequirementSpecOut>(`${base}/requirements`),
      tryFetch<SizingRun[]>(`${base}/sizing-runs`),
      tryFetch<WingPlanformOut>(`${base}/planform`),
      tryFetch<AeroAnalysisRun[]>(`${base}/aero-analyses`),
      tryFetch<MassItem[]>(`${base}/mass-items`),
      tryFetch<MassProperties>(`${base}/mass-properties`),
      tryFetch<AnalysisRunLite[]>(`${base}/stability-analyses`),
      tryFetch<AnalysisRunLite[]>(`${base}/spar-analyses`),
      tryFetch<SweepRunLite[]>(`${base}/design-sweeps`),
      tryFetch<TransitionsInfo>(`${base}/transitions`),
      tryFetch<ApprovalEntry[]>(`${base}/approvals`),
    ]);
    // sizing一覧は要約のみのため、最新の全文を個別取得
    let sizing: SizingRun | null = null;
    const sizingList = sizingRuns as unknown as { id: string }[] | null;
    if (sizingList && sizingList.length > 0) {
      sizing = await tryFetch<SizingRun>(`/api/sizing-runs/${sizingList[0].id}`);
    }
    setData({
      requirements,
      sizing,
      planform,
      aero: aeroRuns && aeroRuns.length > 0 ? aeroRuns[0] : null,
      massItems: massItems ?? [],
      massProps,
      stability: stabilityRuns && stabilityRuns.length > 0 ? stabilityRuns[0] : null,
      spar: sparRuns && sparRuns.length > 0 ? sparRuns[0] : null,
      sweep: sweepRuns && sweepRuns.length > 0 ? sweepRuns[0] : null,
      transitions,
      approvals: approvals ?? [],
    });
    setLoading(false);
  }, [projectId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return (
    <ShellContext.Provider value={{ project, data, loading, refresh }}>
      {children}
    </ShellContext.Provider>
  );
}

export function useProjectShell(): ShellState {
  return useContext(ShellContext);
}

// 工程ごとの完了・違反状態(ステッパーと概要が共用)
export type StepState = {
  done: boolean;
  violations: number;
  warnings: number;
};

export function violationsOf(warnings: CalcWarning[] | undefined): number {
  return (warnings ?? []).filter((w) => w.severity === "violation").length;
}

export function warningsOf(warnings: CalcWarning[] | undefined): number {
  return (warnings ?? []).filter((w) => w.severity === "warning").length;
}

export function computeStepStates(data: ProjectShellData): Record<string, StepState> {
  const zero = { violations: 0, warnings: 0 };
  return {
    requirements: { done: data.requirements !== null, ...zero },
    sizing: {
      done: data.sizing !== null,
      violations: violationsOf(data.sizing?.outputs.warnings),
      warnings: warningsOf(data.sizing?.outputs.warnings),
    },
    aero: {
      done: data.planform !== null && data.aero !== null,
      violations: violationsOf(data.aero?.outputs.warnings),
      warnings: warningsOf(data.aero?.outputs.warnings),
    },
    mass: {
      done: data.massItems.length > 0,
      violations: violationsOf(data.massProps?.warnings),
      warnings: warningsOf(data.massProps?.warnings),
    },
    stability: {
      done: data.stability !== null,
      violations: violationsOf(data.stability?.outputs.warnings),
      warnings: warningsOf(data.stability?.outputs.warnings),
    },
    structure: {
      done: data.spar !== null,
      violations: violationsOf(data.spar?.outputs.warnings),
      warnings: warningsOf(data.spar?.outputs.warnings),
    },
    optimize: { done: data.sweep !== null, ...zero },
    approval: {
      done: data.transitions?.current === "approved",
      ...zero,
    },
  };
}
