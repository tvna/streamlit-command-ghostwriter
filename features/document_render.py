"""テンプレートのレンダリングと検証を行うモジュール。

このモジュールは、テンプレートファイルの検証、レンダリング、フォーマットを行う機能を提供します。
主な機能:
- テンプレートファイルの構文とセキュリティの検証
- コンテキストデータの適用とレンダリング
- レンダリング結果のフォーマット処理

クラス階層:
- ValidationModels: バリデーションモデル
  - FormatConfig: フォーマット設定
  - ContextConfig: コンテキスト設定
  - ValidationState: 検証状態
- DocumentRender: メインのレンダリングクラス
  - FileValidator: ファイルサイズの検証
  - ContentFormatter: フォーマット処理
  - TemplateSecurityValidator: テンプレートのセキュリティ検証

検証プロセス:
1. 入力検証
   - Pydanticモデルによるバリデーション
   - フォーマット設定の検証
   - コンテキストデータの型チェック

2. ファイル検証
   - FileValidatorによるサイズ制限のチェック
   - エンコーディングの検証 (UTF-8)
   - バイナリデータの検出

3. テンプレートの検証
   - 構文チェック (Jinja2 AST)
   - セキュリティチェック (禁止タグ、属性)
   - 再帰的構造の検出
   - ループ範囲の制限

4. コンテキストの適用
   - 変数の型チェック
   - 未定義変数の検証 (strict/non-strictモード)
   - メモリ使用量の制限
   - 再帰的構造の防止

5. 出力フォーマット
   - 空白行の処理 (保持/圧縮/削除)
   - 改行の正規化
   - HTMLコンテンツの安全性確認

エラー処理:
- ValidationError: Pydanticによる検証エラー
- ValueError: 値の検証エラー
- TypeError: 型の不一致エラー
- UnicodeError: エンコーディングエラー
- TemplateError: テンプレート処理エラー

セキュリティ機能:
- HTMLエスケープのデフォルト有効化
- 安全なフィルター実装 (safe, html_safe)
- 再帰的構造の検出と防止
- メモリ使用量の制限
- ループ回数の制限

典型的な使用方法:
```python
with open('template.txt', 'rb') as f:
    template_file = BytesIO(f.read())
    renderer = DocumentRender(template_file)
    if renderer.is_valid_template:
        context = {'name': 'World'}
        format_config = FormatConfig(format_type=2)  # NORMALIZE_BREAKS
        if renderer.apply_context(context, format_config.format_type):
            result = renderer.render_content
```
"""

from datetime import datetime
from decimal import Decimal
from functools import wraps
from io import BytesIO
from typing import (
    Annotated,
    Any,
    Callable,
    ClassVar,
    Dict,
    Final,
    List,
    Optional,
    TypeAlias,
    TypeVar,
    Union,
)

import jinja2
from jinja2 import Environment, Template, nodes
from jinja2.runtime import StrictUndefined, Undefined
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, ValidationError

from .validate_template import TemplateSecurityValidator, ValidationState
from .validate_uploaded_file import FileSizeConfig, FileValidator

# --- Format Type Constants ---
FORMAT_TYPE_KEEP: Final[int] = 0  # Keep whitespace
FORMAT_TYPE_COMPRESS: Final[int] = 1  # Compress consecutive whitespace lines to one
FORMAT_TYPE_KEEP_ALT: Final[int] = 2  # Alias for KEEP
FORMAT_TYPE_COMPRESS_ALT: Final[int] = 3  # Alias for COMPRESS
FORMAT_TYPE_REMOVE_ALL: Final[int] = 4  # Remove all whitespace lines
MIN_FORMAT_TYPE: Final[int] = FORMAT_TYPE_KEEP
MAX_FORMAT_TYPE: Final[int] = FORMAT_TYPE_REMOVE_ALL

# --- Validation Constants ---
MAX_BYTES_PER_CHAR_UTF8: Final[int] = 4  # Maximum bytes per character assumed for UTF-8 estimate

