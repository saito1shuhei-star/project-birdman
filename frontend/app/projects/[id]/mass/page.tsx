"use client";

// 質量・重心台帳(Step 9)

import { useState } from "react";
import { useParams } from "next/navigation";
import { API_BASE, apiFetch, MassItem } from "@/lib/api";
import { useProjectShell } from "@/lib/project-shell";
import { sig4 } from "@/lib/ui";

const MASS_CATEGORIES: [string, string][] = [
  ["wing_structure", "主翼構造"],
  ["fuselage_structure", "胴体・フレーム"],
  ["tail_structure", "尾翼"],
  ["propulsion", "プロペラ・駆動系"],
  ["cockpit", "コックピット"],
  ["control", "操縦系統"],
  ["pilot", "パイロット"],
  ["contest_equipment", "大会搭載機材(カメラ等)"],
  ["other", "その他"],
];

type ItemForm = {
  name: string;
  category: string;
  mass: string;
  x: string;
  z: string;
  source: string;
};

const EMPTY_ITEM: ItemForm = {
  name: "",
  category: "wing_structure",
  mass: "",
  x: "0",
  z: "0",
  source: "estimated",
};

export default function MassPage() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;
  const { data, refresh } = useProjectShell();
  const [form, setForm] = useState<ItemForm>(EMPTY_ITEM);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const addItem = async (ev: React.FormEvent) => {
    ev.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await apiFetch<MassItem>(`/api/projects/${projectId}/mass-items`, {
        method: "POST",
        body: JSON.stringify({
          name: form.name,
          category: form.category,
          mass: { value: Number(form.mass), unit: "kg" },
          position_x: { value: Number(form.x), unit: "m" },
          position_z: { value: Number(form.z), unit: "m" },
          source: form.source,
        }),
      });
      setForm(EMPTY_ITEM);
      await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const removeItem = async (itemId: string) => {
    setBusy(true);
    try {
      await fetch(`${API_BASE}/api/mass-items/${itemId}`, { method: "DELETE" });
      await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const props = data.massProps;

  return (
    <>
      <h2>質量・重心台帳(Step 9)</h2>
      <p className="note">
        座標系: 原点=機首先端、x=後方+、y=右+、z=上+(A-135)。点質量近似(A-136)。
      </p>
      {error && <p className="error">{error}</p>}

      <div className="card">
        {data.massItems.length > 0 && (
          <table>
            <thead>
              <tr>
                <th>部品名</th><th>カテゴリ</th><th>質量</th><th>x / z [m]</th><th>出所</th><th></th>
              </tr>
            </thead>
            <tbody>
              {data.massItems.map((it) => (
                <tr key={it.id}>
                  <td>{it.name}</td>
                  <td>{MASS_CATEGORIES.find(([v]) => v === it.category)?.[1] ?? it.category}</td>
                  <td>{it.mass.value} {it.mass.unit}</td>
                  <td>{it.position_x.value} / {it.position_z.value}</td>
                  <td>{it.source === "measured" ? "実測" : "推定"}</td>
                  <td><button type="button" disabled={busy} onClick={() => removeItem(it.id)}>削除</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <form onSubmit={addItem}>
          <div className="grid2">
            <label>部品名<input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
            <label>カテゴリ
              <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
                {MASS_CATEGORIES.map(([v, label]) => (<option key={v} value={v}>{label}</option>))}
              </select>
            </label>
            <label>質量 [kg]<input required type="number" step="any" value={form.mass} onChange={(e) => setForm({ ...form, mass: e.target.value })} /></label>
            <label>出所
              <select value={form.source} onChange={(e) => setForm({ ...form, source: e.target.value })}>
                <option value="estimated">推定値</option>
                <option value="measured">実測値</option>
              </select>
            </label>
            <label>x [m](機首から後方+)<input type="number" step="any" value={form.x} onChange={(e) => setForm({ ...form, x: e.target.value })} /></label>
            <label>z [m](上方+)<input type="number" step="any" value={form.z} onChange={(e) => setForm({ ...form, z: e.target.value })} /></label>
          </div>
          <button type="submit" disabled={busy}>部品を追加</button>
        </form>
      </div>

      {props && (
        <div className="card">
          <h3>質量特性</h3>
          <p className="note">
            推定 {props.estimated_item_count} 件 / 実測 {props.measured_item_count} 件
          </p>
          {props.warnings.length > 0 && (
            <table>
              <tbody>
                {props.warnings.map((w) => (
                  <tr key={w.code} className={`warn-${w.severity}`}>
                    <td>{w.code}</td><td>{w.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <table>
            <tbody>
              {[
                ["total_mass", "総質量"],
                ["airframe_mass", "機体質量(パイロット除く)"],
                ["airframe_mass_target", "機体質量目標"],
                ["airframe_mass_delta", "目標との差"],
                ["cg_x", "重心 x"],
                ["cg_z", "重心 z"],
                ["inertia_yy", "ピッチ慣性 Iyy"],
              ]
                .filter(([k]) => props.quantities[k])
                .map(([k, label]) => {
                  const q = props.quantities[k];
                  return (
                    <tr key={k}>
                      <td>{label}</td><td>{sig4(q.value)}</td><td>{q.unit}</td>
                    </tr>
                  );
                })}
            </tbody>
          </table>
          {props.breakdown.length > 0 && (
            <>
              <h3>カテゴリ内訳</h3>
              <table>
                <tbody>
                  {props.breakdown.map((b) => (
                    <tr key={b.category}>
                      <td>{MASS_CATEGORIES.find(([v]) => v === b.category)?.[1] ?? b.category}</td>
                      <td>{sig4(b.mass.value)} kg</td>
                      <td>{sig4(b.fraction * 100)} %</td>
                      <td>{b.item_count} 件</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </div>
      )}
    </>
  );
}
