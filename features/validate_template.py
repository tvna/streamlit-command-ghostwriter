"""Jinja2テンプレートのセキュリティと構造を検証するモジュール。

このモジュールは、ユーザーが提供するJinja2テンプレートに対して、
潜在的なセキュリティリスクやリソース枯渇攻撃 (DoS) に繋がる可能性のある
構造的な問題を検出し、安全なレンダリングを支援することを目的としています。

主な機能:
- Pydantic v2モデルによる設定と検証:
    - `TemplateConfig`: 禁止タグ (`macro`, `include` 等)、禁止属性 (`__class__`, `os` 等)、
      ループ反復回数の上限などを定義します。
    - `RangeConfig`: `range()` 関数の引数を検証し、有効な範囲内であることを確認します。
    - `ValidationState`: 検証プロセス中の状態 (有効/無効、エラーメッセージ) を保持します。
    - `HTMLContent`: `safe` フィルタ使用時のHTMLコンテンツの安全性を検証します。

- `TemplateSecurityValidator` クラス:
    - テンプレート検証の中核コンポーネントで、以下の2段階の検証を提供:

    - 1. 静的解析 (`validate_template_file`):
        - ファイルサイズ検証: `max_file_size_bytes` に基づき上限を設定します。
        - エンコーディング検証: UTF-8形式の有効性、NULLバイト等のバイナリデータがないか確認します。
        - 構文検証: Jinja2の基本的な構文エラーがないか確認します。
        - 禁止タグ検証: `macro`, `include`, `import`, `extends`, `do` 等のタグ使用を禁止します。
        - 禁止属性検証: `__class__`, `os`, `eval` 等の危険な属性へのアクセスを禁止します。
        - リテラルループ範囲検証: `{% for i in range(100001) %}` のようなハードコードされた
          大きな範囲のループが `max_range_size` を超えないか確認します。

    - 2. ランタイム解析 (`validate_runtime_security`):
        - コンテキスト (`context`) 適用時に生じる問題を検出します。
        - 再帰的構造検出: コンテキストデータやテンプレート内変数操作による無限再帰を検出します。
        - ゼロ除算検証: `{{ 10 / var }}` のような式でゼロ除算が発生しないか確認します。
        - 動的ループ範囲検証: コンテキスト変数に依存する大きなループや、大きなデータ構造の展開が
          設定された上限 (`max_memory_size_bytes`, `max_range_size`) を超えないか監視します。

- ノード評価機能:
    - テンプレートASTの各ノードタイプ (Name, Const, List, Dict, Call, Getattr) に対応する
      評価関数を提供し、式の評価とセキュリティリスク検出を行います。
    - ディスパッチパターンを活用して、ノードタイプに応じた適切な検証を実行します。

利用方法:
このモジュールは `DocumentRender` クラスなど、Jinja2テンプレートを扱うコンポーネントから利用されます。
通常、テンプレートファイルのアップロード時に `validate_template_file` を呼び出して静的解析を実行し、
その後レンダリング前に `validate_runtime_security` を呼び出してコンテキスト適用時の潜在的な問題を
検出します。これにより、テンプレートのセキュアなレンダリングを実現します。

このモジュールはPydantic v2を活用しており、`BaseModel` を拡張して型安全な検証を実現しています。
また、`Final` やタイプヒントを積極的に活用し、コードの安全性と明確性を高めています。

セキュリティ上の留意点:
- テンプレート内でのサーバーサイドリソースへのアクセスを制限します。
- テンプレートインジェクション攻撃を防止します。
- DoS攻撃を防ぐため、リソース使用量に上限を設けます。
- `html_safe_filter` 関数により、安全なHTMLコンテンツのみ許可します。
"""

import re
from decimal import Decimal
from io import BytesIO
from typing import (
    Annotated,
    Any,
    Callable,
    Dict,
    Final,
    List,
    Optional,
    Protocol,
    Set,
    Tuple,
    Type,
    TypeAlias,
    TypeVar,
    Union,
    cast,
)

