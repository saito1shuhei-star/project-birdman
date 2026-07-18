"""PBMドメイン例外。

ValueErrorを併せて継承する例外は、Pydanticバリデータ内で送出すると
ValidationError(API境界では422)として扱われる。
"""


class PBMError(Exception):
    """PBMのすべてのドメイン例外の基底。"""


class UnitDimensionError(PBMError, ValueError):
    """物理量の次元が期待と一致しない。"""


class NonPhysicalValueError(PBMError, ValueError):
    """非物理的な値(負の質量、NaN、範囲外など)。"""


class CalculationError(PBMError):
    """計算結果が不正(NaN/inf等)。発生した場合は計算エンジンのバグ。"""


class InvalidTransitionError(PBMError):
    """許可されていない設計状態遷移。"""


class ApprovalRequiredError(PBMError):
    """承認済み(approved)でない設計に対する製造用データ生成の要求。"""


class MissingRequirementError(PBMError):
    """要求仕様が未入力の状態でのサイジング実行要求。"""


class NotFoundError(PBMError):
    """対象エンティティが存在しない。"""


class SolverUnavailableError(PBMError):
    """realモードでの解析実行が要求されたが、外部ソルバーが利用不可(未インストール/パス未設定)。

    モックへ黙って差し替えてはならない(CON-003)。呼び出し側が明示的にモックへ
    切り替えるか、外部ソフトを設定するまでエラーとする。
    """


class SolverNotImplementedError(PBMError):
    """realモードの実行経路が未実装。実解析を実行していないのに実行済みに見せない(CON-003)。"""
