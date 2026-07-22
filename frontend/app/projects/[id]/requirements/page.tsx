"use client";

// 要求仕様(Step 2): 単位付き入力・保存・変更履歴

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { apiFetch, Quantity, RequirementSpec, RequirementSpecOut } from "@/lib/api";
import { useProjectShell } from "@/lib/project-shell";
import { QuantityField, QuantityForm } from "@/lib/ui";

type ReqForm = {
  pilot_mass: QuantityForm;
  airframe_mass_target: QuantityForm;
  pilot_power_sustained: QuantityForm;
  target_cruise_speed: QuantityForm;
  wingspan_limit: QuantityForm;
  air_density: QuantityForm;
  wind_speed_limit: QuantityForm;
  flight_altitude_limit: QuantityForm;
  pilot_age: string;
  cl_cruise: string;
  cl_max: string;
  cd0: string;
  oswald_efficiency: string;
  propeller_efficiency: string;
  drivetrain_efficiency: string;
};

const DEFAULT_FORM: ReqForm = {
  pilot_mass: { value: "60", unit: "kg" },
  airframe_mass_target: { value: "40", unit: "kg" },
  pilot_power_sustained: { value: "250", unit: "W" },
  target_cruise_speed: { value: "7.5", unit: "m/s" },
  wingspan_limit: { value: "30", unit: "m" },
  air_density: { value: "1.225", unit: "kg/m^3" },
  wind_speed_limit: { value: "5.0", unit: "m/s" },
  flight_altitude_limit: { value: "10.0", unit: "m" },
  pilot_age: "",
  cl_cruise: "1.0",
  cl_max: "1.4",
  cd0: "0.020",
  oswald_efficiency: "0.90",
  propeller_efficiency: "0.80",
  drivetrain_efficiency: "0.95",
};

const SPEC_FIELD_LABELS: Record<string, string> = {
  pilot_mass: "パイロット質量",
  airframe_mass_target: "機体質量目標",
  pilot_power_sustained: "パイロット持続出力",
  pilot_power_max: "パイロット最大出力",
  target_cruise_speed: "目標巡航速度",
  target_distance: "目標飛行距離",
  wingspan_limit: "翼幅制限",
  air_density: "空気密度",
  wind_speed_limit: "風速条件の上限",
  flight_altitude_limit: "飛行制限高度",
  pilot_age: "パイロット年齢",
  cl_cruise: "CL_cruise",
  cl_max: "CL_max",
  cd0: "CD0",
  oswald_efficiency: "オズワルド効率 e",
  propeller_efficiency: "プロペラ効率 η_prop",
  drivetrain_efficiency: "駆動系効率 η_drive",
};

function specDiff(prev: RequirementSpec, curr: RequirementSpec): string[] {
  const fmt = (v: unknown): string => {
    if (v == null) return "—";
    if (typeof v === "object" && "value" in (v as object)) {
      const q = v as Quantity;
      return `${q.value} ${q.unit}`;
    }
    return String(v);
  };
  const lines: string[] = [];
  for (const k of Object.keys(SPEC_FIELD_LABELS) as (keyof RequirementSpec)[]) {
    if (JSON.stringify(prev[k] ?? null) !== JSON.stringify(curr[k] ?? null)) {
      lines.push(`${SPEC_FIELD_LABELS[k]}: ${fmt(prev[k])} → ${fmt(curr[k])}`);
    }
  }
  return lines;
}

