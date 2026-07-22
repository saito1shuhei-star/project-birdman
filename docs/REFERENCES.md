# REFERENCES — 外部情報源一覧

Codex版PBM(commit 6a9e400)のREFERENCES.mdから統合。接続実装の移植状況は
[INTEGRATION_PLAN.md](INTEGRATION_PLAN.md) を参照。

## 気象・観測情報(T-511で統合予定)

- **Open-Meteo** — [Weather API](https://open-meteo.com/en/docs)。現在の風速・風向・突風・気温・気圧
- **NASA POWER** — [API](https://power.larc.nasa.gov/docs/services/api/)。過去の日別風速・気温・気圧
- **NOAA** — [NCEI Data Service API](https://www.ncei.noaa.gov/support/access-data-service-api-user-documentation) / [観測地点検索](https://www.ncei.noaa.gov/access/search/)
- **気象庁** — [気象データ高度利用ポータル](https://www.data.jma.go.jp/developer/) / [アメダス地点表](https://www.jma.go.jp/bosai/amedas/const/amedastable.json) / [最新データ時刻](https://www.jma.go.jp/bosai/amedas/data/latest_time.txt) / [地域区分](https://www.jma.go.jp/bosai/common/const/area.json) / [防災情報XML](https://xml.kishou.go.jp/)
  - 近いアメダス観測所の候補表示・観測地点選択・地域選択に使用

**運用上の注意**: 外部気象情報だけで飛行可否を決めない。現地風速計・公式発表・運営責任者の判断を優先する(Codex版の設計方針を継承)。

## 地図・標高(T-511/T-513で統合予定)

- [Google Maps Elevation API](https://developers.google.com/maps/documentation/elevation) / [Geocoding API](https://developers.google.com/maps/documentation/geocoding)
- [APIキー管理のベストプラクティス](https://docs.cloud.google.com/docs/authentication/api-keys-best-practices) — **秘密鍵はリポジトリに保存しない**(NFR-008)

## 数値・単位・セキュリティ

- [NIST SI単位資料](https://www.nist.gov/pml/special-publication-811/nist-guide-si-appendix-b-conversion-factors/nist-guide-si-appendix-b8) — 標準重力加速度 9.80665 m/s² の根拠(A-001)
- [FastAPI Security](https://fastapi.tiangolo.com/reference/security/) / [NIST RBAC](https://csrc.nist.gov/Projects/Role-Based-Access-Control) — 認証・ロール管理(T-514)

## XROTOR(統合済み)

- [MIT XROTOR配布ページ](https://web.mit.edu/drela/Public/web/xrotor/) / [User Guide](https://web.mit.edu/drela/Public/web/xrotor/xrotor_doc.txt)
- **XROTOR 7.55向け**の入力生成(ARBI/AERO/OPER)・実行証跡・サマリ取込を実装済み
  (`pbm/domain/xrotor_case.py`, `pbm/adapters/xrotor.py`)。
  **7.69へ変更する場合は入力順と結果形式の再確認が必要**

## XFLR5(統合済み)

- [公式サイト](https://www.xflr5.tech/) / [リリースノート](https://www.xflr5.tech/ReleaseNotes.htm) / [6.62配布](https://sourceforge.net/projects/xflr5/files/6.62/)
- [コマンド実行に関する公式Ticket #57](https://sourceforge.net/p/xflr5/tickets/57/) — **XFLR5はコマンドライン実行非対応**。
  そのため入力ZIP作成→GUI手動実行→結果表取込を正式経路とする(`pbm/domain/xflr5_case.py`)

## Autodesk Fusion(T-516で統合予定)

- [UserParameters API](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/UserParameters.htm) / [パラメーター入出力](https://help.autodesk.com/cloudhelp/ENU/Fusion-Model/files/SLD-IMPORT-EXPORT-PARAMETERS.htm) / [ExportManager API](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/ExportManager.htm)
- 方式: PBMからCSV/受け渡しZIPを作成し、Fusion側で人が確認して読み込む(自動操作しない)。
  **承認済み設計のみ出力可(FR-004)**

## 大会規則

- 「鳥人間コンテスト2025」ルールブック(讀賣テレビ) — 要約は [CONTEST_RULES_2025_NOTES.md](CONTEST_RULES_2025_NOTES.md)。
  **著作物のためPDF本体をリポジトリにコミットしない**
