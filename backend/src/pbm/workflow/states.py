"""設計状態の遷移規則(DOMAIN_MODEL.md §3)。

- 許可されていない遷移は InvalidTransitionError
- approved / rejected への遷移は承認者名(actor)必須
- approved 以外からの製造用データ生成は ApprovalRequiredError(FR-004)
"""

from pbm.domain.errors import ApprovalRequiredError, InvalidTransitionError
from pbm.domain.states import DesignState

ALLOWED_TRANSITIONS: dict[DesignState, frozenset[DesignState]] = {
    DesignState.draft: frozenset({DesignState.calculated}),
    DesignState.calculated: frozenset(
        {DesignState.analyzed, DesignState.review_required, DesignState.draft}
    ),
    DesignState.analyzed: frozenset({DesignState.review_required, DesignState.draft}),
    DesignState.review_required: frozenset(
        {DesignState.approved, DesignState.rejected, DesignState.draft}
    ),
    DesignState.approved: frozenset({DesignState.superseded}),
    DesignState.rejected: frozenset({DesignState.draft}),
    DesignState.superseded: frozenset(),
}

# 人間の承認判断を伴う遷移。actor(判断者名)を必須とする(PROJECT_BRIEF §2)
ACTOR_REQUIRED_STATES = frozenset({DesignState.approved, DesignState.rejected})


def validate_transition(current: DesignState, to: DesignState, actor: str | None = None) -> None:
    """遷移の可否を検証する。不正ならInvalidTransitionError。"""
    if to not in ALLOWED_TRANSITIONS[current]:
        raise InvalidTransitionError(f"状態遷移 {current} → {to} は許可されていません")
    if to in ACTOR_REQUIRED_STATES and not (actor and actor.strip()):
        raise InvalidTransitionError(f"{to} への遷移には承認者名(actor)が必要です")


def ensure_approved_for_manufacturing(current: DesignState) -> None:
    """製造用データ生成の前提条件(FR-004)。"""
    if current is not DesignState.approved:
        raise ApprovalRequiredError(
            f"製造用データは承認済み(approved)の設計からのみ生成できます(現在: {current})"
        )
