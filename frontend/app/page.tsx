"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { apiFetch, Project, ProjectCreate } from "@/lib/api";

const EMPTY_FORM: ProjectCreate = {
  team_name: "",
  aircraft_name: "",
  design_year: new Date().getFullYear() + 1,
  category: "human_powered_propeller",
  design_lead: "",
  unit_system: "SI",
  version: "v0.1",
  design_goal: "",
};

export default function HomePage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [form, setForm] = useState<ProjectCreate>(EMPTY_FORM);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const reload = useCallback(async () => {
    try {
      setProjects(await apiFetch<Project[]>("/api/projects"));
      setError(null);
    } catch (e) {
      setError(
        `プロジェクト一覧を取得できません(バックエンドは起動していますか?): ${String(e)}`,
      );
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const create = async (ev: React.FormEvent) => {
    ev.preventDefault();
    setLoading(true);
    try {
      await apiFetch<Project>("/api/projects", {
        method: "POST",
        body: JSON.stringify(form),
      });
      setForm(EMPTY_FORM);
      await reload();
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <h1>Project BirdMan</h1>
      <p className="note">
        人力飛行機設計支援プラットフォーム — Phase 1: 初期サイジングMVP。
        計算結果は解析的推定であり、実機の飛行安全を保証しません。
      </p>
      {error && <p className="error">{error}</p>}

      <h2>プロジェクト一覧</h2>
      {projects.length === 0 ? (
        <p>プロジェクトがありません。下のフォームから作成してください。</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>機体名</th>
              <th>チーム</th>
              <th>年度</th>
              <th>部門</th>
              <th>状態</th>
              <th>設計責任者</th>
            </tr>
          </thead>
          <tbody>
            {projects.map((p) => (
              <tr key={p.id}>
                <td>
                  <Link href={`/projects/${p.id}`}>{p.aircraft_name}</Link>
                </td>
                <td>{p.team_name}</td>
                <td>{p.design_year}</td>
                <td>{p.category}</td>
                <td>
                  <span className={`badge ${p.status}`}>{p.status}</span>
                </td>
                <td>{p.design_lead}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <h2>新規プロジェクト作成</h2>
      <form className="card" onSubmit={create}>
        <div className="grid2">
          <label>
            チーム名
            <input
              required
              value={form.team_name}
              onChange={(e) => setForm({ ...form, team_name: e.target.value })}
            />
          </label>
          <label>
            機体名
            <input
              required
              value={form.aircraft_name}
              onChange={(e) =>
                setForm({ ...form, aircraft_name: e.target.value })
              }
            />
          </label>
          <label>
            設計年度
            <input
              type="number"
              min={1977}
              max={2100}
              required
              value={form.design_year}
              onChange={(e) =>
                setForm({ ...form, design_year: Number(e.target.value) })
              }
            />
          </label>
          <label>
            部門
            <select
              value={form.category}
              onChange={(e) => setForm({ ...form, category: e.target.value })}
            >
              <option value="glider">滑空機部門(glider)</option>
              <option value="human_powered_propeller">
                人力プロペラ機部門(human_powered_propeller)
              </option>
              <option value="other">その他(other)</option>
            </select>
          </label>
          <label>
            設計責任者
            <input
              required
              value={form.design_lead}
              onChange={(e) =>
                setForm({ ...form, design_lead: e.target.value })
              }
            />
          </label>
          <label>
            バージョン
            <input
              value={form.version}
              onChange={(e) => setForm({ ...form, version: e.target.value })}
            />
          </label>
        </div>
        <label>
          設計目標
          <input
            style={{ width: "100%" }}
            value={form.design_goal}
            onChange={(e) => setForm({ ...form, design_goal: e.target.value })}
          />
        </label>
        <button type="submit" disabled={loading}>
          作成
        </button>
      </form>
    </>
  );
}
