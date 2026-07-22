import { expect, Page, test } from "@playwright/test";

// ゴールデンパス(案A+Bハイブリッドレイアウト):
// 概要ダッシュボード → 工程ステッパーで各ページを巡回して全工程を実行する。
// 表示文言はUI変更に追随してメンテナンスすること。

async function goStep(page: Page, label: RegExp) {
  await page.locator("nav.stepper").getByRole("link", { name: label }).click();
}

test("設計ワークフローの縦スライスが一通り動作する", async ({ page }) => {
  const aircraftName = `E2E-${Date.now()}`;

  // --- プロジェクト作成 ---
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Project BirdMan" })).toBeVisible();
  await page.getByLabel("チーム名").fill("E2Eチーム");
  await page.getByLabel("機体名").fill(aircraftName);
  await page.getByLabel("設計責任者").fill("Playwright");
  await page.getByRole("button", { name: "作成" }).click();

  // 一覧からプロジェクトを開く → 概要ダッシュボード
  await page.getByRole("link", { name: aircraftName }).click();
  await expect(page.getByRole("heading", { name: "概要" })).toBeVisible();
  await expect(page.getByText("次にやること")).toBeVisible();

  // --- 要求仕様(Step 2) ---
  await goStep(page, /要求仕様/);
  await expect(page.getByText("要求仕様(Step 2)")).toBeVisible();
  await page.getByRole("button", { name: "要求仕様を保存" }).click();
  await expect(page.getByText(/要求仕様 rev\.1/)).toBeVisible();

  // --- 初期サイジング(Step 3) ---
  await goStep(page, /初期サイジング/);
  await page.getByRole("button", { name: "初期サイジングを実行(Step 3)" }).click();
  await expect(page.getByText("初期サイジング結果")).toBeVisible();
  await expect(page.getByText("POWER_DEFICIT")).toBeVisible();
  await expect(page.getByText("analytical_estimate").first()).toBeVisible();

  // --- 主翼・空力(Step 4–5) ---
  await goStep(page, /主翼・空力/);
  await page.getByRole("button", { name: "平面形を保存" }).click();
  await expect(page.getByText(/保存済み rev\.1/)).toBeVisible();
  await page.getByRole("button", { name: "モック空力解析を実行(Step 5)" }).click();
  await expect(page.getByText("空力解析結果(Step 5)")).toBeVisible();
  await expect(page.getByText(/実際のXFLR5解析ではありません/)).toBeVisible();
  await expect(page.getByText(/最大揚抗比/)).toBeVisible();

  // --- 質量・重心(Step 9) ---
  await goStep(page, /質量・重心/);
  await page.getByLabel("部品名").fill("主桁");
  await page.getByLabel("質量 [kg]", { exact: true }).fill("10");
  await page.getByLabel("x [m](機首から後方+)").fill("1.0");
  await page.getByRole("button", { name: "部品を追加" }).click();
  await expect(page.getByText("質量特性")).toBeVisible();
  await expect(page.getByText("総質量")).toBeVisible();

  // --- 安定性(Step 7) ---
  await goStep(page, /安定性/);
  await page.getByRole("button", { name: "静安定を計算" }).click();
  await expect(page.getByText("静安定余裕 SM")).toBeVisible();

  // --- 構造(Step 8) ---
  await goStep(page, /構造/);
  await page.getByLabel("荷重倍数 n(要チーム確定)").fill("1.0");
  await page.getByLabel("ヤング率 E [GPa](要チーム確定)").fill("200");
  await page.getByLabel("許容応力 [MPa](要チーム確定)").fill("800");
  await page.getByLabel("要求安全率(要チーム確定)").fill("1.5");
  await page.getByRole("button", { name: "梁解析を実行" }).click();
  await expect(page.getByText("翼根曲げモーメント")).toBeVisible();
  await expect(page.getByText("安全率 SF")).toBeVisible();

  // --- 最適化(Step 11) ---
  await goStep(page, /最適化/);
  await page.getByRole("button", { name: "スイープを実行" }).click();
  await expect(page.getByText(/評価 \d+ 案/)).toBeVisible();

  // --- 承認(T-304): analyzed → review_required → approved ---
  await goStep(page, /承認・レポート/);
  await page.getByLabel("判断者(actor)").fill("E2E設計責任者");
  await page.getByLabel("コメント").fill("E2E承認テスト");
  await page.getByRole("button", { name: /review_required へ遷移/ }).click();
  await expect(page.getByText("analyzed → review_required")).toBeVisible();
  await page.getByRole("button", { name: /approved へ遷移/ }).click();
  await expect(page.getByText("review_required → approved")).toBeVisible();
  await expect(page.getByText("(自動遷移)").first()).toBeVisible();

  // --- 概要に戻ると全工程が完了状態、承認済みでレポート導線が出る ---
  await goStep(page, /概要/);
  await expect(page.getByRole("heading", { name: "概要" })).toBeVisible();
  await expect(page.getByText("承認済み。")).toBeVisible();
  await expect(
    page.getByRole("link", { name: /設計レポートを確認する/ }),
  ).toBeVisible();
});