T = TypeVar("T")
ValueType: TypeAlias = Union[str, Decimal, bool, None]
ListType: TypeAlias = List[Union[ValueType, "ListType", "DictType"]]
DictType: TypeAlias = Dict[str, Union[ValueType, ListType, "DictType"]]
ContextType: TypeAlias = Dict[str, Union[ValueType, ListType, DictType]]
RecursiveValue: TypeAlias = Union[ValueType, ListType, DictType]
ContainerType: TypeAlias = Union[ValueType, ListType, DictType]


def undefined_operation(func: Callable[..., T]) -> Callable[["CustomUndefined", "OperandType"], str]:
    """未定義変数に対する演算を処理するデコレータ。

    Args:
        func: デコレート対象の関数

    Returns:
        常に空文字列を返す関数
    """

    @wraps(func)
    def wrapper(self: "CustomUndefined", other: "OperandType") -> str:
        return ""

    return wrapper


class CustomUndefined(Undefined):
    """非strictモード用のカスタムUndefinedクラス。

    未定義変数に対して以下の動作を提供します:
    - 属性アクセス: 空文字列を返す
    - 文字列化: 空文字列を返す
    - 演算: 空文字列を返す
    - 比較: False を返す
    """

    # __init__ uses parent Undefined.__init__

    def __getattr__(self, name: str) -> "CustomUndefined":
        return self

    def __str__(self) -> str:
        return ""

    def __html__(self) -> str:
        return ""

    def __bool__(self) -> bool:
        return False

    def __eq__(self, other: object) -> bool:
        # Allow comparison with Undefined and CustomUndefined itself
        return isinstance(other, (Undefined, CustomUndefined))

    # 算術演算子のサポート
    @undefined_operation
    def __add__(self, other: "OperandType") -> str:  # type: ignore[override]
        return ""

    @undefined_operation
    def __radd__(self, other: "OperandType") -> str:  # type: ignore[override]
        return ""

    @undefined_operation
    def __sub__(self, other: "OperandType") -> str:  # type: ignore[override]
        return ""

    @undefined_operation
    def __rsub__(self, other: "OperandType") -> str:  # type: ignore[override]
        return ""

    @undefined_operation
    def __mul__(self, other: "OperandType") -> str:  # type: ignore[override]
        return ""

    @undefined_operation
    def __rmul__(self, other: "OperandType") -> str:  # type: ignore[override]
        return ""

    @undefined_operation
    def __truediv__(self, other: "OperandType") -> str:  # type: ignore[override]
        return ""

    @undefined_operation
    def __rtruediv__(self, other: "OperandType") -> str:  # type: ignore[override]
        return ""

    @undefined_operation
    def __floordiv__(self, other: "OperandType") -> str:  # type: ignore[override]
        return ""

    @undefined_operation
    def __rfloordiv__(self, other: "OperandType") -> str:  # type: ignore[override]
        return ""

    @undefined_operation
    def __mod__(self, other: "OperandType") -> str:  # type: ignore[override]
        return ""

    @undefined_operation
    def __rmod__(self, other: "OperandType") -> str:  # type: ignore[override]
        return ""

    def __call__(self, *args: object, **kwargs: object) -> "CustomUndefined":  # type: ignore[override]
        return self


# OperandType referencing the now module-level CustomUndefined
OperandType = Union[str, int, float, bool, Undefined, CustomUndefined]

# ---------------------------------------------------------------------------


class FormatConfig(BaseModel):
    """フォーマット設定のバリデーションモデル。"""

    model_config = ConfigDict(strict=True)

    # Use constants for validation range
    format_type: Annotated[int, Field(ge=MIN_FORMAT_TYPE, le=MAX_FORMAT_TYPE)]
    is_strict_undefined: bool = Field(default=True)


class ContextConfig(BaseModel):
    """コンテキスト設定のバリデーションモデル。"""

    model_config = ConfigDict(strict=True)

    context: Dict[str, Any] = Field(default_factory=dict)
    format_config: FormatConfig


