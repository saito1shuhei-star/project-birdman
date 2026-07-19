import { expect, test } from "@playwright/test";

// ゴールデンパス: プロジェクト作成 → 要求仕様 → サイジング → 平面形 → 空力解析
// → 質量台帳 → 静安定 → 梁解析(T-206)。
// 表示文言はUI変更に追随してメンテナンスすること。

test("設計ワークフローの縦スライスが一通り動作する", async ({ page }) => {
  const aircraftName = `E2E-${Date.now()}`;

  // --- プロジェクト作成 ---
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Project BirdMan" })).toBeVisible();
  await page.getByLabel("チーム名").fill("E2Eチーム");
  await page.getByLabel("機体名").fill(aircraftName);
  await page.getByLabel("設計責任者").fill("Playwright");
  await page.getByRole("button", { name: "作成" }).click();

  // 一覧に現れたプロジェクトを開く
  await page.getByRole("link", { name: aircraftName }).click();
  await expect(page.getByText("要求仕様(Step 2)")).toBeVisible();

  // --- 要求仕様の保存(既定値のまま)とサイジング実行 ---
  await page.getByRole("button", { name: "要求仕様を保存" }).click();
  await expect(page.getByText(/要求仕様 rev\.1/)).toBeVisible();
  await page.getByRole("button", { name: "初期サイジングを実行(Step 3)" }).click();
  await expect(page.getByText("初期サイジング結果")).toBeVisible();
  // 既定入力(RC-1相当)では出力不足の違反警告が出る
  await expect(page.getByText("POWER_DEFICIT")).toBeVisible();
  // 解析的推定であることが明示される
  await expect(page.getByText("analytical_estimate").first()).toBeVisible();

  // --- 平面形の保存とモック空力解析 ---
  await page.getByRole("button", { name: "平面形を保存" }).click();
  await expect(page.getByText(/保存済み rev\.1/)).toBeVisible();
  await page
    .getByRole("button", { name: "モック空力解析を実行(Step 5)" })
    .click();
  await expect(page.getByText("空力解析結果(Step 5)")).toBeVisible();
  await expect(page.getByText(/実際のXFLR5解析ではありません/)).toBeVisible();
  await expect(page.getByText(/最大揚抗比/)).toBeVisible();

  // --- 質量台帳 ---
  await page.getByLabel("部品名").fill("主桁");
  await page.getByLabel("質量 [kg]", { exact: true }).fill("10");
  await page.getByLabel("x [m](機首から後方+)").fill("1.0");
  await page.getByRole("button", { name: "部品を追加" }).click();
  await expect(page.getByText("質量特性")).toBeVisible();
  await expect(page.getByText("総質量")).toBeVisible();

  // --- 静安定(平面形+台帳が揃ったので実行可能) ---
  await page.getByRole("button", { name: "静安定を計算" }).click();
  await expect(page.getByText("静安定余裕 SM")).toBeVisible();

  // --- 梁解析(人間確定パラメータを入力) ---
  await page.getByLabel("荷重倍数 n(要チーム確定)").fill("1.0");
  await page.getByLabel("ヤング率 E [GPa](要チーム確定)").fill("200");
  await page.getByLabel("許容応力 [MPa](要チーム確定)").fill("800");
  await page.getByLabel("要求安全率(要チーム確定)").fill("1.5");
  await page.getByRole("button", { name: "梁解析を実行" }).click();
  await expect(page.getByText("翼根曲げモーメント")).toBeVisible();
  await expect(page.getByText("安全率 SF")).toBeVisible();
});
