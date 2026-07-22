// 工程ステッパーの定義(案A)。PROJECT_BRIEFのStep番号と画面の対応。

export type StepDef = {
  slug: string; // /projects/[id]/<slug>(空文字=概要)
  label: string;
  brief: string; // PROJECT_BRIEFのStep対応
};

export const PROJECT_STEPS: StepDef[] = [
  { slug: "", label: "概要", brief: "ダッシュボード" },
  { slug: "requirements", label: "要求仕様", brief: "Step 2" },
  { slug: "sizing", label: "初期サイジング", brief: "Step 3" },
  { slug: "aero", label: "主翼・空力", brief: "Step 4–5" },
  { slug: "mass", label: "質量・重心", brief: "Step 9" },
  { slug: "stability", label: "安定性", brief: "Step 7" },
  { slug: "structure", label: "構造(主桁)", brief: "Step 8" },
  { slug: "optimize", label: "最適化", brief: "Step 11" },
  { slug: "approval", label: "承認・レポート", brief: "Step 13" },
];
