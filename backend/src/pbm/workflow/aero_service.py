"""空力解析(Step 5)のオーケストレーション。

平面形(Step 4)と要求仕様(Step 2)から解析リクエストを組み立て、
AerodynamicSolverAdapter(XFLR5等)を呼び出す。計算式はここに書かない。
"""

from __future__ import annotations

from pbm.adapters.base import ExecutionMode, SolverExecution
from pbm.adapters.xflr5 import XFLR5Adapter
from pbm.domain.aero_analysis import AeroAnalysisOutput, AeroAnalysisRequest
from pbm.domain.planform import WingPlanformInput
from pbm.domain.requirements import RequirementSpecInput


def build_aero_request(
    planform: WingPlanformInput, spec: RequirementSpecInput
) -> AeroAnalysisRequest:
    """平面形の幾何と要求仕様の係数から空力解析リクエストを組み立てる。

    - AR: 平面形から導出(台形積分)
    - e / CD0 / CL_max: 要求仕様の値(既定値はASSUMPTIONS A-103〜A-105)
    - 翼型名: 翼根セクションの値(モックでは未使用、実解析用に記録)
    """
    return AeroAnalysisRequest(
        airfoil_name=planform.sections[0].airfoil,
        aspect_ratio=planform.aspect_ratio,
        oswald_efficiency=spec.oswald_efficiency,
        parasite_drag_coefficient=spec.cd0,
        cl_max=spec.cl_max,
    )


def execute_aero_analysis(
    request: AeroAnalysisRequest,
    execution_mode: ExecutionMode = ExecutionMode.mock,
    adapter: XFLR5Adapter | None = None,
) -> tuple[AeroAnalysisOutput, SolverExecution]:
    """空力解析を実行する。既定はmock(XFLR5未接続でも動作)。"""
    solver = adapter if adapter is not None else XFLR5Adapter()
    return solver.run(request, execution_mode=execution_mode)