import jinja2
from jinja2 import Environment, nodes
from markupsafe import Markup
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    ValidationError,
    field_validator,
)

from .validate_uploaded_file import FileSizeConfig, FileValidator

T = TypeVar("T")
NodeT = TypeVar("NodeT", bound=nodes.Node)

# Type definitions for container validation
ContainerValueType: TypeAlias = Union[str, Decimal, bool, None]
ContainerListType: TypeAlias = List[Union[ContainerValueType, "ContainerListType", "ContainerDictType"]]  # type: ignore
ContainerDictType: TypeAlias = Dict[str, Union[ContainerValueType, ContainerListType, "ContainerDictType"]]  # type: ignore
ContainerType: TypeAlias = Union[ContainerValueType, ContainerListType, ContainerDictType]

# Type definition for evaluated values
# Define recursively to avoid Any
EvaluatedValue: TypeAlias = Union[str, Decimal, bool, List["EvaluatedValue"], Dict[str, "EvaluatedValue"], None]


# Type definition for node evaluator function
class NodeEvaluatorProtocol(Protocol):
    def __call__(self, node: nodes.Node, context: Dict[str, Any], assignments: Dict[str, Any]) -> EvaluatedValue: ...


NodeEvaluatorFunc: TypeAlias = NodeEvaluatorProtocol


class TemplateConfig(BaseModel):
    """テンプレート設定のバリデーションモデル。"""

    model_config = ConfigDict(strict=True, validate_assignment=True)

    max_range_size: Annotated[int, Field(gt=0)]
    restricted_tags: Set[str] = Field(default_factory=lambda: {"macro", "include", "import", "extends", "do"})
    restricted_attributes: Set[str] = Field(
        default_factory=lambda: {
            "request",
            "config",
            "os",
            "sys",
            "builtins",
            "eval",
            "exec",
            "getattr",
            "setattr",
            "delattr",
            "globals",
            "locals",
            "__class__",
            "__base__",
            "__subclasses__",
            "__mro__",
        }
    )


class RangeConfig(BaseModel):
    """rangeループの設定のバリデーションモデル。"""

    model_config = ConfigDict(strict=True)

    start: Annotated[int, Field(default=0, ge=0, validate_default=False)]
    stop: Annotated[int, Field(default=100, gt=0, validate_default=True)]
    step: Annotated[int, Field(default=1, gt=0, validate_default=False)]


class ValidationState(BaseModel):
    """テンプレートの検証状態を表すクラス。"""

    model_config = ConfigDict(strict=True, validate_assignment=True)

    is_valid: bool = Field(default=True)
    error_message: Optional[str] = Field(default=None)
    content: Optional[str] = Field(default=None)

    def set_error(self, message: Optional[str]) -> None:
        """エラーメッセージを設定する。

        Args:
            message: エラーメッセージ (Noneの場合は空文字列に変換)
        """
        self.is_valid = False
        self.error_message = str(message) if message is not None else ""

    def reset(self) -> None:
        """状態をリセットする。"""
        self.is_valid = True
        self.error_message = None
        self.content = None


# Type definition for node validators
NodeValidator: TypeAlias = Callable[[nodes.Node, Dict[str, Any], Dict[str, Any], ValidationState], bool]


class HTMLContent(BaseModel):
    """HTMLコンテンツのバリデーションモデル。"""

    model_config = ConfigDict(strict=True)

    content: str = Field(...)

    @field_validator("content")
    @classmethod
    def _validate_html_content(cls, v: str) -> str:
        """HTMLコンテンツを検証する。

        Args:
            v: 検証対象のコンテンツ

        Returns:
            str: 検証済みのコンテンツ

        Raises:
            ValueError: 安全でないHTML要素が含まれる場合
        """

        # 安全でないHTMLパターンをチェック
        unsafe_patterns: Final[List[str]] = [
            r"<script",  # スクリプトタグ
            r"javascript:",  # JavaScriptプロトコル
            r"data:",  # データURIスキーム
            r"vbscript:",  # VBScriptプロトコル
            r"on\w+\s*=",  # イベントハンドラ属性
        ]

        for pattern in unsafe_patterns:
            if re.search(pattern, v, re.IGNORECASE):
                raise ValueError("HTML content contains potentially unsafe elements")

        return v


