"""BoundaryResponse — structured degradation when confidence is low.

When vector distance exceeds threshold, returns a structured response
indicating low confidence instead of potentially misleading results.
"""

from __future__ import annotations

from dataclasses import dataclass

from oprocess.config import get_config


@dataclass
class BoundaryResponse:
    """Structured response for low-confidence queries."""

    query: str
    best_score: float
    threshold: float
    suggestion: str
    is_within_boundary: bool

    def to_dict(self) -> dict:
        return {
            "boundary_triggered": not self.is_within_boundary,
            "query": self.query,
            "best_score": self.best_score,
            "threshold": self.threshold,
            "suggestion": self.suggestion,
            "is_within_boundary": self.is_within_boundary,
        }


def check_boundary(
    query: str,
    best_score: float,
    threshold: float | None = None,
) -> BoundaryResponse:
    """Check if query results are within confidence boundary."""
    if threshold is None:
        threshold = get_config()["boundary_threshold"]
    is_within = best_score >= threshold

    if is_within:
        suggestion = ""
    else:
        suggestion = (
            f"查询 '{query}' 的最佳匹配分数为 {best_score:.3f}，"
            f"低于置信阈值 {threshold}。"
            "建议：1) 尝试更具体的关键词 2) 使用英文搜索 "
            "3) 浏览流程树定位相关节点"
        )

    return BoundaryResponse(
        query=query,
        best_score=best_score,
        threshold=threshold,
        suggestion=suggestion,
        is_within_boundary=is_within,
    )