class ContentFormatter(BaseModel):
    """テンプレート出力のフォーマット処理を行うクラス。

    フォーマットタイプ:
        0: 空白行を保持
        1: 連続する空白行を1行に圧縮
        2: 空白行を保持 (タイプ0と同じ)
        3: 連続する空白行を1行に圧縮 (タイプ1と同じ)
        4: すべての空白行を削除
    """

    def format(self, content: str, format_type: int) -> str:
        """コンテンツをフォーマットする。

        Args:
            content: フォーマット対象の文字列
            format_type: フォーマットタイプ

        Returns:
            フォーマット後の文字列
        """
        # Use format type constants
        if format_type in [FORMAT_TYPE_COMPRESS, FORMAT_TYPE_COMPRESS_ALT]:
            return self._compress_whitespace(content)
        elif format_type == FORMAT_TYPE_REMOVE_ALL:
            return self._remove_all_whitespace(content)

        return content

    def _compress_whitespace(self, content: str) -> str:
        """連続する空白行を1行に圧縮する。

        Args:
            content: 圧縮対象の文字列

        Returns:
            圧縮後の文字列
        """
        lines: List[str] = content.splitlines(True)
        result: List[str] = []
        prev_empty: bool = False

        for line in lines:
            is_empty = not line.strip()
            if not is_empty:
                result.append(line)
                prev_empty = False
            elif not prev_empty:
                result.append("\n")
                prev_empty = True

        return "".join(result)

    def _remove_all_whitespace(self, content: str) -> str:
        """すべての空白行を削除する。

        Args:
            content: 処理対象の文字列

        Returns:
            処理後の文字列
        """
        lines: List[str] = content.splitlines(True)
        result: List[str] = [line for line in lines if line.strip()]
        return "".join(result)


