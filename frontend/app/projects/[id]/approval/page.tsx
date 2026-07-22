"use client";

// 承認・レポート(Step 13 / T-304)

import { useState } from "react";
import { useParams } from "next/navigation";
import { apiFetch, reportUrl } from "@/lib/api";
import { useProjectShell } from "@/lib/project-shell";

export default function ApprovalPage() {
  const params = useParams<{ id: string }>();
  const { data, refresh } = useProjectShell();
  const [actor, setActor] = useState("");
  const [comment, setComment] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const transitions = data.transitions;

  const doTransition = async (to: string) => {
    setBusy(true);
    setError(null);
    try {
      await apiFetch(`/api/projects/${params.id}/transition`, {
        method: "POST",
        body: JSON.stringify({
          to,
          actor: actor.trim() || null,
          comment: comment.trim() || null,
        }),
      });
      await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <h2>設計状態・承認</h2>
      <p className="note">
        approved / rejected への遷移には判断者名が必要です。全遷移は監査ログに記録されます。
        承認は設計状態の承認であり、実機の飛行安全を保証するものではありません。
      </p>
      {error && <p className="error">{error}</p>}

      <div className="card">
        <div className="grid2">
          <label>
            判断者(actor)
            <input value={actor} onChange={(e) => setActor(e.target.value)} />
          </label>
          <label>
            コメント
            <input value={comment} onChange={(e) => setComment(e.target.value)} />
          </label>
        </div>
        {transitions &&
          transitions.allowed.map((to) => (
            <button
              key={to}
              type="button"
              disabled={
                busy ||
                (transitions.actor_required.includes(to) && actor.trim() === "")
              }
              onClick={() => doTransition(to)}
              style={{ marginRight: "0.5rem" }}
            >
              {to} へ遷移
              {transitions.actor_required.includes(to) ? "(判断者名必須)" : ""}
            </button>
          ))}
      </div>

      {data.sizing && (
        <p>
          <a href={reportUrl(data.sizing.id)} target="_blank" rel="noreferrer">
            設計レポートを開く(全工程の現況・式・仮定・承認履歴・免責を含む)
          </a>
        </p>
      )}

      {data.approvals.length > 0 && (
        <div className="card">
          <h3>状態遷移の監査ログ</h3>
          <table>
            <thead>
              <tr>
                <th>日時</th><th>遷移</th><th>判断者</th><th>コメント</th>
              </tr>
            </thead>
            <tbody>
              {data.approvals.map((a) => (
                <tr key={a.id}>
                  <td>{new Date(a.created_at).toLocaleString("ja-JP")}</td>
                  <td>{a.from_state} → {a.to_state}</td>
                  <td>{a.actor ?? "(自動遷移)"}</td>
                  <td>{a.comment ?? ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
