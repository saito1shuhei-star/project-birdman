# INTEGRATION_PLAN — Codex版PBMの統合計画

決定(2026-07-22、ユーザー指示): **本リポジトリ(GitHub版)を本流とし、Codex版PBMの機能をこちらへ統合する。**

- 統合元: `C:/Users/shusa/Documents/Codex/2026-07-19/project-birdman-project-brief-md-requirements`(commit `6a9e400`、本体44ファイル+テスト21ファイル、API v0.8.0)
- 統合元の性格: 大会運用・データ管理・外部連携に強い(認証、全操作履歴、気象連携、XROTOR/XFLR5実連携、Fusionハンドオフ、大会運用画面)
- 本リポジトリの性格: 設計計算・検証・レポートに強い(初期サイジング16式、静安定、梁、スイープ、数値回帰テスト266件、E2E、CI)
- 両者は同じ2025年版ルールブックを情報源とする

## 統合ステータス

### ✅ 統合済み(2026-07-22)

| 機能 | 統合元 | 統合先 | 備考 |
|---|---|---|---|
| XROTOR構造化入力(ARBI/AERO/OPERスクリプト生成、7.55対応) | xrotor_input.py | `pbm/domain/xrotor_case.py` | 単位付き検証をpint基盤へ適応(角度はensure_angle) |
| XROTOR実実行(隔離サブプロセス・証跡保持) | xrotor_adapter.py | `pbm/adapters/xrotor.py` `run_script()` | 要PBM_XROTOR_PATH+PBM_XROTOR_VERSION。入力/stdout/stderr/生成ファイルをBinaryArtifactで保存 |
| XROTORサマリ取込(execution_mode=imported) | xrotor_input.py | 同上+`POST /xrotor-imports` | 不完全なサマリは拒否(捏造しない) |
| XFLR5ハンドオフ(入力ZIP・「結果ではない」明示) | xflr5.py | `pbm/domain/xflr5_case.py`+`POST /xflr5-handoffs` | XFLR5 6.62はコマンド実行非対応(Ticket #57)のため手動実行が正式経路 |
| XFLR5結果表取込(alpha/CL/CD/Cm必須) | xflr5.py | 同上+`POST /xflr5-imports` | 派生値の追加なし(derived_values_added=false) |
| BinaryArtifact(base64+SHA-256証跡) | xrotor_adapter.py | `pbm/adapters/base.py` | 全外部ソフト共通 |
| 外部情報源一覧 | REFERENCES.md | `docs/REFERENCES.md` | 気象API・XROTOR/XFLR5/Fusion・NIST等 |

### 📋 未統合(優先度順にTASKS.mdへ登録済み)

| 機能 | 統合元(参照先) | タスク | 優先度 |
|---|---|---|---|
| 質量台帳の変更履歴+target種別 | mass_properties_persistence.py | T-510 | 高(こちらの既知の弱点) |
| 気象アダプター(Open-Meteo/NASA POWER/NOAA/気象庁アメダス)+観測地点選択 | external_data.py, weather_sites.py | T-511 | 高 |
| フライト条件判断の記録(現地風速の瞬間値/時間平均、公式発表、チーム判断と実行委員会決定の分離) | flight_conditions.py | T-512 | 高 |
| 大会運用一式(規則チェックリスト・役割(ナビゲーター/マナーリーダー)・機体チェック履歴・提出物版管理・当日指示・禁止区域地図) | api.py(competition operations) | T-513 | 高 |
| 認証(利用者ID+秘密鍵)・ロール(designer/reviewer/operations_manager/administrator)・全操作履歴 | auth.py, roles.py | T-514 | 中(Web公開の前提) |
| 機体ジオメトリ一元管理(胴体・尾翼・プロペラ、履歴付き) | aircraft_geometry.py | T-515 | 中 |
| Fusionハンドオフ(CSV/ZIP出力+人による確認記録) | fusion_handoff.py, engineering_workflow_*.py | T-516 | 中(Phase 5前倒し。**承認済み設計のみ=FR-004ガード必須**) |
| XROTOR比較画面(設計点比較) | xrotor_comparison*.py | T-517 | 中 |
| Excel解析テンプレート出力 | excel_adapter.py, outputs/*.xlsx | T-518 | 低 |
| ルールブック原本の版管理(rulebook_sources) | rulebook_sources.py | T-513に含む | — |

## 統合時の規約統一(こちらの定義を正とする)

| 項目 | 本流の定義 | Codex版からの変換 |
|---|---|---|
| 部門 | glider / human_powered_propeller / other | human_powered_propellerのみ→そのまま。**滑空機部門の欠落はこちらで解消済み** |
| ExecutionMode | real / mock / imported / analytical_estimate(4値) | real/mock+XFLR5のmanual→importedへ写像 |
| 質量カテゴリ | wing_structure等9種(contest_equipment含む) | wing→wing_structure, frame→fuselage_structure, fairing→cockpit, drivetrain+propeller→propulsion, controls→control |
| 座標系 | A-135(機首原点、x後方+) | 統合元reference-frames機能はT-515で吸収 |
| 単位 | Pint(Quantity=value+unit) | 統合元units.pyのDimension enumは移植せずpintへ適応 |
| TakeoffMethod | (未実装。導入時はassisted等の禁止方式に規則注記CON-008を付す) | — |

## データ移行

Codex版DBの実データは「気象取得履歴0件・観測地点0件・規則原本0件・XROTOR実解析0件」(ユーザー確認済み)のため、**データ移行は不要**。設計データが入る前に統合を決定できたことが幸い。

## 8765側の扱い

- 新規データの入力は本リポジトリ側に一本化することを推奨(二重管理の防止)
- Codex版リポジトリは参照用として保持(上表の「統合元」パス)。統合完了後にアーカイブ判断