export default function RequirementsPage() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;
  const { refresh } = useProjectShell();
  const [form, setForm] = useState<ReqForm>(DEFAULT_FORM);
  const [revision, setRevision] = useState<number | null>(null);
  const [history, setHistory] = useState<RequirementSpecOut[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const req = await apiFetch<RequirementSpecOut>(
          `/api/projects/${projectId}/requirements`,
        );
        setRevision(req.revision);
        const s = req.spec;
        setForm({
          pilot_mass: { value: String(s.pilot_mass.value), unit: s.pilot_mass.unit },
          airframe_mass_target: {
            value: String(s.airframe_mass_target.value),
            unit: s.airframe_mass_target.unit,
          },
          pilot_power_sustained: {
            value: String(s.pilot_power_sustained.value),
            unit: s.pilot_power_sustained.unit,
          },
          target_cruise_speed: {
            value: String(s.target_cruise_speed.value),
            unit: s.target_cruise_speed.unit,
          },
          wingspan_limit: {
            value: String(s.wingspan_limit.value),
            unit: s.wingspan_limit.unit,
          },
          air_density: { value: String(s.air_density.value), unit: s.air_density.unit },
          wind_speed_limit: {
            value: String(s.wind_speed_limit.value),
            unit: s.wind_speed_limit.unit,
          },
          flight_altitude_limit: {
            value: String(s.flight_altitude_limit.value),
            unit: s.flight_altitude_limit.unit,
          },
          pilot_age: s.pilot_age != null ? String(s.pilot_age) : "",
          cl_cruise: String(s.cl_cruise),
          cl_max: String(s.cl_max),
          cd0: String(s.cd0),
          oswald_efficiency: String(s.oswald_efficiency),
          propeller_efficiency: String(s.propeller_efficiency),
          drivetrain_efficiency: String(s.drivetrain_efficiency),
        });
      } catch {
        // 未入力は既定値のまま
      }
      try {
        setHistory(
          await apiFetch<RequirementSpecOut[]>(
            `/api/projects/${projectId}/requirements/history`,
          ),
        );
      } catch {
        // 履歴なし
      }
    })();
  }, [projectId]);

  const save = async (ev: React.FormEvent) => {
    ev.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const saved = await apiFetch<RequirementSpecOut>(
        `/api/projects/${projectId}/requirements`,
        {
          method: "PUT",
          body: JSON.stringify({
            pilot_mass: { value: Number(form.pilot_mass.value), unit: form.pilot_mass.unit },
            airframe_mass_target: {
              value: Number(form.airframe_mass_target.value),
              unit: form.airframe_mass_target.unit,
            },
            pilot_power_sustained: {
              value: Number(form.pilot_power_sustained.value),
              unit: form.pilot_power_sustained.unit,
            },
            target_cruise_speed: {
              value: Number(form.target_cruise_speed.value),
              unit: form.target_cruise_speed.unit,
            },
            wingspan_limit: {
              value: Number(form.wingspan_limit.value),
              unit: form.wingspan_limit.unit,
            },
            air_density: {
              value: Number(form.air_density.value),
              unit: form.air_density.unit,
            },
            wind_speed_limit: {
              value: Number(form.wind_speed_limit.value),
              unit: form.wind_speed_limit.unit,
            },
            flight_altitude_limit: {
              value: Number(form.flight_altitude_limit.value),
              unit: form.flight_altitude_limit.unit,
            },
            pilot_age: form.pilot_age.trim() === "" ? null : Number(form.pilot_age),
            cl_cruise: Number(form.cl_cruise),
            cl_max: Number(form.cl_max),
            cd0: Number(form.cd0),
            oswald_efficiency: Number(form.oswald_efficiency),
            propeller_efficiency: Number(form.propeller_efficiency),
            drivetrain_efficiency: Number(form.drivetrain_efficiency),
          }),
        },
      );
      setRevision(saved.revision);
      setHistory(
        await apiFetch<RequirementSpecOut[]>(
          `/api/projects/${projectId}/requirements/history`,
        ),
      );
      await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <h2>要求仕様(Step 2){revision !== null && ` — 要求仕様 rev.${revision}`}</h2>
      {error && <p className="error">{error}</p>}
      <form className="card" onSubmit={save}>
        <div className="grid2">
          <QuantityField label="パイロット質量" field={form.pilot_mass} units={["kg", "g", "lb"]} onChange={(q) => setForm({ ...form, pilot_mass: q })} />
          <QuantityField label="機体質量目標" field={form.airframe_mass_target} units={["kg", "g", "lb"]} onChange={(q) => setForm({ ...form, airframe_mass_target: q })} />
          <QuantityField label="パイロット持続出力" field={form.pilot_power_sustained} units={["W", "kW"]} onChange={(q) => setForm({ ...form, pilot_power_sustained: q })} />
          <QuantityField label="目標巡航速度" field={form.target_cruise_speed} units={["m/s", "km/h", "knot"]} onChange={(q) => setForm({ ...form, target_cruise_speed: q })} />
          <QuantityField label="翼幅制限(※大会規則ではなくチーム独自の設計制約)" field={form.wingspan_limit} units={["m", "cm", "mm", "ft"]} onChange={(q) => setForm({ ...form, wingspan_limit: q })} />
          <QuantityField label="空気密度" field={form.air_density} units={["kg/m^3", "g/L"]} onChange={(q) => setForm({ ...form, air_density: q })} />
          <QuantityField label="風速条件の上限(参考: 大会規則の競技中断基準 5 m/s)" field={form.wind_speed_limit} units={["m/s", "km/h", "knot"]} onChange={(q) => setForm({ ...form, wind_speed_limit: q })} />
          <QuantityField label="飛行制限高度(参考: 大会規則 10 m)" field={form.flight_altitude_limit} units={["m", "ft"]} onChange={(q) => setForm({ ...form, flight_altitude_limit: q })} />
        </div>
        <label>
          パイロット年齢(任意・記録のみ。大会規則の適合判定はチーム自身で行ってください)
          <input type="number" min={10} max={100} value={form.pilot_age} onChange={(e) => setForm({ ...form, pilot_age: e.target.value })} />
        </label>
        <p className="note">
          係数(無次元)— 既定値は仮定(ASSUMPTIONS.md A-102〜A-107)。根拠なく変更しないこと。
        </p>
        <div className="grid2">
          <label>巡航揚力係数 CL_cruise<input type="number" step="any" value={form.cl_cruise} onChange={(e) => setForm({ ...form, cl_cruise: e.target.value })} /></label>
          <label>最大揚力係数 CL_max<input type="number" step="any" value={form.cl_max} onChange={(e) => setForm({ ...form, cl_max: e.target.value })} /></label>
          <label>有害抗力係数 CD0<input type="number" step="any" value={form.cd0} onChange={(e) => setForm({ ...form, cd0: e.target.value })} /></label>
          <label>オズワルド効率 e<input type="number" step="any" value={form.oswald_efficiency} onChange={(e) => setForm({ ...form, oswald_efficiency: e.target.value })} /></label>
          <label>プロペラ効率 η_prop<input type="number" step="any" value={form.propeller_efficiency} onChange={(e) => setForm({ ...form, propeller_efficiency: e.target.value })} /></label>
          <label>駆動系効率 η_drive<input type="number" step="any" value={form.drivetrain_efficiency} onChange={(e) => setForm({ ...form, drivetrain_efficiency: e.target.value })} /></label>
        </div>
        <button type="submit" disabled={busy}>要求仕様を保存</button>
      </form>

      {history.length > 1 && (
        <div className="card">
          <button type="button" onClick={() => setShowHistory(!showHistory)}>
            要求仕様の変更履歴({history.length}リビジョン){showHistory ? "を閉じる" : "を表示"}
          </button>
          {showHistory && (
            <table>
              <thead>
                <tr><th>rev</th><th>日時</th><th>前リビジョンからの変更点</th></tr>
              </thead>
              <tbody>
                {history.map((h, i) => {
                  const older = history[i + 1];
                  const changes = older ? specDiff(older.spec, h.spec) : null;
                  return (
                    <tr key={h.id}>
                      <td>{h.revision}</td>
                      <td>{new Date(h.created_at).toLocaleString("ja-JP")}</td>
                      <td>
                        {changes === null
                          ? "(初版)"
                          : changes.length === 0
                            ? "変更なし(再保存)"
                            : changes.map((c) => <div key={c}>{c}</div>)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      )}
    </>
  );
}