class DocumentRender(BaseModel):
    """テンプレートのレンダリングと検証を行うクラス。

    テンプレートファイルの検証、レンダリング、フォーマットを一貫して処理します。
    Pydanticモデルによる厳密な入力検証、セキュリティチェック、メモリ使用量の制限を提供します。

    主な機能:
    1. 入力検証
       - フォーマット設定の検証 (FormatConfig)
       - コンテキストデータの検証 (ContextConfig)
       - 検証状態の管理 (ValidationState)

    2. セキュリティ検証
       - テンプレートの構文チェック
       - 禁止タグ・属性の検出
       - 再帰的構造の防止
       - メモリ使用量の制限
       - HTMLコンテンツの安全性確認

    3. レンダリング処理
       - 未定義変数の処理 (strict/non-strictモード)
       - エラー処理の一元管理
       - メモリ使用量の監視
       - 出力フォーマットの制御

    Attributes:
        MAX_FILE_SIZE_BYTES: テンプレートファイルの最大サイズ [バイト]
            デフォルト: 30MB
        MAX_MEMORY_SIZE_BYTES: レンダリング結果の最大メモリ使用量 [バイト]
            デフォルト: 150MB

    Properties:
        is_valid_template: テンプレートが有効かどうか
        error_message: エラーメッセージ (エラーがない場合はNone)
        render_content: レンダリング結果 (レンダリングが行われていない場合はNone)

    エラー処理:
    - ValidationError: 入力値の検証エラー
    - ValueError: ファイルサイズ、メモリ使用量などの制限超過
    - UnicodeError: エンコーディングエラー
    - TemplateError: テンプレート処理エラー
    """

    MAX_FILE_SIZE_BYTES: ClassVar[int] = 30 * 1024 * 1024  # 30MB
    MAX_MEMORY_SIZE_BYTES: ClassVar[int] = 150 * 1024 * 1024  # 150MB

    _ast: Optional[nodes.Template] = PrivateAttr(default=None)
    _file_validator = FileValidator(size_config=FileSizeConfig(max_size_bytes=MAX_FILE_SIZE_BYTES))
    _formatter = ContentFormatter()
    _is_strict_undefined: bool = PrivateAttr(default=True)
    _render_content: Optional[str] = PrivateAttr(default=None)
    _template_content: Optional[str] = PrivateAttr(default=None)
    _template_file: Optional[BytesIO] = PrivateAttr(default=None)
    _security_validator = TemplateSecurityValidator(max_file_size_bytes=MAX_FILE_SIZE_BYTES, max_memory_size_bytes=MAX_MEMORY_SIZE_BYTES)
    _validation_state = ValidationState()

    def __init__(self, template_file: BytesIO) -> None:
        """DocumentRenderインスタンスを初期化する。

        Args:
            template_file: テンプレートファイル (BytesIO)

        Note:
            初期検証に失敗した場合、エラー状態を保持します。
            エラー状態は is_valid_template と error_message プロパティで確認できます。
        """

        super().__init__()
        self._file_validator.validate_size(template_file)
        self._template_file = template_file

        # 初期検証を実行
        template_content: Optional[str] = None
        ast: Optional[nodes.Template] = None
        template_content, ast = self._security_validator.validate_template_file(self._template_file, self._validation_state)
        if self._validation_state.is_valid:
            self._template_content = template_content
            self._ast = ast

    @property
    def is_valid_template(self) -> bool:
        """テンプレートが有効かどうかを返す。

        Returns:
            bool: テンプレートが有効な場合はTrue
        """
        return self._validation_state.is_valid

    @property
    def error_message(self) -> Optional[str]:
        """エラーメッセージを返す。

        Returns:
            Optional[str]: エラーメッセージ (エラーがない場合はNone)
        """
        return self._validation_state.error_message

    @property
    def render_content(self) -> Optional[str]:
        """レンダリング結果を返す。

        Returns:
            Optional[str]: レンダリング結果 (レンダリングが行われていない場合はNone)
        """
        return self._render_content

    def _handle_rendering_error(self, e: Exception) -> bool:
        """レンダリングエラーを処理する。

        発生した例外の種類に応じて適切なエラーメッセージを設定します。
        - Jinja2の未定義変数エラー
        - Jinja2のテンプレートエラー
        - その他の例外

        Args:
            e: 発生した例外

        Returns:
            常にFalse
        """
        if isinstance(e, jinja2.UndefinedError):
            self._validation_state.set_error(f"Template runtime error: {e!s}")
        else:
            self._validation_state.set_error(f"Template runtime error: {e!s}")
        return False

    def _validate_input_config(self, context: Dict[str, Any], format_type: int, is_strict_undefined: bool) -> Optional[ContextConfig]:
        """入力設定のバリデーションを行う。

        Args:
            context: テンプレートに適用するコンテキスト
            format_type: フォーマットタイプ (0-4の整数)
            is_strict_undefined: 未定義変数を厳密にチェックするかどうか

        Returns:
            Optional[ContextConfig]: バリデーション済みの設定 (エラー時はNone)
        """
        try:
            # FormatConfig のバリデーション
            format_config = FormatConfig(format_type=format_type, is_strict_undefined=is_strict_undefined)
            # ContextConfig のバリデーション (context はここで検証される)
            return ContextConfig(context=context, format_config=format_config)
        except ValidationError as e:
            # エラーリストから最初の詳細なエラーメッセージを取得
            # TODO(all): Handle multiple errors if needed
            first_error = e.errors()[0]
            error_field = ".".join(map(str, first_error["loc"])) if first_error.get("loc") else "input"
            error_msg = first_error["msg"]
            # より具体的なエラーメッセージを設定
            self._validation_state.set_error(f"Validation error: {error_msg} at '{error_field}'")
            return None

    def _render_template(self, context: Dict[str, Any], template_content: str) -> Optional[str]:
        """テンプレートをレンダリングする。

        Args:
            context: テンプレートに適用するコンテキスト

        Returns:
            Optional[str]: レンダリング結果 (エラー時はNone)
        """
        try:
            env: Environment = self._create_environment()
            template: Template = env.from_string(template_content)
            return template.render(**context)
        except Exception as e:
            self._handle_rendering_error(e)
            return None

    def apply_context(self, context: Dict[str, Any], format_type: int, is_strict_undefined: bool = True) -> bool:
        """テンプレートにコンテキストを適用する。

        Args:
            context: テンプレートに適用するコンテキスト
            format_type: フォーマットタイプ (0-4の整数)
            is_strict_undefined: 未定義変数を厳密にチェックするかどうか

        Returns:
            bool: コンテキストの適用が成功したかどうか

        Note:
            このメソッドは以下の順序で処理を行います:
            1. 前提条件の検証
            2. 入力設定のバリデーション
            3. テンプレートの状態検証
            4. レンダリング処理
            5. メモリ使用量の検証
            6. フォーマット処理
        """
        if not self._validation_state.is_valid:
            return False

        if self._template_content is None:
            return False

        config: Optional[ContextConfig] = self._prepare_context_config(context, format_type, is_strict_undefined)
        if config is None or not self._validation_state.is_valid:
            return False

        rendered_content: Optional[str] = self._process_template(config, self._template_content)
        if rendered_content is None or not self._validation_state.is_valid:
            return False

        if not self._validate_memory_usage(rendered_content):
            return False

        self._render_content = self._formatter.format(rendered_content, config.format_config.format_type)
        return True

    def _prepare_context_config(self, context: Dict[str, Any], format_type: int, is_strict_undefined: bool) -> Optional[ContextConfig]:
        """コンテキスト設定を準備する。

        Args:
            context: テンプレートに適用するコンテキスト
            format_type: フォーマットタイプ
            is_strict_undefined: 未定義変数を厳密にチェックするかどうか

        Returns:
            Optional[ContextConfig]: 検証済みの設定
        """
        config: Optional[ContextConfig] = self._validate_input_config(context, format_type, is_strict_undefined)
        if config is None or self._ast is None:
            return None

        self._validation_state = self._security_validator.validate_runtime_security(self._ast, context)
        self._is_strict_undefined = config.format_config.is_strict_undefined

        return config

    def _process_template(self, config: ContextConfig, template_content: str) -> Optional[str]:
        """テンプレートの処理を行う。

        Args:
            config: コンテキスト設定

        Returns:
            Optional[str]: レンダリング結果
        """

        rendered: Optional[str] = self._render_template(config.context, template_content)
        if rendered is None:
            return None

        return rendered

    def _validate_memory_usage(self, content: str) -> bool:
        """メモリ使用量を検証する。

        レンダリング結果のメモリ使用量が制限値を超えていないかチェックします。
        バイナリデータの検出とUTF-8エンコードのサイズ計算を行います。

        Args:
            content: 検証対象のコンテンツ

        Returns:
            メモリ使用量が制限内の場合はTrue
        """

        # メモリ使用量の検証
        content_size: Final[int] = len(content.encode("utf-8"))
        if content_size > self.MAX_MEMORY_SIZE_BYTES:
            self._validation_state.set_error(f"Memory consumption exceeds maximum limit of {self.MAX_MEMORY_SIZE_BYTES} bytes")
            return False
        return True

    def _create_environment(self) -> Environment:
        """Jinja2環境を作成する。

        カスタムフィルターやセキュリティ設定を含む環境を作成します。
        デフォルトでHTMLエスケープを有効化し、安全性を確保します。

        Returns:
            Environment: 設定済みのJinja2環境
        """
        env: Environment = Environment(
            autoescape=True,  # HTMLエスケープをデフォルトで有効化
            undefined=StrictUndefined if self._is_strict_undefined else CustomUndefined,
            extensions=["jinja2.ext.do"],  # 'do'拡張を有効化
        )

        # カスタムフィルターの登録
        env.filters["date"] = self._date_filter
        env.filters["safe"] = self._security_validator.html_safe_filter  # safeフィルターを安全な実装に変更
        env.filters["html_safe"] = self._security_validator.html_safe_filter

        return env

    def _date_filter(self, value: str, format_str: str = "%Y-%m-%d") -> str:
        """日付文字列をフォーマットする。

        Args:
            value: 日付文字列または datetime オブジェクト
            format_str: 出力フォーマット

        Returns:
            フォーマットされた日付文字列

        Raises:
            ValueError: 日付の解析に失敗した場合
        """

        try:
            # ISO形式の日付文字列をパース
            dt: datetime = datetime.fromisoformat(value.replace("Z", "+00:00"))

            return dt.strftime(format_str)

        except ValueError as e:
            raise ValueError("Invalid date format") from e