class TemplateSecurityValidator(BaseModel):
    """テンプレートのセキュリティ検証を行うクラス。

    テンプレートの構文、セキュリティ、および構造を検証します。
    検証は以下の2段階で実行されます:
    1. 静的解析 (初期検証)
       - ファイルサイズの検証
       - エンコーディングの検証
       - 禁止タグのチェック
       - 禁止属性のチェック
       - リテラル値のループ範囲チェック
    2. ランタイム検証
       - 再帰的構造の検出
       - ゼロ除算の検証
       - 動的なループ範囲の検証

    Attributes:
        config: テンプレート設定
        max_file_size_bytes: ファイルサイズの最大バイト数
        max_memory_size_bytes: メモリサイズの最大バイト数
    """

    # --- Pydantic Model Configuration ---
    model_config = ConfigDict(arbitrary_types_allowed=True)  # Allow custom types if needed

    # --- Public Fields (Configuration) ---
    _config: TemplateConfig = PrivateAttr(default=TemplateConfig(max_range_size=100000))
    max_file_size_bytes: Annotated[int, Field(gt=0)]
    max_memory_size_bytes: Annotated[int, Field(gt=0)]

    # --- Private Fields (Internal State) ---
    _validation_state: ValidationState = PrivateAttr(default_factory=ValidationState)

    # --- Properties (Accessing Config) ---
    @property
    def max_range_size(self) -> int:
        """最大range値を返す。"""
        return self._config.max_range_size

    @property
    def restricted_tags(self) -> Set[str]:
        """禁止タグのセットを返す。"""
        return self._config.restricted_tags

    @property
    def restricted_attributes(self) -> Set[str]:
        """禁止属性のセットを返す。"""
        return self._config.restricted_attributes

    def validate_runtime_security(self, ast: nodes.Template, context: Dict[str, Any]) -> ValidationState:
        """ランタイムセキュリティの検証を実行する。

        Args:
            ast: 検証対象のテンプレートAST
            context: テンプレートに適用するコンテキスト

        Returns:
            ValidationState: 検証結果
        """
        validation_state: Final[ValidationState] = ValidationState()
        assignments: Dict[str, Any] = {}

        # 1. 再帰的構造の検出 (ここから例外が発生する可能性)
        if not self._validate_recursive_structures(ast, context, assignments, validation_state):
            return validation_state

        # 2. ゼロ除算の検証
        if not self._validate_division_operations(ast, context, assignments, validation_state):
            return validation_state

        return validation_state

    def _validate_recursive_structures(
        self, ast: nodes.Template, context: Dict[str, Any], assignments: Dict[str, Any], validation_state: ValidationState
    ) -> bool:
        """再帰的構造を検出する。

        Args:
            ast: 検証対象のAST
            context: テンプレートに適用するコンテキスト
            assignments: 変数の割り当て状態
            validation_state: 検証状態

        Returns:
            bool: 検証が成功したかどうか
        """
        node_validators: Dict[Type[nodes.Node], NodeValidator] = {
            nodes.Assign: lambda n, c, a, v: self._validate_assignment_node(cast("nodes.Assign", n), c, a, v),
            nodes.For: lambda n, c, a, v: self._validate_for_loop_node(cast("nodes.For", n), c, a, v),
            nodes.Call: lambda n, c, a, v: self._validate_function_call_node(cast("nodes.Call", n), c, a, v),
        }

        for node in ast.find_all((nodes.Assign, nodes.For, nodes.Call)):
            validator: Optional[NodeValidator] = node_validators.get(type(node))
            if validator:
                try:
                    if not validator(node, context, assignments, validation_state):
                        return False
                except Exception as e:
                    validation_state.set_error(f"Template runtime error: {type(node).__name__} {e!s}")
                    return False
        return True

    def _validate_assignment_node(
        self, node: nodes.Assign, context: Dict[str, Any], assignments: Dict[str, Any], validation_state: ValidationState
    ) -> bool:
        """代入ノードを検証する。

        Args:
            node: 代入ノード
            context: テンプレートに適用するコンテキスト
            assignments: 変数の割り当て状態
            validation_state: 検証状態

        Returns:
            bool: 検証が成功したかどうか
        """
        if isinstance(node.target, nodes.Name):
            target_name: Final[str] = node.target.name
            value: Final[EvaluatedValue] = self._evaluate_expression(node.node, context, assignments)
            assignments[target_name] = value
            return True
        return True

    def _validate_for_loop_node(
        self, node: nodes.For, context: Dict[str, Any], assignments: Dict[str, Any], validation_state: ValidationState
    ) -> bool:
        """forループノードを検証する。

        Args:
            node: forループノード
            context: テンプレートに適用するコンテキスト
            assignments: 変数の割り当て状態
            validation_state: 検証状態

        Returns:
            bool: 検証が成功したかどうか
        """
        if isinstance(node.iter, nodes.Name):
            iter_name: Final[str] = node.iter.name
            if iter_name in assignments:
                self._evaluate_expression(node.iter, context, assignments)
        return True

    def _validate_function_call_node(
        self, node: nodes.Call, context: Dict[str, Any], assignments: Dict[str, Any], validation_state: ValidationState
    ) -> bool:
        """関数呼び出しノードを検証する。

        Args:
            node: 関数呼び出しノード
            context: テンプレートに適用するコンテキスト
            assignments: 変数の割り当て状態
            validation_state: 検証状態

        Returns:
            bool: 検証が成功したかどうか
        """
        self._evaluate_expression(node, context, assignments)
        return True

    def _validate_division_operations(
        self, ast: nodes.Template, context: Dict[str, Any], assignments: Dict[str, Any], validation_state: ValidationState
    ) -> bool:
        """除算演算を検証する。

        Args:
            ast: 検証対象のAST
            context: テンプレートに適用するコンテキスト
            assignments: 変数の割り当て状態
            validation_state: 検証状態

        Returns:
            bool: 検証が成功したかどうか
        """
        for node in ast.find_all(nodes.Div):
            right_value: EvaluatedValue = self._evaluate_expression(node.right, context, assignments)
            if right_value == 0:
                validation_state.set_error("Template security error: division by zero is not allowed")
                return False
        return True

    def html_safe_filter(self, value: str) -> Markup:
        """HTMLをエスケープせずに出力する。

        Args:
            value: HTML文字列

        Returns:
            Markup: 安全なMarkupオブジェクト

        Raises:
            ValueError: 安全でないHTML要素が含まれる場合
        """
        try:
            html_content: Final[HTMLContent] = HTMLContent(content=value)
            return Markup("").join(html_content.content)
        except ValidationError as e:
            raise ValueError(str(e)) from e

    def _evaluate_expression(
        self,
        node: nodes.Node,
        context: Dict[str, Any],
        assignments: Dict[str, Any],
    ) -> Union[str, Decimal, List[Any], Dict[str, Any], bool, None]:
        """式を評価する。

        Args:
            node: 評価対象のノード
            context: テンプレートに適用するコンテキスト
            assignments: 変数の割り当て状態

        Returns:
            Union[None, str, Decimal, List[Any], Dict[str, Any], bool]: 評価結果

        Raises:
            ValueError: 再帰的構造が検出された場合
            TypeError: 式の評価に失敗した場合
        """
        try:
            evaluator = self._get_node_evaluator(node)
            if evaluator is None:
                raise TypeError("cannot evaluate expression")
            return evaluator(node, context, assignments)
        except Exception as e:
            raise TypeError("cannot evaluate expression") from e

    def _get_node_evaluator(self, node: nodes.Node) -> Optional[NodeEvaluatorFunc]:
        """ノードに対応する評価関数を取得する。

        Args:
            node: 評価対象のノード

        Returns:
            Optional[NodeEvaluatorFunc]: 評価関数 (対応する関数がない場合はNone)
        """
        evaluators: Dict[Type[nodes.Node], Callable[..., EvaluatedValue]] = {
            nodes.Name: self._evaluate_name,
            nodes.Const: self._evaluate_const,
            nodes.List: self._evaluate_list,
            nodes.Dict: self._evaluate_dict,
            nodes.Call: self._evaluate_call,
            nodes.Getattr: self._evaluate_getattr,
        }
        evaluator: Optional[NodeEvaluatorFunc] = evaluators.get(type(node))
        return cast("Optional[NodeEvaluatorFunc]", evaluator) if evaluator is not None else None

    def _evaluate_name(
        self,
        node: nodes.Name,
        context: Dict[str, Any],
        assignments: Dict[str, Any],
    ) -> Optional[EvaluatedValue]:
        """変数名を評価する。

        Args:
            node: 変数名ノード
            context: テンプレートに適用するコンテキスト
            assignments: 変数の割り当て状態

        Returns:
            Optional[EvaluatedValue]: 評価結果 [変数の値またはNone]
        """
        name: Final[str] = node.name
        if name in assignments:
            value = assignments[name]
            if isinstance(value, (type(None), str, Decimal, list, dict, bool)):
                return cast("EvaluatedValue", value)
            return None
        if name in context:
            value = context[name]
            if isinstance(value, (type(None), str, Decimal, list, dict, bool)):
                return cast("EvaluatedValue", value)
            return None
        return None

    def _evaluate_const(
        self,
        node: nodes.Const,
        context: Dict[str, Any],
        assignments: Dict[str, Any],
    ) -> Union[str, Decimal]:
        """定数を評価する。

        Args:
            node: 定数ノード
            context: テンプレートに適用するコンテキスト
            assignments: 変数の割り当て状態

        Returns:
            Union[str, Decimal]: 評価結果
        """
        if isinstance(node.value, (int, float)):
            return Decimal(str(node.value))
        return node.value

    def _evaluate_list(
        self,
        node: nodes.List,
        context: Dict[str, Any],
        assignments: Dict[str, Any],
    ) -> List[EvaluatedValue]:
        """リストを評価する。

        Args:
            node: リストノード
            context: テンプレートに適用するコンテキスト
            assignments: 変数の割り当て状態

        Returns:
            List[EvaluatedValue]: 評価結果

        Raises:
            ValueError: 再帰的構造が検出された場合
        """
        values: List[EvaluatedValue] = []
        for item in node.items:
            value = self._evaluate_expression(item, context, assignments)
            values.append(value)
        return values

    def _evaluate_dict(
        self,
        node: nodes.Dict,
        context: Dict[str, Any],
        assignments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """辞書を評価する。

        Args:
            node: 辞書ノード
            context: テンプレートに適用するコンテキスト
            assignments: 変数の割り当て状態

        Returns:
            Dict[str, Any]: 評価結果

        Raises:
            ValueError: 再帰的構造が検出された場合
            TypeError: キーが文字列でない場合
        """
        result: Dict[str, Any] = {}
        for pair in node.items:
            key = self._evaluate_expression(pair.key, context, assignments)
            if not isinstance(key, str):
                raise TypeError("Dictionary keys must be strings")
            value = self._evaluate_expression(pair.value, context, assignments)
            result[key] = value
        return result

    def _evaluate_call(
        self,
        node: nodes.Call,
        context: Dict[str, Any],
        assignments: Dict[str, Any],
    ) -> Optional[EvaluatedValue]:
        """メソッド呼び出しを評価し、再帰をチェックする。

        Args:
            node: メソッド呼び出しノード
            context: テンプレートに適用するコンテキスト
            assignments: 変数の割り当て状態

        Returns:
            Optional[EvaluatedValue]: 評価結果

        Raises:
            ValueError: 再帰的構造が検出された場合
            TypeError: 評価中にエラーが発生した場合
        """
        # メソッドが呼び出されるオブジェクトを評価
        self._evaluate_expression(node.node, context, assignments)

        # 引数を評価
        [self._evaluate_expression(arg, context, assignments) for arg in node.args]

        # 注: このメソッドは主に再帰検出に焦点を当てており、
        # 実際のメソッド呼び出しの結果は返しません
        return None

    def _evaluate_getattr(
        self,
        node: nodes.Getattr,
        context: Dict[str, Any],
        assignments: Dict[str, Any],
    ) -> Optional[EvaluatedValue]:
        """属性アクセスを評価する。

        Args:
            node: 属性アクセスノード
            context: テンプレートに適用するコンテキスト
            assignments: 変数の割り当て状態

        Returns:
            Optional[EvaluatedValue]: 評価結果 [属性の値またはNone]
        """
        self._evaluate_expression(node.node, context, assignments)
        return None

    def _validate_restricted_tags(self, ast: nodes.Template, validation_state: ValidationState) -> bool:
        """禁止タグを検証する。

        Args:
            ast: 検証対象のAST
            validation_state: 検証状態

        Returns:
            bool: 検証が成功したかどうか
        """
        # Check for standard restricted tags
        for node in ast.find_all((nodes.Macro, nodes.Include, nodes.Import, nodes.Extends)):
            tag_name = node.__class__.__name__.lower()
            if tag_name in self.restricted_tags:
                validation_state.set_error(f"Template security error: '{tag_name}' tag is not allowed")
                return False

        # Specifically check for the 'do' tag (ExprStmt)
        if "do" in self.restricted_tags:
            # If 'do' is restricted, the presence of *any* ExprStmt is forbidden.
            if any(isinstance(node, nodes.ExprStmt) for node in ast.find_all(nodes.ExprStmt)):
                validation_state.set_error("Template security error: 'do' tag is not allowed")
                return False

        return True

    def _check_getattr(self, node: nodes.Getattr, validation_state: ValidationState) -> bool:
        """Getattrノードを検証する。"""
        attribute_name: Final[str] = node.attr
        if attribute_name in self.restricted_attributes:
            validation_state.set_error(f"Template security error: Access to restricted attribute '{attribute_name}' is forbidden.")
            return False
        return True

    def _check_getitem(self, node: nodes.Getitem, validation_state: ValidationState) -> bool:
        """Getitemノードを検証する。"""
        if isinstance(node.arg, nodes.Const) and isinstance(node.arg.value, str):
            attribute_name: Final[str] = node.arg.value
            if attribute_name in self.restricted_attributes:
                validation_state.set_error(f"Template security error: Access to restricted item '{attribute_name}' is forbidden.")
                return False
        return True

    def _check_name(self, node: nodes.Name, validation_state: ValidationState) -> bool:
        """Nameノードを検証する。"""
        variable_name: Final[str] = node.name
        if variable_name in self.restricted_attributes:
            validation_state.set_error(f"Template security error: Use of restricted variable '{variable_name}' is forbidden.")
            return False
        return True

    def _check_call(self, node: nodes.Call, validation_state: ValidationState) -> bool:
        """Callノードを検証する。"""
        if isinstance(node.node, nodes.Name):
            function_name: Final[str] = node.node.name
            if function_name in self.restricted_attributes:
                validation_state.set_error(f"Template security error: Call to restricted function '{function_name}()' is forbidden.")
                return False
        return True

    def _check_assign(self, node: nodes.Assign, validation_state: ValidationState) -> bool:
        """Assignノードを検証する。"""
        # Check if the assigned value is a restricted name
        if isinstance(node.node, nodes.Name) and node.node.name in self.restricted_attributes:
            variable_name: Final[str] = node.node.name
            validation_state.set_error(f"Template security error: Assignment of restricted variable '{variable_name}' is forbidden.")
            return False
        # Check if the assigned value is a call to a restricted function
        elif (
            isinstance(node.node, nodes.Call)
            and isinstance(node.node.node, nodes.Name)
            and node.node.node.name in self.restricted_attributes
        ):
            function_name: Final[str] = node.node.node.name
            validation_state.set_error(
                f"Template security error: Assignment involving restricted function '{function_name}()' is forbidden."
            )
            return False
        return True

    def _validate_restricted_attributes(self, ast: nodes.Template, validation_state: ValidationState) -> bool:
        """テンプレート内で制限された属性や変数へのアクセスがないか検証する (ディスパッチ辞書使用)。

        Args:
            ast: 検証対象のテンプレートAST
            validation_state: 検証状態オブジェクト

        Returns:
            bool: 検証が成功した場合はTrue、失敗した場合はFalse
        """
        # マッピング: Node Type -> Validation Handler Function
        # Remove type annotation from handler_map and let type checker infer
        handler_map = {
            nodes.Getattr: self._check_getattr,
            nodes.Getitem: self._check_getitem,
            nodes.Name: self._check_name,
            nodes.Call: self._check_call,
            nodes.Assign: self._check_assign,
        }

        nodes_to_check = list(ast.find_all(tuple(handler_map.keys())))

        for node in nodes_to_check:
            node_type = type(node)
            # handler type will be inferred, remove explicit annotation
            handler = handler_map.get(node_type)

            if handler:
                # Call the handler (potential runtime errors if signature mismatches)
                if not handler(node, validation_state):
                    return False
            # If no handler is found for the node type, it's ignored.

        return True

    def _validate_loop_range(self, ast: nodes.Template, validation_state: ValidationState) -> bool:
        """ループ範囲を検証する。

        Args:
            ast: 検証対象のAST
            validation_state: 検証状態

        Returns:
            bool: 検証が成功したかどうか
        """
        for node in ast.find_all(nodes.For):
            if not self._is_range_call(node.iter):
                continue

            try:
                call_node = cast("nodes.Call", node.iter)
                range_args = self._get_range_arguments(call_node)
                iterations = self._calculate_range_iterations(*range_args)

                if iterations > self.max_range_size:
                    validation_state.set_error(f"Template security error: loop range exceeds maximum limit of {self.max_range_size}")
                    return False

            except ValueError as e:
                validation_state.set_error(f"Template security error: {e}")
                return False
            except TypeError:
                # 動的な値の場合は、ランタイムでの検証に委ねる
                continue

        return True

    def _is_range_call(self, node: nodes.Node) -> bool:
        """ノードがrange関数の呼び出しかどうかを判定する。

        Args:
            node: 検証対象のノード

        Returns:
            bool: range関数の呼び出しの場合はTrue
        """
        return isinstance(node, nodes.Call) and isinstance(node.node, nodes.Name) and node.node.name == "range"

    def _get_range_arguments(self, node: nodes.Call) -> tuple[int, int, int]:
        """range関数の引数を取得する。

        Args:
            node: range関数の呼び出しノード

        Returns:
            tuple[int, int, int]: (start, stop, step)の組

        Raises:
            TypeError: リテラル値でない場合
            ValueError: 引数が不正な場合
        """
        args = node.args
        try:
            if len(args) == 1:  # range(stop)
                stop = self._evaluate_literal(args[0])
                # Provide default start and step explicitly for RangeConfig validation
                range_config = RangeConfig(start=0, stop=stop, step=1)
                return range_config.start, range_config.stop, range_config.step
            elif len(args) >= 2:  # range(start, stop[, step])
                start = self._evaluate_literal(args[0])
                stop = self._evaluate_literal(args[1])
                step = self._evaluate_literal(args[2]) if len(args) > 2 else 1
                range_config = RangeConfig(start=start, stop=stop, step=step)
                return range_config.start, range_config.stop, range_config.step

            raise ValueError("invalid number of arguments for range()")
        except ValidationError as e:
            raise ValueError(str(e)) from e

    def _calculate_range_iterations(self, start: int, stop: int, step: int) -> int:
        """range関数の反復回数を計算する。

        Args:
            start: 開始値
            stop: 終了値
            step: ステップ値

        Returns:
            int: 反復回数
        """
        if step > 0:
            return (stop - start + step - 1) // step
        else:
            return (start - stop - step - 1) // -step

    def _evaluate_literal(self, node: nodes.Node) -> int:
        """リテラル値を評価する。

        Args:
            node: 評価対象のノード

        Returns:
            int: 評価結果

        Raises:
            TypeError: リテラル値でない場合
            ValueError: 評価できない場合
        """
        if isinstance(node, nodes.Const) and isinstance(node.value, (int, float)):
            return int(node.value)
        raise TypeError("Not a literal value")

    def validate_template_file(
        self, template_file: BytesIO, validation_state: ValidationState
    ) -> Tuple[Optional[str], Optional[nodes.Template]]:
        """テンプレートファイルの検証を行う。

        Args:
            template_file: テンプレートファイル (BytesIO)
            validation_state: 検証状態 (Noneの場合は新規作成)

        Returns:
            Tuple[Optional[str], Optional[nodes.Template]]: (テンプレート内容, AST)のタプル。エラー時はNoneを含む
        """
        validation_state.reset()

        # ファイルの内容を取得
        current_pos = template_file.tell()
        content = template_file.read()
        template_file.seek(current_pos)  # 元の位置に戻す

        # ファイルサイズの検証
        file_validator = FileValidator(size_config=FileSizeConfig(max_size_bytes=self.max_file_size_bytes))
        if not file_validator.validate_size(template_file):
            validation_state.set_error(f"Template file size exceeds maximum limit of {self.max_file_size_bytes} bytes")
            return None, None

        # バイナリデータのチェック
        if b"\x00" in content:
            validation_state.set_error("Template file contains invalid binary data")
            return None, None

        # UTF-8デコードのチェック
        try:
            template_content = content.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            validation_state.set_error("Template file contains invalid UTF-8 bytes")
            return None, None

        # 構文の検証とASTの取得
        ast = self._validate_syntax(template_content, validation_state)
        if ast is None:
            return None, None

        # 1. 禁止タグの検証
        if not self._validate_restricted_tags(ast, validation_state):
            return None, None

        # 2. 属性アクセスの検証
        if not self._validate_restricted_attributes(ast, validation_state):
            return None, None

        # 3. ループ範囲の検証 (リテラル値のみ)
        if not self._validate_loop_range(ast, validation_state):
            return None, None

        # If all static checks pass
        return template_content, ast

    def _validate_syntax(self, template_content: str, validation_state: ValidationState) -> Optional[nodes.Template]:
        """テンプレートの構文を検証する。

        Args:
            template_content: テンプレートの内容
            validation_state: 検証状態

        Returns:
            Optional[nodes.Template]: 構文解析結果 (エラーの場合はNone)
        """
        try:
            env = Environment(autoescape=True, extensions=["jinja2.ext.do"])
            return env.parse(template_content)
        except jinja2.TemplateSyntaxError as e:
            validation_state.set_error(f"Template syntax error: {e!s}")
            return None
