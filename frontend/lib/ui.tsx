"use client";

// 工程ページ共通の小部品(表示のみ。物理計算はしない)

import { CalcWarning, SolverExecution } from "@/lib/api";

export const sig4 = (v: number) => Number(v.toPrecision(4)).toString();

export type QuantityForm = { value: string; unit: string };

export function QuantityField({
  label,
  field,
  units,
  onChange,
  required = true,
}: {
  label: string;
  field: QuantityForm;
  units: string[];
  onChange: (q: QuantityForm) => void;
  required?: boolean;
}) {
  return (
    <label>
      {label}
      <span style={{ display: "flex", gap: "0.4rem" }}>
        <input
          required={required}
          type="number"
          step="any"
          value={field.value}
          onChange={(e) => onChange({ ...field, value: e.target.value })}
        />
        <select
          value={field.unit}
          onChange={(e) => onChange({ ...field, unit: e.target.value })}
        >
          {units.map((u) => (
            <option key={u} value={u}>
              {u}
            </option>
          ))}
        </select>
      </span>
    </label>
  );
}

export function WarningList({ warnings }: { warnings: CalcWarning[] }) {
  if (warnings.length === 0) return null;
  return (
    <table>
      <tbody>
        {warnings.map((w) => (
          <tr key={w.code} className={`warn-${w.severity}`}>
            <td>{w.code}</td>
            <td>{w.severity}</td>
            <td>{w.message}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function ExecutionBadge({
  execution,
  mockNote,
}: {
  execution: SolverExecution;
  mockNote?: string;
}) {
  return (
    <p className="note">
      実行モード:{" "}
      <span className={`badge ${execution.execution_mode}`}>
        {execution.execution_mode}
      </span>{" "}
      {execution.execution_mode === "mock" && mockNote && <strong>{mockNote}</strong>}
      {" / "}ソルバー: {execution.solver_name} v{execution.solver_version}
    </p>
  );
}
