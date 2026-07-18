"""正規化JSONのSHA-256ハッシュ計算(FR-022, DATA_MODEL.md)。

サイジング実行・空力解析実行など、すべての計算/解析リクエストの再現性判定に共通利用する。
"""

from __future__ import annotations

import hashlib
import json

from pydantic import BaseModel


def compute_input_hash(model: BaseModel) -> str:
    """正規化(キーソート・区切り統一)した入力JSONのSHA-256 hexダイジェストを返す。"""
    canonical = json.dumps(
        model.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
