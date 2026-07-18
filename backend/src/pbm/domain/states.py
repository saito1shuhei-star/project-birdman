"""設計ライフサイクル状態(DOMAIN_MODEL.md §3)。遷移規則は pbm.workflow.states。"""

from enum import StrEnum


class DesignState(StrEnum):
    draft = "draft"
    calculated = "calculated"
    analyzed = "analyzed"
    review_required = "review_required"
    approved = "approved"
    rejected = "rejected"
    superseded = "superseded"
