"""設計状態遷移の単体テスト(DOMAIN_MODEL.md §3, FR-003, FR-004)。"""

import pytest

from pbm.domain.errors import ApprovalRequiredError, InvalidTransitionError
from pbm.domain.states import DesignState
from pbm.workflow.states import (
    ALLOWED_TRANSITIONS,
    ensure_approved_for_manufacturing,
    validate_transition,
)


class TestAllowedTransitions:
    def test_normal_flow(self):
        validate_transition(DesignState.draft, DesignState.calculated)
        validate_transition(DesignState.calculated, DesignState.review_required)
        validate_transition(DesignState.review_required, DesignState.approved, actor="設計責任者")
        validate_transition(DesignState.approved, DesignState.superseded)

    def test_back_to_draft_on_change(self):
        for state in (DesignState.calculated, DesignState.analyzed, DesignState.review_required):
            validate_transition(state, DesignState.draft)

    def test_rejected_returns_to_draft(self):
        validate_transition(DesignState.review_required, DesignState.rejected, actor="設計責任者")
        validate_transition(DesignState.rejected, DesignState.draft)


class TestForbiddenTransitions:
    @pytest.mark.parametrize(
        ("src", "dst"),
        [
            (DesignState.draft, DesignState.approved),       # 承認の飛び級禁止
            (DesignState.draft, DesignState.review_required),
            (DesignState.calculated, DesignState.approved),
            (DesignState.approved, DesignState.draft),        # 承認後は破棄(superseded)のみ
            (DesignState.superseded, DesignState.draft),      # 終端状態
        ],
    )
    def test_forbidden(self, src, dst):
        with pytest.raises(InvalidTransitionError):
            validate_transition(src, dst, actor="誰か")

    def test_approval_requires_actor(self):
        with pytest.raises(InvalidTransitionError, match="actor"):
            validate_transition(DesignState.review_required, DesignState.approved)
        with pytest.raises(InvalidTransitionError, match="actor"):
            validate_transition(DesignState.review_required, DesignState.rejected, actor="  ")


class TestManufacturingGuard:
    def test_only_approved_allowed(self):
        ensure_approved_for_manufacturing(DesignState.approved)
        for state in DesignState:
            if state is DesignState.approved:
                continue
            with pytest.raises(ApprovalRequiredError):
                ensure_approved_for_manufacturing(state)

    def test_transition_table_covers_all_states(self):
        assert set(ALLOWED_TRANSITIONS) == set(DesignState)
