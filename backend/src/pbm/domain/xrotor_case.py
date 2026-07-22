"""XROTOR 7.55向けの構造化入力(ARBI/AERO/OPERフロー)。

Codex版PBM(commit 6a9e400, src/birdman/xrotor_input.py)からの移植。
- 単位付きの翼形状・運転点からXROTORコンソール入力スクリプトを生成する
- 生成はスクリプト整形のみで空力計算は行わない(実解析はXROTOR本体)
- 出典: MIT XROTOR 7.55 User Guide(ARBI任意形状入力・AERO/EDITの13係数)
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field, model_validator

from pbm.domain.quantities import (
    Quantity,
    ensure_angle,
    ensure_dimension,
    ensure_inverse_angle,
)

XROTOR_GENERATOR_VERSION = "pbm-xrotor-arbi-v1"
_SAFE_CASE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._-]{0,79}$")


class XrotorStation(BaseModel):
    """半径方向1ステーション(絶対寸法・単位付き)。"""

    radius: Quantity
    chord: Quantity
    blade_angle: Quantity  # 角度単位(deg等)

    @model_validator(mode="after")
    def _validate(self) -> XrotorStation:
        ensure_dimension(self.radius, "[length]", "radius")
        ensure_dimension(self.chord, "[length]", "chord")
        ensure_angle(self.blade_angle, "blade_angle")
        if self.chord.magnitude_si <= 0:
            raise ValueError("chord: 正の値が必要です")
        if self.radius.magnitude_si <= 0:
            raise ValueError("radius: 正の値が必要です")
        return self


class XrotorAirfoilModel(BaseModel):
    """XROTORのAERO/EDITメニューが要求する13係数+出典。"""

    zero_lift_angle: Quantity                 # 角度
    lift_curve_slope: Quantity                # 1/rad
    stall_lift_curve_slope: Quantity          # 1/rad
    maximum_lift_coefficient: float
    minimum_lift_coefficient: float
    stall_transition_width: float = Field(gt=0)
    moment_coefficient: float
    minimum_drag_coefficient: float = Field(ge=0)
    lift_coefficient_at_minimum_drag: float
    quadratic_drag_coefficient: float = Field(ge=0)
    reference_reynolds_number: float = Field(gt=0)
    reynolds_exponent: float
    critical_mach_number: float = Field(gt=0, le=1.5)
    source: str = Field(min_length=1, max_length=500)  # 係数の出典(必須)

    @model_validator(mode="after")
    def _validate(self) -> XrotorAirfoilModel:
        ensure_angle(self.zero_lift_angle, "zero_lift_angle")
        ensure_inverse_angle(self.lift_curve_slope, "lift_curve_slope")
        ensure_inverse_angle(self.stall_lift_curve_slope, "stall_lift_curve_slope")
        if not self.source.strip():
            raise ValueError("source: 翼型係数の出典は必須です")
        if self.lift_curve_slope.to("1/rad").value <= 0:
            raise ValueError("lift_curve_slope: 正の値が必要です")
        if self.maximum_lift_coefficient <= self.minimum_lift_coefficient:
            raise ValueError("maximum_lift_coefficientはminimumより大きい必要があります")
        return self


class XrotorCase(BaseModel):
    """XROTORの運転点+任意ブレード形状の完全な定義。"""

    case_name: str
    blade_count: int = Field(ge=1, le=8)
    flight_speed: Quantity
    tip_radius: Quantity
    hub_radius: Quantity
    rotational_speed: Quantity                # 回転数(rpm等: 1/[time])
    altitude: Quantity
    air_density: Quantity
    dynamic_viscosity: Quantity
    speed_of_sound: Quantity
    stations: list[XrotorStation] = Field(min_length=3, max_length=50)
    airfoil: XrotorAirfoilModel
    apply_prandtl_corrections: bool = True

    @model_validator(mode="after")
    def _validate(self) -> XrotorCase:
        if not _SAFE_CASE_NAME.fullmatch(self.case_name):
            raise ValueError(
                "case_name: ASCII英数字・空白・ドット・ハイフン・アンダースコアのみ"
                "(80文字以内)"
            )
        ensure_dimension(self.flight_speed, "[length] / [time]", "flight_speed")
        ensure_dimension(self.tip_radius, "[length]", "tip_radius")
        ensure_dimension(self.hub_radius, "[length]", "hub_radius")
        ensure_dimension(self.rotational_speed, "1 / [time]", "rotational_speed")
        ensure_dimension(self.altitude, "[length]", "altitude")
        ensure_dimension(self.air_density, "[mass] / [length] ** 3", "air_density")
        ensure_dimension(
            self.dynamic_viscosity, "[mass] / [length] / [time]", "dynamic_viscosity"
        )
        ensure_dimension(self.speed_of_sound, "[length] / [time]", "speed_of_sound")
        for name in ("flight_speed", "rotational_speed", "air_density",
                     "dynamic_viscosity", "speed_of_sound"):
            if getattr(self, name).magnitude_si <= 0:
                raise ValueError(f"{name}: 正の値が必要です")
        tip_m = self.tip_radius.to("m").value
        hub_m = self.hub_radius.to("m").value
        if hub_m <= 0 or tip_m <= hub_m:
            raise ValueError("tip_radiusは正のhub_radiusより大きい必要があります")
        altitude_m = self.altitude.to("m").value
        if not -1000 <= altitude_m <= 20000:
            raise ValueError("altitude: -1000〜20000 mの範囲が必要です")
        radii = [s.radius.to("m").value for s in self.stations]
        if any(right <= left for left, right in zip(radii, radii[1:], strict=False)):
            raise ValueError("stations: 半径は狭義単調増加が必要です")
        if abs(radii[0] - hub_m) > 1e-6:
            raise ValueError("最初のステーション半径はhub_radiusと一致する必要があります")
        if abs(radii[-1] - tip_m) > 1e-6:
            raise ValueError("最後のステーション半径はtip_radiusと一致する必要があります")
        return self

    def normalized_payload(self) -> dict:
        """SI値と生成スクリプトで用いる比率(トレーサビリティ用)。"""
        tip_m = self.tip_radius.to("m").value
        return {
            "case_name": self.case_name,
            "blade_count": self.blade_count,
            "flight_speed_mps": self.flight_speed.to("m/s").value,
            "tip_radius_m": tip_m,
            "hub_radius_m": self.hub_radius.to("m").value,
            "rotational_speed_rpm": self.rotational_speed.to("rpm").value,
            "altitude_m": self.altitude.to("m").value,
            "air_density_kg_per_m3": self.air_density.to("kg/m^3").value,
            "dynamic_viscosity_pa_s": self.dynamic_viscosity.to("Pa*s").value,
            "speed_of_sound_mps": self.speed_of_sound.to("m/s").value,
            "stations": [
                {
                    "radius_m": s.radius.to("m").value,
                    "radius_ratio": s.radius.to("m").value / tip_m,
                    "chord_m": s.chord.to("m").value,
                    "chord_ratio": s.chord.to("m").value / tip_m,
                    "blade_angle_deg": s.blade_angle.to("deg").value,
                }
                for s in self.stations
            ],
            "airfoil_source": self.airfoil.source.strip(),
            "apply_prandtl_corrections": self.apply_prandtl_corrections,
            "generator_version": XROTOR_GENERATOR_VERSION,
        }

    def generate_script(self) -> str:
        """XROTOR 7.55のARBI/AERO/OPER用コンソール入力(ASCII)を生成する。"""
        tip_m = self.tip_radius.to("m").value
        station_lines = [
            (
                f"{_number(s.radius.to('m').value / tip_m)} "
                f"{_number(s.chord.to('m').value / tip_m)} "
                f"{_number(s.blade_angle.to('deg').value)}"
            )
            for s in self.stations
        ]
        a = self.airfoil
        coefficient_values = [
            a.zero_lift_angle.to("deg").value,
            a.lift_curve_slope.to("1/rad").value,
            a.stall_lift_curve_slope.to("1/rad").value,
            a.maximum_lift_coefficient,
            a.minimum_lift_coefficient,
            a.stall_transition_width,
            a.moment_coefficient,
            a.minimum_drag_coefficient,
            a.lift_coefficient_at_minimum_drag,
            a.quadratic_drag_coefficient,
            a.reference_reynolds_number,
            a.reynolds_exponent,
            a.critical_mach_number,
        ]
        lines = [
            f"NAME {self.case_name}",
            f"ATMO {_number(self.altitude.to('km').value)}",
            f"VSOU {_number(self.speed_of_sound.to('m/s').value)}",
            f"DENS {_number(self.air_density.to('kg/m^3').value)}",
            f"VISC {_number(self.dynamic_viscosity.to('Pa*s').value)}",
            "ARBI",
            str(self.blade_count),
            _number(self.flight_speed.to("m/s").value),
            _number(tip_m),
            _number(self.hub_radius.to("m").value),
            str(len(self.stations)),
            *station_lines,
            "Y" if self.apply_prandtl_corrections else "N",
            ".AERO",
            "EDIT",
        ]
        for index, value in enumerate(coefficient_values, start=1):
            lines.extend((str(index), _number(float(value))))
        lines.extend(
            (
                "",
                "",
                ".OPER",
                f"RPM {_number(self.rotational_speed.to('rpm').value)}",
                "",
                "QUIT",
                "",
            )
        )
        return "\n".join(lines)


def _number(value: float) -> str:
    return format(value, ".12g")
