"""テンプレートの検証と関連するPydanticモデルを提供するモジュール。

主な機能:
- テンプレート設定、検証状態などのPydanticモデル定義
- TemplateSecurityValidator: Jinja2テンプレートのセキュリティ検証
  - ファイルサイズ、構文、エンコーディング、禁止タグ・属性、ループ範囲などの静的検証
  - 再帰構造、ゼロ除算、動的ループ範囲などのランタイム検証 (コンテキスト適用後)

ファイルサイズ上限は `TemplateSecurityValidator` の初期化時に指定可能です。
通常、このモジュールのクラスは `DocumentRender` から利用されます。
"""

import decimal
import logging
import re
from decimal import Decimal
from io import BytesIO
from typing import (
    Annotated,
    Any,
    Callable,
    Dict,
    Iterator,
    List,
    Optional,
    Protocol,
    Sequence,
    Set,
    Tuple,
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
    ValidationError,
    field_validator,
)

# Re-add the import for FileValidator and FileSizeConfig

T = TypeVar("T")
RecursiveT = TypeVar("RecursiveT", bound="RecursiveValue")
NodeType = TypeVar("NodeType", bound=nodes.Node)
NodeEvaluator = Callable[[NodeType, Dict[str, Any], Dict[str, Any]], Any]

# 評価可能な値の型を定義
EvaluatedValue = Union[str, Decimal, List[Any], Dict[str, Any], bool, None]


class RecursiveValue(Protocol):
    """再帰的な構造を持つ値の型プロトコル。

    このプロトコルは、再帰的な構造 (リスト、辞書、セットなど)を持つ値の型を定義します。
    再帰的な構造は、自身の要素として同じ型の値を含むことができます。
    """

    def __iter__(self) -> Iterator[RecursiveT]: ...  # type: ignore


class TemplateConfig(BaseModel):
    """テンプレート設定のバリデーションモデル。"""

    model_config = ConfigDict(strict=True, validate_assignment=True)

    max_file_size: Annotated[int, Field(gt=0)] = Field(default=1024 * 1024)  # 1MB
    max_memory_size: Annotated[int, Field(gt=0)] = Field(default=1024 * 1024 * 10)  # 10MB
    max_range_size: Annotated[int, Field(gt=0)] = Field(default=100000)
    restricted_tags: Set[str] = Field(default_factory=lambda: {"macro", "include", "import", "extends"})
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

    @field_validator("max_file_size", "max_memory_size", "max_range_size")
    @classmethod
    def validate_positive_limits(cls, v: int) -> int:
        """制限値が正の値であることを検証する。

        Args:
            v: 検証対象の値

        Returns:
            int: 検証済みの値

        Raises:
            ValueError: 値が0以下の場合
        """
        if v <= 0:
            raise ValueError("Limit must be a positive integer")
        return v


class RangeConfig(BaseModel):
    """rangeループの設定のバリデーションモデル。"""

    model_config = ConfigDict(strict=True)

    start: int = Field(default=0)
    stop: int
    step: int = Field(default=1)

    @field_validator("step")
    @classmethod
    def validate_step(cls, v: int) -> int:
        """ステップ値を検証する。

        Args:
            v: ステップ値

        Returns:
            int: 検証済みのステップ値

        Raises:
            ValueError: ステップ値が0の場合
        """
        if v == 0:
            raise ValueError("Step cannot be zero")
        return v


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


