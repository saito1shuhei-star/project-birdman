"""単位付き物理量 Quantity(NFR-001)。

- 物理量は必ず値+単位で保持する。内部標準はSI
- 単位の解釈・変換・次元検証はPintに委譲する
- NaN/±infはモデル構築時に拒否する
"""

from __future__ import annotations

import math

import pint
from pydantic import BaseModel, field_validator

from pbm.domain.errors import UnitDimensionError

_UREG = pint.UnitRegistry()


def unit_registry() -> pint.UnitRegistry:
    """PBM共通のPintレジストリ(プロセス内で単一)。"""
    return _UREG


class Quantity(BaseModel):
    """値と単位を一体で保持する物理量。

    unit はPintが解釈できる文字列("kg", "m/s", "kg/m^3", "dimensionless" 等)。
    """

    value: float
    unit: str

    model_config = {"frozen": True}

    @field_validator("value")
    @classmethod
    def _reject_non_finite(cls, v: float) -> float:
        if not math.isfinite(v):
            raise ValueError("物理量にNaN・無限大は使用できません")
        return v

    @field_validator("unit")
    @classmethod
    def _reject_unknown_unit(cls, u: str) -> str:
        try:
            _UREG.Unit(u)
        except Exception as exc:  # pint は複数種の例外を送出する
            raise ValueError(f"解釈できない単位です: {u!r}") from exc
        return u

    def _pint(self) -> pint.Quantity:
        return _UREG.Quantity(self.value, self.unit)

    @property
    def dimensionality(self) -> str:
        """次元の文字列表現(例 '[mass]')。"""
        return str(self._pint().dimensionality)

    def to(self, unit: str) -> Quantity:
        """指定単位へ変換した新しいQuantityを返す。次元不一致はUnitDimensionError。"""
        try:
            converted = self._pint().to(unit)
        except pint.DimensionalityError as exc:
            raise UnitDimensionError(str(exc)) from exc
        return Quantity(value=float(converted.magnitude), unit=unit)

    def si(self) -> Quantity:
        """SI基本単位へ正規化した新しいQuantityを返す。"""
        base = self._pint().to_base_units()
        return Quantity(value=float(base.magnitude), unit=str(base.units))

    @property
    def magnitude_si(self) -> float:
        """SI基本単位系での数値。計算エンジンへの受け渡しに使用する。"""
        return float(self._pint().to_base_units().magnitude)

    def __str__(self) -> str:
        return f"{self.value:g} {self.unit}"


def ensure_dimension(q: Quantity, expected: str, field_name: str = "") -> None:
    """qの次元がexpected(例 '[mass]', '[length] / [time]')と一致することを検証する。"""
    expected_dim = _UREG.get_dimensionality(expected)
    actual_dim = _UREG.Unit(q.unit).dimensionality
    if actual_dim != expected_dim:
        label = f"{field_name}: " if field_name else ""
        raise UnitDimensionError(
            f"{label}次元が不正です。期待 {expected}({expected_dim})、"
            f"実際 {q.unit!r}({actual_dim})"
        )
