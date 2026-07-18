"""HTMLレポート生成(FR-030, FR-032)。計算はせず、保存済み結果を整形するのみ。"""

from __future__ import annotations

from jinja2 import Environment, PackageLoader, select_autoescape

from pbm.domain.entities import Project
from pbm.domain.results import SizingRunResult

_env = Environment(
    loader=PackageLoader("pbm.reports", "templates"),
    autoescape=select_autoescape(["html"]),
)

# 結果表示の並び順と日本語名(単位はQuantityが保持)
_QUANTITY_LABELS: list[tuple[str, str]] = [
    ("total_mass", "全備質量"),
    ("required_lift", "必要揚力(全備重量)"),
    ("dynamic_pressure", "動圧"),
    ("wing_area", "必要翼面積"),
    ("wing_loading", "翼面荷重"),
    ("aspect_ratio", "アスペクト比"),
    ("mean_chord", "平均翼弦"),
    ("stall_speed", "失速速度"),
    ("speed_to_stall_ratio", "速度余裕 V/V_stall"),
    ("induced_drag_coefficient", "誘導抗力係数 CDi"),
    ("parasite_drag_coefficient", "有害抗力係数 CD0"),
    ("drag_coefficient_total", "全機抗力係数 CD"),
    ("required_thrust", "必要推力"),
    ("lift_to_drag", "揚抗比 L/D"),
    ("aero_power", "空力所要動力"),
    ("required_pilot_power", "パイロット必要出力"),
    ("power_margin", "出力収支"),
    ("reynolds_number", "レイノルズ数"),
]


def _sig4(value: float) -> str:
    """有効4桁表示(品質要件: 有効桁の明示)。"""
    return format(value, ".4g")


def render_sizing_report(project: Project, run: SizingRunResult) -> str:
    template = _env.get_template("sizing_report.html.j2")
    results = [
        {"key": key, "label": label, "quantity": run.outputs.quantities[key]}
        for key, label in _QUANTITY_LABELS
        if key in run.outputs.quantities
    ]
    return template.render(
        project=project,
        run=run,
        results=results,
        sig4=_sig4,
        inputs=run.inputs_snapshot,
    )