class HTMLContent(BaseModel):
    """HTMLコンテンツのバリデーションモデル。"""

    model_config = ConfigDict(strict=True)

    content: str = Field(...)

    @field_validator("content")
    @classmethod
    def validate_html_content(cls, v: str) -> str:
        """HTMLコンテンツを検証する。

        Args:
            v: 検証対象のコンテンツ

        Returns:
            str: 検証済みのコンテンツ

        Raises:
            ValueError: 安全でないHTML要素が含まれる場合
        """
        if not isinstance(v, str):
            raise ValueError("HTML content must be a string")

        # 安全でないHTMLパターンをチェック
        unsafe_patterns = [
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


class TemplateSecurityValidator:
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
    """

    def __init__(self) -> None:
        """初期化。"""
        self.config = TemplateConfig()
        self._validation_state = ValidationState()

    @property
    def max_file_size(self) -> int:
        """最大ファイルサイズを返す。"""
        return self.config.max_file_size

    @property
    def max_memory_size(self) -> int:
        """最大メモリ使用量を返す。"""
        return self.config.max_memory_size

    @property
    def max_range_size(self) -> int:
        """最大range値を返す。"""
        return self.config.max_range_size

    @property
    def restricted_tags(self) -> Set[str]:
        """禁止タグのセットを返す。"""
        return self.config.restricted_tags

    @property
    def restricted_attributes(self) -> Set[str]:
        """禁止属性のセットを返す。"""
        return self.config.restricted_attributes

    def validate_template(self, ast: nodes.Template) -> ValidationState:
        """テンプレートのセキュリティを検証する。

        Args:
            ast: 検証対象のテンプレートAST

        Returns:
            ValidationState: 検証結果
        """
        self._validation_state.reset()

        # 1. 禁止タグの検証
        if not self._validate_restricted_tags(ast, self._validation_state):
            return self._validation_state

        # 2. 属性アクセスの検証
        if not self._validate_restricted_attributes(ast, self._validation_state):
            return self._validation_state

        # 3. ループ範囲の検証 (リテラル値のみ)
        if not self._validate_loop_range(ast, self._validation_state):
            return self._validation_state

        return self._validation_state

    def validate_runtime_security(self, ast: nodes.Template, context: Dict[str, Any]) -> ValidationState:
        """ランタイムセキュリティの検証を実行する。

        Args:
            ast: 検証対象のテンプレートAST
            context: テンプレートに適用するコンテキスト

        Returns:
            ValidationState: 検証結果
        """
        validation_state = ValidationState()
        assignments: Dict[str, Any] = {}

        try:
            # 1. 再帰的構造の検出
            if not self._validate_recursive_structures(ast, context, assignments, validation_state):
                return validation_state

            # 2. ゼロ除算の検証
            if not self._validate_division_operations(ast, context, assignments, validation_state):
                return validation_state

            return validation_state

        except Exception as e:
            validation_state.set_error(f"Runtime validation error: {e!s}")
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
        for node in ast.find_all((nodes.Assign, nodes.For, nodes.Call)):
            try:
                if isinstance(node, nodes.Assign):
                    if not self._validate_assignment(node, context, assignments, validation_state):
                        return False
                elif isinstance(node, nodes.For):
                    if not self._validate_for_loop(node, context, assignments, validation_state):
                        return False
                elif isinstance(node, nodes.Call):
                    if not self._validate_function_call(node, context, assignments, validation_state):
                        return False
            except Exception as e:
                if "recursive structure detected" in str(e):
                    validation_state.set_error("Template security error: recursive structure detected")
                    return False
        return True

    def _validate_assignment(
        self, node: nodes.Assign, context: Dict[str, Any], assignments: Dict[str, Any], validation_state: ValidationState
    ) -> bool:
        """代入文を検証する。

        Args:
            node: 代入ノード
            context: テンプレートに適用するコンテキスト
            assignments: 変数の割り当て状態
            validation_state: 検証状態

        Returns:
            bool: 検証が成功したかどうか
        """
        if isinstance(node.target, nodes.Name):
            target_name = node.target.name
            try:
                value = self._evaluate_expression(node.node, context, assignments)
                assignments[target_name] = value
                return True
            except Exception as e:
                if "recursive structure detected" in str(e):
                    validation_state.set_error("Template security error: recursive structure detected")
                    return False
        return True

    def _validate_for_loop(
        self, node: nodes.For, context: Dict[str, Any], assignments: Dict[str, Any], validation_state: ValidationState
    ) -> bool:
        """forループを検証する。

        Args:
            node: forループノード
            context: テンプレートに適用するコンテキスト
            assignments: 変数の割り当て状態
            validation_state: 検証状態

        Returns:
            bool: 検証が成功したかどうか
        """
        if isinstance(node.iter, nodes.Name):
            iter_name = node.iter.name
            if iter_name in assignments:
                try:
                    self._evaluate_expression(node.iter, context, assignments)
                    return True
                except Exception as e:
                    if "recursive structure detected" in str(e):
                        validation_state.set_error("Template security error: recursive structure detected")
                        return False
        return True

    def _validate_function_call(
        self, node: nodes.Call, context: Dict[str, Any], assignments: Dict[str, Any], validation_state: ValidationState
    ) -> bool:
        """関数呼び出しを検証する。

        Args:
            node: 関数呼び出しノード
            context: テンプレートに適用するコンテキスト
            assignments: 変数の割り当て状態
            validation_state: 検証状態

        Returns:
            bool: 検証が成功したかどうか
        """
        try:
            self._evaluate_expression(node, context, assignments)
            return True
        except Exception as e:
            if "recursive structure detected" in str(e):
                validation_state.set_error("Template security error: recursive structure detected")
                return False
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
            try:
                right_value = self._evaluate_expression(node.right, context, assignments)
                if right_value == 0:
                    validation_state.set_error("Template security error: division by zero is not allowed")
                    return False
            except Exception:
                logging.exception("Template security error: division by zero is not allowed")
                return False
        return True

    def validate_safe_content(self, node: nodes.Filter) -> ValidationState:
        """safeフィルターで使用されるコンテンツの安全性を検証する。

        Args:
            node: フィルターノード

        Returns:
            ValidationState: 検証結果
        """
        validation_state = ValidationState()
        try:
            if isinstance(node.node, nodes.Const):
                content = str(node.node.value)
                HTMLContent(content=content)  # バリデーションのみ実行
            else:
                validation_state.set_error("Content validation error: node is not a constant")
        except ValidationError as e:
            validation_state.set_error(f"HTML content validation error: {e!s}")
        except Exception as e:
            validation_state.set_error(f"Content validation error: {e!s}")
        return validation_state

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
            html_content = HTMLContent(content=value)
            return Markup("").join(html_content.content)
        except ValidationError as e:
            raise ValueError(str(e)) from e

    def _is_recursive_structure(self, value: RecursiveValue) -> bool:
        """値が再帰的構造かどうかを判定する。

        Args:
            value: チェック対象の値

        Returns:
            bool: 再帰的構造の場合はTrue
        """
        try:
            # 循環参照を検出するための集合
            seen: Set[int] = set()

            def check_recursive(v: RecursiveValue, depth: int = 0) -> bool:
                if depth > 100:  # 再帰の深さ制限
                    return True

                # オブジェクトのIDを取得
                obj_id = id(v)
                if obj_id in seen:
                    return True

                # リストや辞書の場合は、その要素も確認
                if isinstance(v, (list, dict, set)):
                    seen.add(obj_id)
                    try:
                        if isinstance(v, (list, set)):
                            for item in v:
                                if check_recursive(cast("RecursiveValue", item), depth + 1):
                                    return True
                        else:  # dict
                            for item in v.values():
                                if check_recursive(cast("RecursiveValue", item), depth + 1):
                                    return True
                        return False
                    finally:
                        seen.remove(obj_id)

                return False

            return check_recursive(value)
        except Exception:
            # 再帰的構造の検出に失敗した場合は、安全のためTrueを返す
            return True

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
                raise TypeError("Cannot evaluate expression")
            return evaluator(node, context, assignments)
        except Exception as e:
            if "recursive structure detected" in str(e):
                raise ValueError("recursive structure detected") from e
            raise TypeError("Cannot evaluate expression") from e

    def _get_node_evaluator(
        self,
        node: nodes.Node,
    ) -> Optional[NodeEvaluator[nodes.Node]]:
        """ノードに対応する評価関数を取得する。

        Args:
            node: 評価対象のノード

        Returns:
            Optional[Callable]: 評価関数 [対応する評価関数がない場合はNone]
        """
        evaluators: Dict[type[nodes.Node], NodeEvaluator[nodes.Node]] = {
            nodes.Name: self._evaluate_name,  # type: ignore
            nodes.Const: self._evaluate_const,  # type: ignore
            nodes.List: self._evaluate_list,  # type: ignore
            nodes.Dict: self._evaluate_dict,  # type: ignore
            nodes.Call: self._evaluate_call,  # type: ignore
            nodes.Getattr: self._evaluate_getattr,  # type: ignore
            nodes.BinExpr: self._evaluate_binexpr,  # type: ignore
        }
        return evaluators.get(type(node))

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
        name = node.name
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
    ) -> List[Any]:
        """リストを評価する。

        Args:
            node: リストノード
            context: テンプレートに適用するコンテキスト
            assignments: 変数の割り当て状態

        Returns:
            List[Any]: 評価結果

        Raises:
            ValueError: 再帰的構造が検出された場合
        """
        values: List[Any] = []
        for item in node.items:
            value = self._evaluate_expression(item, context, assignments)
            values.append(value)
        if self._is_recursive_structure(cast("RecursiveValue", values)):
            raise ValueError("recursive structure detected")
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
        if self._is_recursive_structure(cast("RecursiveValue", result)):
            raise ValueError("recursive structure detected")
        return result

    def _evaluate_call(
        self,
        node: nodes.Call,
        context: Dict[str, Any],
        assignments: Dict[str, Any],
    ) -> Optional[List[Any]]:
        """メソッド呼び出しを評価する。

        Args:
            node: メソッド呼び出しノード
            context: テンプレートに適用するコンテキスト
            assignments: 変数の割り当て状態

        Returns:
            Optional[List[Any]]: 評価結果
        """
        if not self._is_valid_list_operation(node):
            return None

        node_attr = cast("nodes.Getattr", node.node)
        obj = self._evaluate_expression(node_attr.node, context, assignments)
        if not isinstance(obj, list):
            return None

        method_name = node_attr.attr
        args = self._evaluate_call_arguments(node, node_attr, context, assignments)

        return self._execute_list_operation(obj, method_name, args)

    def _is_valid_list_operation(self, node: nodes.Call) -> bool:
        """リスト操作が有効かどうかを検証する。

        Args:
            node: メソッド呼び出しノード

        Returns:
            bool: 有効な場合はTrue
        """
        if not isinstance(node.node, nodes.Getattr):
            return False

        method_name = node.node.attr
        return method_name in ["append", "extend"]

    def _evaluate_call_arguments(
        self,
        node: nodes.Call,
        node_attr: nodes.Getattr,
        context: Dict[str, Any],
        assignments: Dict[str, Any],
    ) -> List[Any]:
        """メソッド呼び出しの引数を評価する。

        Args:
            node: メソッド呼び出しノード
            node_attr: 属性アクセスノード
            context: テンプレートに適用するコンテキスト
            assignments: 変数の割り当て状態

        Returns:
            List[Any]: 評価された引数のリスト

        Raises:
            ValueError: 再帰的構造が検出された場合
        """
        args = [self._evaluate_expression(arg, context, assignments) for arg in node.args]
        obj = self._evaluate_expression(node_attr.node, context, assignments)

        if any(arg is obj or self._is_recursive_structure(cast("RecursiveValue", arg)) for arg in args):
            raise ValueError("recursive structure detected")

        return args

    def _execute_list_operation(
        self,
        obj: List[Any],
        method_name: str,
        args: List[Any],
    ) -> List[Any]:
        """リスト操作を実行する。

        Args:
            obj: 対象のリスト
            method_name: メソッド名
            args: 引数リスト

        Returns:
            List[Any]: 操作結果のリスト

        Raises:
            TypeError: 引数が不正な場合
            ValueError: 再帰的構造が検出された場合
        """
        new_list = obj.copy()

        if method_name == "append":
            new_list.append(args[0])
        elif method_name == "extend":
            if not isinstance(args[0], (list, tuple, set)):
                raise TypeError("extend() argument must be iterable")
            new_list.extend(cast("Sequence[Any]", args[0]))

        if self._is_recursive_structure(cast("RecursiveValue", new_list)):
            raise ValueError("recursive structure detected")

        return new_list

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
        obj = self._evaluate_expression(node.node, context, assignments)
        if obj is None:
            return None

        try:
            value = getattr(obj, node.attr)
            if isinstance(value, (type(None), str, Decimal, list, dict, bool)):
                return cast("EvaluatedValue", value)
            return None
        except AttributeError:
            return None

    def _evaluate_binexpr(
        self,
        node: nodes.BinExpr,
        context: Dict[str, Any],
        assignments: Dict[str, Any],
    ) -> Union[Decimal, str]:
        """二項演算を評価する。

        Args:
            node: 二項演算ノード
            context: テンプレートに適用するコンテキスト
            assignments: 変数の割り当て状態

        Returns:
            Union[Decimal, str]: 評価結果

        Raises:
            TypeError: サポートされていない演算子の場合
        """
        left = self._evaluate_expression(node.left, context, assignments)
        right = self._evaluate_expression(node.right, context, assignments)

        if not isinstance(left, (Decimal, str)) or not isinstance(right, (Decimal, str)):
            raise TypeError("Binary operations are only supported for numbers and strings")

        if isinstance(node, nodes.Div) and right == 0:
            raise ValueError("division by zero is not allowed")

        # 文字列の場合は加算のみ許可
        if isinstance(left, str) or isinstance(right, str):
            return self._evaluate_string_operation(node, left, right)

        # 数値の場合は全ての演算を許可
        return self._evaluate_numeric_operation(node, left, right)

    def _evaluate_string_operation(
        self,
        node: nodes.BinExpr,
        left: Union[Decimal, str],
        right: Union[Decimal, str],
    ) -> str:
        """文字列演算を評価する。

        Args:
            node: 二項演算ノード
            left: 左辺の値
            right: 右辺の値

        Returns:
            str: 評価結果

        Raises:
            TypeError: 加算以外の演算子が使用された場合
        """
        if not isinstance(node, nodes.Add):
            raise TypeError("Only addition is supported for strings")
        return str(left) + str(right)

    def _evaluate_numeric_operation(
        self,
        node: nodes.BinExpr,
        left: Union[Decimal, str],
        right: Union[Decimal, str],
    ) -> Decimal:
        """数値演算を評価する。

        Args:
            node: 二項演算ノード
            left: 左辺の値
            right: 右辺の値

        Returns:
            Decimal: 評価結果

        Raises:
            TypeError: サポートされていない演算子の場合
            ValueError: 無効な数値演算の場合
        """
        left_num = cast("Decimal", left)
        right_num = cast("Decimal", right)

        # Use lambdas for simple arithmetic operations
        operator_map: Dict[type[nodes.BinExpr], Callable[[Decimal, Decimal], Decimal]] = {
            nodes.Add: lambda a, b: a + b,
            nodes.Sub: lambda a, b: a - b,
            nodes.Mul: lambda a, b: a * b,
            nodes.Div: lambda a, b: a / b,  # Division by zero checked earlier
            nodes.FloorDiv: lambda a, b: Decimal(a // b),
            nodes.Mod: lambda a, b: a % b,
            nodes.Pow: lambda a, b: Decimal(pow(float(a), float(b))),
        }

        operator_func = operator_map.get(type(node))
        if operator_func is None:
            raise TypeError(f"Unsupported binary operator: {type(node).__name__}")

        try:
            return operator_func(left_num, right_num)
        except decimal.InvalidOperation as e:
            raise ValueError(f"Invalid numeric operation: {e!s}") from e

    def _validate_restricted_tags(self, ast: nodes.Template, validation_state: ValidationState) -> bool:
        """禁止タグを検証する。

        Args:
            ast: 検証対象のAST
            validation_state: 検証状態

        Returns:
            bool: 検証が成功したかどうか
        """
        for node in ast.find_all((nodes.Macro, nodes.Include, nodes.Import, nodes.Extends)):
            tag_name = node.__class__.__name__.lower()
            if tag_name in self.restricted_tags:
                validation_state.set_error(f"Template security error: '{tag_name}' tag is not allowed")
                return False
        return True

    def _check_getattr(self, node: nodes.Getattr, validation_state: ValidationState) -> bool:
        """Getattrノードを検証する。"""
        attribute_name = node.attr
        if attribute_name in self.restricted_attributes:
            validation_state.set_error(
                f"Template security validation failed: Access to restricted attribute '{attribute_name}' is forbidden."
            )
            return False
        return True

    def _check_getitem(self, node: nodes.Getitem, validation_state: ValidationState) -> bool:
        """Getitemノードを検証する。"""
        if isinstance(node.arg, nodes.Const) and isinstance(node.arg.value, str):
            attribute_name = node.arg.value
            if attribute_name in self.restricted_attributes:
                validation_state.set_error(
                    f"Template security validation failed: Access to restricted item '{attribute_name}' is forbidden."
                )
                return False
        return True

    def _check_name(self, node: nodes.Name, validation_state: ValidationState) -> bool:
        """Nameノードを検証する。"""
        variable_name = node.name
        if variable_name in self.restricted_attributes:
            validation_state.set_error(f"Template security validation failed: Use of restricted variable '{variable_name}' is forbidden.")
            return False
        return True

    def _check_call(self, node: nodes.Call, validation_state: ValidationState) -> bool:
        """Callノードを検証する。"""
        if isinstance(node.node, nodes.Name):
            function_name = node.node.name
            if function_name in self.restricted_attributes:
                validation_state.set_error(
                    f"Template security validation failed: Call to restricted function '{function_name}()' is forbidden."
                )
                return False
        return True

    def _check_assign(self, node: nodes.Assign, validation_state: ValidationState) -> bool:
        """Assignノードを検証する。"""
        # Check if the assigned value is a restricted name
        if isinstance(node.node, nodes.Name) and node.node.name in self.restricted_attributes:
            variable_name = node.node.name
            validation_state.set_error(
                f"Template security validation failed: Assignment of restricted variable '{variable_name}' is forbidden."
            )
            return False
        # Check if the assigned value is a call to a restricted function
        elif (
            isinstance(node.node, nodes.Call)
            and isinstance(node.node.node, nodes.Name)
            and node.node.node.name in self.restricted_attributes
        ):
            function_name = node.node.node.name
            validation_state.set_error(
                f"Template security validation failed: Assignment involving restricted function '{function_name}()' is forbidden."
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
        handler_map: Dict[type[nodes.Node], Callable[[Any, ValidationState], bool]] = {
            nodes.Getattr: self._check_getattr,  # type: ignore
            nodes.Getitem: self._check_getitem,  # type: ignore
            nodes.Name: self._check_name,
            nodes.Call: self._check_call,
            nodes.Assign: self._check_assign,  # type: ignore
        }

        nodes_to_check = list(ast.find_all(tuple(handler_map.keys())))

        for node in nodes_to_check:
            node_type = type(node)
            handler = handler_map.get(node_type)

            if handler:
                # Note: We pass the specific node type expected by the handler.
                # The type ignore comments are necessary because the map values have a broader type hint.
                if not handler(node, validation_state):
                    return False
            # If no handler is found for the node type, it's ignored (as intended).

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
                range_config = RangeConfig(stop=stop)
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

        try:
            # ファイルの内容を取得
            current_pos = template_file.tell()
            content = template_file.read()
            template_file.seek(current_pos)  # 元の位置に戻す

            # ファイルサイズの検証
            if len(content) > self.max_file_size:
                validation_state.set_error(f"Template file size exceeds maximum limit of {self.max_file_size} bytes")
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

            # セキュリティチェック (静的検証のみ)
            if not self.validate_template(ast).is_valid:
                validation_state.set_error("Template security validation failed")
                return None, None

            return template_content, ast

        except Exception as e:
            validation_state.set_error(f"Template file validation error: {e!s}")
            return None, None

    def _validate_syntax(self, template_content: str, validation_state: ValidationState) -> Optional[nodes.Template]:
        """テンプレートの構文を検証する。

        Args:
            template_content: テンプレートの内容
            validation_state: 検証状態

        Returns:
            Optional[nodes.Template]: 構文解析結果 (エラーの場合はNone)
        """
        try:
            env = Environment(autoescape=True)
            return env.parse(template_content)
        except jinja2.TemplateSyntaxError as e:
            validation_state.set_error(str(e))
            return None
        except Exception as e:
            validation_state.set_error(f"Template syntax error: {e!s}")
            return None
