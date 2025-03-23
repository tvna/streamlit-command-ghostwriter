"""テンプレートのレンダリングと検証を行うモジュール。

このモジュールは、テンプレートの検証、レンダリング、フォーマット処理を提供します。
主な機能は以下の通りです：

1. テンプレートの検証
   - 構文チェック
   - セキュリティチェック
   - ファイルサイズの検証
2. コンテキストの適用
   - 変数の検証
   - 型チェック
3. 出力フォーマット
   - 空白行の処理
   - 改行の正規化

クラス階層：
- DocumentRender: メインのレンダリングクラス
  - TemplateValidator: テンプレート検証
  - ContentFormatter: フォーマット処理
  - TemplateSecurityValidator: テンプレートのセキュリティ検証
  - ContextValidator: コンテキスト検証

TODO:
1. セキュリティ検証の改善 [CWE-94]
   - マクロの使用に関するセキュリティチェックの強化
   - テンプレートインジェクション対策の見直し
   - 再帰的な構造の検出精度の向上

2. ファイルサイズ制限の検証方法の改善
   - 現在の実装: read()メソッドの戻り値のサイズをチェック
   - 課題: メモリ効率が悪い（ファイル全体をメモリに読み込む）
   - 改善案: seek()とtell()を使用したファイルサイズの事前チェック

3. エラーメッセージの一貫性確保
   - ValidationResultクラスのエラーメッセージフォーマットの統一
   - 各種バリデーションエラーの明確な区別

典型的な使用方法:
```python
with open('template.txt', 'rb') as f:
    template_file = BytesIO(f.read())
    renderer = DocumentRender(template_file)
    if renderer.is_valid_template:
        renderer.apply_context({'name': 'World'}, format_type=FormatType.NORMALIZE_BREAKS)
        result = renderer.render_content
```
"""

import re
from datetime import datetime
from enum import IntEnum
from io import BytesIO
from typing import Annotated, Any, ClassVar, Dict, Optional, Self, Union

import jinja2
from jinja2 import Environment, nodes
from jinja2.runtime import StrictUndefined, Undefined
from markupsafe import Markup
from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)


class ValidationResult(BaseModel):
    """検証結果を表すクラス。

    検証の結果と、エラーメッセージを保持します。
    pydanticのBaseModelを継承し、型の安全性とバリデーションを提供します。

    Attributes:
        is_valid (bool): 検証が成功したかどうか
        error_message (str): エラーメッセージ（検証が失敗した場合のみ有効）
        content (Optional[str]): 検証済みのコンテンツ（エンコーディング検証時のみ使用）
    """

    is_valid: bool = Field(default=True, description="検証が成功したかどうか")
    error_message: str = Field(default="", description="エラーメッセージ（検証が失敗した場合のみ有効）")
    content: Optional[str] = Field(default=None, description="検証済みのコンテンツ（エンコーディング検証時のみ使用）")

    model_config = ConfigDict(frozen=True)

    @field_validator("error_message")
    @classmethod
    def validate_error_message(cls, v: str, info: ValidationInfo) -> str:
        """エラーメッセージのバリデーションを行う。

        検証が失敗している場合は、エラーメッセージが必須です。

        Args:
            v (str): エラーメッセージ
            info (ValidationInfo): バリデーション情報

        Returns:
            str: バリデーション済みのエラーメッセージ

        Raises:
            ValueError: 検証が失敗しているのにエラーメッセージが空の場合
        """
        is_valid = info.data.get("is_valid", True)
        if not is_valid and not v:
            raise ValueError("Error message is required when validation fails")
        return v


class FormatType(IntEnum):
    """フォーマットタイプを表す列挙型。

    テンプレート出力のフォーマット方法を定義します。各タイプは以下の処理を行います：
    - RAW: 生のテキストをそのまま出力
    - REMOVE_SPACES: 連続する空白行を1行に圧縮
    - NORMALIZE_BREAKS: 3つ以上の連続する改行を2つに圧縮
    - REMOVE_AND_NORMALIZE: 空白行を削除し、改行を正規化
    - COMPACT: 最も圧縮された形式（全ての空白行を削除）

    Attributes:
        RAW (int): 生のテキスト (= 0)
        REMOVE_SPACES (int): 空白行を削除 (= 1)
        NORMALIZE_BREAKS (int): 改行を正規化 (= 2)
        REMOVE_AND_NORMALIZE (int): 空白行を削除し、改行を正規化 (= 3)
        COMPACT (int): 最も圧縮されたフォーマット (= 4)
    """

    RAW = 0
    REMOVE_SPACES = 1
    NORMALIZE_BREAKS = 2
    REMOVE_AND_NORMALIZE = 3
    COMPACT = 4


class TemplateValidationError(Exception):
    """テンプレート検証時に発生するエラー。

    テンプレートの構文やセキュリティ上の問題を示します。
    以下の場合に発生します：
    - 禁止されたタグや属性の使用
    - 再帰的な構造の検出
    - メモリ使用量の超過
    - UTF-8デコードエラー
    """

    pass


class TemplateContent(BaseModel):
    """テンプレートの内容を表すモデル。

    テンプレートの内容とファイルサイズを保持し、両者の整合性を検証します。
    UTF-8エンコーディングを前提とし、コンテンツのバイトサイズとファイルサイズが
    一致することを確認します。

    Attributes:
        content (str): テンプレートの内容
        file_size (int): ファイルサイズ（バイト単位）

    Raises:
        ValueError: コンテンツのサイズがファイルサイズと一致しない場合
    """

    content: Annotated[
        str,
        Field(description="テンプレートの内容"),
        BeforeValidator(lambda x: str(x) if x else ""),
    ]
    file_size: Annotated[
        int,
        Field(description="ファイルサイズ（バイト単位）"),
        BeforeValidator(lambda x: int(x)),
        AfterValidator(lambda x: x if x >= 0 else 0),
    ]

    model_config = ConfigDict(validate_assignment=True)

    @model_validator(mode="after")
    def validate_content_size(self) -> Self:
        """コンテンツのサイズがファイルサイズと一致することを検証します。

        Returns:
            Self: 検証に成功した場合、自身を返します

        Raises:
            ValueError: コンテンツのサイズがファイルサイズと一致しない場合
        """
        if len(self.content.encode("utf-8")) != self.file_size:
            raise ValueError("Content size does not match file size")
        return self


class ValidationState:
    """テンプレートの検証状態を表すクラス。"""

    def __init__(self) -> None:
        """初期化。"""
        self._is_valid: bool = True
        self._error_message: Optional[str] = None
        self._content: Optional[str] = None

    @property
    def is_valid(self) -> bool:
        """検証が成功したかどうかを返す。"""
        return self._is_valid

    @property
    def error_message(self) -> Optional[str]:
        """エラーメッセージを返す。

        Returns:
            Optional[str]: エラーメッセージ（エラーがない場合はNone）
        """
        return self._error_message if self._error_message else None

    @property
    def content(self) -> Optional[str]:
        """テンプレート内容を返す。"""
        return self._content

    def set_error(self, message: Optional[str]) -> None:
        """エラーメッセージを設定する。

        Args:
            message: エラーメッセージ（Noneの場合は空文字列に変換）
        """
        self._is_valid = False
        self._error_message = str(message) if message is not None else ""

    def set_content(self, content: str) -> None:
        """テンプレート内容を設定する。

        Args:
            content: テンプレート内容
        """
        self._content = content

    def reset(self) -> None:
        """状態をリセットする。"""
        self._is_valid = True
        self._error_message = None
        self._content = None


class TemplateSecurityValidator:
    """テンプレートのセキュリティ検証を行うクラス。

    テンプレートの構文、セキュリティ、および構造を検証します。
    検証は以下の2段階で実行されます：
    1. 静的解析（初期検証）
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
        MAX_RANGE_SIZE (int): rangeで許容される最大サイズ（100,000）
        RESTRICTED_TAGS (Set[str]): 禁止されたタグのセット
        RESTRICTED_ATTRIBUTES (Set[str]): 禁止された属性のセット
    """

    # 許可されない属性のリスト（静的検証）
    RESTRICTED_ATTRIBUTES: ClassVar[set[str]] = {
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

    # 許可されないタグのリスト（静的検証）
    RESTRICTED_TAGS: ClassVar[set[str]] = {"macro", "include", "import", "extends"}

    # 最大range値
    MAX_RANGE_SIZE: ClassVar[int] = 100000

    def validate_template(self, ast: nodes.Template) -> ValidationState:
        """テンプレートのセキュリティを検証する。

        Args:
            ast: 検証対象のテンプレートAST

        Returns:
            ValidationState: 検証結果
        """
        validation_state = ValidationState()

        # 1. 禁止タグの検証
        if not self._validate_restricted_tags(ast, validation_state):
            return validation_state

        # 2. 属性アクセスの検証
        if not self._validate_restricted_attributes(ast, validation_state):
            return validation_state

        # 3. ループ範囲の検証（リテラル値のみ）
        if not self._validate_loop_range(ast, validation_state):
            return validation_state

        return validation_state

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
            if tag_name in self.RESTRICTED_TAGS:
                validation_state.set_error(f"Template security error: '{tag_name}' tag is not allowed")
                return False
        return True

    def _validate_restricted_attributes(self, ast: nodes.Template, validation_state: ValidationState) -> bool:
        """禁止属性を検証する。

        Args:
            ast: 検証対象のAST
            validation_state: 検証状態

        Returns:
            bool: 検証が成功したかどうか
        """
        for node in ast.find_all(nodes.Getattr):
            if isinstance(node.node, nodes.Name):
                attr_name = node.node.name
                if attr_name in self.RESTRICTED_ATTRIBUTES:
                    validation_state.set_error(f"Template security error: access to '{attr_name}' is restricted")
                    return False
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
            if isinstance(node.iter, nodes.Call) and isinstance(node.iter.node, nodes.Name) and node.iter.node.name == "range":
                try:
                    args = node.iter.args
                    if len(args) == 1:  # range(stop)
                        stop = self._evaluate_literal(args[0])
                        if stop > self.MAX_RANGE_SIZE:
                            validation_state.set_error(
                                f"Template security error: loop range exceeds maximum limit of {self.MAX_RANGE_SIZE}"
                            )
                            return False
                    elif len(args) >= 2:  # range(start, stop[, step])
                        start = self._evaluate_literal(args[0])
                        stop = self._evaluate_literal(args[1])

                        if len(args) > 2:  # step is provided
                            step = self._evaluate_literal(args[2])
                            if step == 0:
                                validation_state.set_error("Template security error: loop step cannot be zero")
                                return False
                        else:
                            step = 1

                        # Calculate the number of iterations
                        if step > 0:
                            iterations = (stop - start + step - 1) // step
                        else:
                            iterations = (start - stop - step - 1) // -step
                        if iterations > self.MAX_RANGE_SIZE:
                            validation_state.set_error(
                                f"Template security error: loop range exceeds maximum limit of {self.MAX_RANGE_SIZE}"
                            )
                            return False
                except (TypeError, ValueError):
                    # 動的な値の場合は、ランタイムでの検証に委ねる
                    continue
        return True

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


class ContextValidator(BaseModel):
    """コンテキストデータを検証するバリデータ。

    テンプレートに適用するコンテキストデータの構造と型を検証します。
    以下の検証を行います：
    1. コンテキストが辞書型であることの確認
    2. フォーマットタイプの有効性チェック
    3. 未定義変数の厳密チェック設定の管理

    Attributes:
        format_type (int): フォーマットタイプ（0-4の整数）
        context (Dict[str, Any]): コンテキストデータ
        is_strict_undefined (bool): 未定義変数を厳密にチェックするかどうか

    Raises:
        ValueError: コンテキストの構造が無効な場合
    """

    format_type: Annotated[
        int,
        Field(description="フォーマットタイプ（0-4の整数）"),
        BeforeValidator(lambda x: int(x)),
        AfterValidator(lambda x: x if 0 <= x <= 4 else 0),
    ]
    context: Annotated[
        Dict[str, Any],
        Field(description="コンテキストデータ"),
        BeforeValidator(lambda x: dict(x) if x else {}),
    ]
    is_strict_undefined: Annotated[
        bool,
        Field(default=True, description="未定義変数を厳密にチェックするかどうか"),
        BeforeValidator(lambda x: bool(x)),
    ]

    @model_validator(mode="after")
    def validate_context_structure(self) -> Self:
        """コンテキストの構造を検証します。

        以下の条件を確認します：
        1. contextが辞書型であること
        2. format_typeが0から4の範囲内であること

        Returns:
            Self: 検証に成功した場合、自身を返します

        Raises:
            ValueError: コンテキストの構造が無効な場合
        """
        if not isinstance(self.context, dict):
            raise ValueError("Context must be a dictionary")

        if self.format_type not in range(5):
            raise ValueError("Unsupported format type")

        return self


class ContentFormatter:
    """テンプレート出力のフォーマット処理を行うクラス。

    フォーマットタイプ:
        0: 空白行を保持
        1: 連続する空白行を1行に圧縮
        2: 空白行を保持（タイプ0と同じ）
        3: 連続する空白行を1行に圧縮（タイプ1と同じ）
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
        if format_type == 0 or format_type == 2:
            return content
        elif format_type == 1 or format_type == 3:
            return self._compress_whitespace(content)
        elif format_type == 4:
            return self._remove_all_whitespace(content)
        else:
            raise ValueError("Unsupported format type")

    def _compress_whitespace(self, content: str) -> str:
        """連続する空白行を1行に圧縮する。

        Args:
            content: 圧縮対象の文字列

        Returns:
            圧縮後の文字列
        """
        lines = content.splitlines(True)
        result = []
        prev_empty = False

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
        lines = content.splitlines(True)
        result = [line for line in lines if line.strip()]
        return "".join(result)


class DocumentRender:
    """テンプレートのレンダリングと検証を行うクラス。

    このクラスは、テンプレートファイルの検証、レンダリング、フォーマット処理を提供します。
    検証は以下の2段階で実行されます：
    1. 初期検証（静的解析）
       - ファイルサイズの検証
       - エンコーディングの検証
       - 禁止タグのチェック
       - 禁止属性のチェック
       - リテラル値のループ範囲チェック
    2. ランタイム検証
       - 再帰的構造の検出
       - ゼロ除算の検証

    Attributes:
        MAX_FILE_SIZE (int): 許可される最大ファイルサイズ（バイト）
        MAX_MEMORY_SIZE (int): 許可される最大メモリ使用量（バイト）
    """

    MAX_FILE_SIZE: ClassVar[int] = 1024 * 1024  # 1MB
    MAX_MEMORY_SIZE: ClassVar[int] = 1024 * 1024 * 10  # 10MB

    def __init__(self, template_file: BytesIO) -> None:
        """DocumentRenderインスタンスを初期化する。

        Args:
            template_file: テンプレートファイル（BytesIO）

        Note:
            初期検証に失敗した場合、エラー状態を保持します。
            エラー状態は is_valid_template と error_message プロパティで確認できます。
        """
        if not isinstance(template_file, BytesIO):
            self._validation_state = ValidationState()
            self._validation_state.set_error("Template file must be a BytesIO object")
            return

        self._template_file = template_file
        self._template_content: Optional[str] = None
        self._render_content: Optional[str] = None
        self._is_strict_undefined: bool = True
        self._formatter = ContentFormatter()
        self._security_validator = TemplateSecurityValidator()
        self._validation_state = ValidationState()
        self._initial_validation_passed = False
        self._ast: Optional[nodes.Template] = None

        # 初期検証を実行
        self._validate_template_file()

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
            Optional[str]: エラーメッセージ（エラーがない場合はNone）
        """
        return self._validation_state.error_message

    @property
    def render_content(self) -> Optional[str]:
        """レンダリング結果を返す。

        Returns:
            Optional[str]: レンダリング結果（レンダリングが行われていない場合はNone）
        """
        return self._render_content

    def _validate_template_file(self) -> bool:
        """テンプレートファイルの検証を行う。

        以下の順序で検証を実行します：
        1. ファイルサイズの検証（最も軽量）
        2. エンコーディングの検証
        3. 構文の検証
        4. セキュリティチェック（静的検証のみ）

        Returns:
            bool: 検証が成功したかどうか
        """
        self._validation_state.reset()

        # 1. ファイルサイズの検証（最も軽量）
        if not self._validate_file_size():
            return False

        # 2. エンコーディングの検証
        template_content = self._validate_encoding()
        if template_content is None:
            return False

        # 3. 構文の検証
        ast = self._validate_syntax(template_content)
        if ast is None:
            return False

        # 4. セキュリティチェック（静的検証のみ）
        security_result = self._security_validator.validate_template(ast)
        if not security_result.is_valid:
            self._validation_state.set_error(security_result.error_message)
            return False

        # 検証に成功した場合、状態を更新
        self._template_content = template_content
        self._ast = ast
        self._initial_validation_passed = True
        return True

    def _validate_file_size(self) -> bool:
        """ファイルサイズを検証する。

        Returns:
            bool: ファイルサイズが制限内の場合はTrue
        """
        try:
            current_pos = self._template_file.tell()
            self._template_file.seek(0, 2)  # ファイルの末尾に移動
            file_size = self._template_file.tell()
            self._template_file.seek(current_pos)  # 元の位置に戻す

            if file_size > self.MAX_FILE_SIZE:
                self._validation_state.set_error(f"Template file size exceeds maximum limit of {self.MAX_FILE_SIZE} bytes")
                return False
            return True
        except Exception as e:
            self._validation_state.set_error(f"File size validation error: {e!s}")
            return False

    def _validate_encoding(self) -> Optional[str]:
        """エンコーディングを検証する。

        Returns:
            Optional[str]: デコードされたテンプレート内容（エラーの場合はNone）
        """
        try:
            current_pos = self._template_file.tell()
            content = self._template_file.read()
            self._template_file.seek(current_pos)  # 元の位置に戻す

            # バイナリデータのチェック
            if b"\x00" in content:
                self._validation_state.set_error("Template file contains invalid binary data")
                return None

            # UTF-8デコードのチェック
            try:
                return content.decode("utf-8", errors="strict")
            except UnicodeDecodeError:
                self._validation_state.set_error("Template file contains invalid UTF-8 bytes")
                return None

        except Exception as e:
            self._validation_state.set_error(f"Encoding validation error: {e!s}")
            return None

    def _validate_syntax(self, template_content: str) -> Optional[nodes.Template]:
        """テンプレートの構文を検証する。

        Args:
            template_content: テンプレートの内容

        Returns:
            Optional[nodes.Template]: 構文解析結果（エラーの場合はNone）
        """
        try:
            env = self._create_environment()
            return env.parse(template_content)
        except jinja2.TemplateSyntaxError as e:
            self._validation_state.set_error(str(e))
            return None
        except Exception as e:
            self._validation_state.set_error(f"Template syntax error: {e!s}")
            return None

    def _validate_security(self, ast: nodes.Template) -> bool:
        """テンプレートのセキュリティを検証する。

        Args:
            ast: テンプレートのAST

        Returns:
            bool: セキュリティチェックに合格した場合はTrue
        """
        result = self._security_validator.validate_template(ast)
        if not result.is_valid:
            self._validation_state.set_error(result.error_message)
            return False

        # HTMLインジェクション対策の追加検証
        try:
            for node in ast.find_all((nodes.Filter,)):
                if node.name in {"safe", "html_safe"}:
                    # safeフィルターが使用されている場合、内容を検証
                    if not self._validate_safe_content(node):
                        self._validation_state.set_error("Template security error: unsafe HTML content detected")
                        return False
        except Exception as e:
            self._validation_state.set_error(f"Template security error: {e!s}")
            return False

        return True

    def _validate_safe_content(self, node: nodes.Filter) -> bool:
        """safeフィルターで使用されるコンテンツの安全性を検証する。

        Args:
            node: フィルターノード

        Returns:
            bool: コンテンツが安全な場合はTrue
        """
        try:
            if isinstance(node.node, nodes.Const):
                # 定数の場合、内容を直接検証
                content = str(node.node.value)
                self._html_safe_filter(content)  # 安全性チェックを実行
            return True
        except ValueError:
            return False
        except Exception:
            return False

    def apply_context(self, context: Dict[str, Any], format_type: int, is_strict_undefined: bool = True) -> bool:
        """テンプレートにコンテキストを適用する。

        Args:
            context: テンプレートに適用するコンテキスト
            format_type: フォーマットタイプ（0-4の整数）
            is_strict_undefined: 未定義変数を厳密にチェックするかどうか

        Returns:
            bool: コンテキストの適用が成功したかどうか
        """
        # 初期検証が失敗している場合は、そのエラーを維持
        if not self._initial_validation_passed:
            return False

        if not self._validate_format_type(format_type):
            self._validation_state.set_error("Unsupported format type")
            return False

        try:
            if self._template_content is None:
                self._validation_state.set_error("Template content is not loaded")
                return False

            if self._ast is None:
                self._validation_state.set_error("AST is not available")
                return False

            # is_strict_undefinedの値を更新
            self._is_strict_undefined = is_strict_undefined

            # ランタイム検証の実行（再帰的構造の検出を含む）
            if not self._runtime_validations(self._ast, context):
                return False

            # テンプレートのレンダリング
            env = self._create_environment()
            template = env.from_string(self._template_content)

            try:
                rendered = template.render(**context)
            except Exception as e:
                # レンダリング時のエラーを適切に処理
                if "recursive structure detected" in str(e):
                    self._validation_state.set_error("Template security error: recursive structure detected")
                    return False
                raise

            # メモリ使用量の検証
            if not self._validate_memory_usage(rendered):
                return False

            # フォーマット処理
            if not self._format_content(rendered, format_type):
                return False

            return True

        except jinja2.UndefinedError as e:
            self._validation_state.set_error(str(e))
            return False
        except jinja2.TemplateError as e:
            self._validation_state.set_error(str(e))
            return False
        except Exception as e:
            self._validation_state.set_error(f"Template rendering error: {e!s}")
            return False

    def _runtime_validations(self, ast: Union[nodes.Template, jinja2.Template], context: Dict[str, Any]) -> bool:
        """ランタイム検証を実行する。

        Args:
            ast: 検証対象のテンプレートAST
            context: テンプレートに適用するコンテキスト

        Returns:
            bool: 検証が成功したかどうか
        """
        try:
            if ast is None:
                self._validation_state.set_error("AST is not available")
                return False

            # ASTの型を確認
            if isinstance(ast, jinja2.Template) and self._template_content is not None:
                ast = ast.environment.parse(self._template_content)

            if not isinstance(ast, nodes.Template):
                self._validation_state.set_error("Invalid AST type")
                return False

            # 1. 再帰的構造の検出
            # 変数の割り当てを追跡するための辞書
            assignments: Dict[str, Any] = {}
            for node in ast.find_all((nodes.Assign, nodes.For, nodes.Call)):
                if isinstance(node, nodes.Assign) and isinstance(node.target, nodes.Name):
                    target_name = node.target.name
                    try:
                        # 変数の値を評価
                        value = self._evaluate_expression(node.node, context, assignments)
                        assignments[target_name] = value
                    except Exception as e:
                        if "recursive structure detected" in str(e):
                            self._validation_state.set_error("Template security error: recursive structure detected")
                            return False
                        continue
                elif isinstance(node, nodes.For):
                    # forループ内での再帰的構造の検出
                    if isinstance(node.iter, nodes.Name):
                        iter_name = node.iter.name
                        if iter_name in assignments:
                            try:
                                self._evaluate_expression(node.iter, context, assignments)
                            except Exception as e:
                                if "recursive structure detected" in str(e):
                                    self._validation_state.set_error("Template security error: recursive structure detected")
                                    return False
                elif isinstance(node, nodes.Call):
                    # メソッド呼び出しの検証
                    try:
                        self._evaluate_expression(node, context, assignments)
                    except Exception as e:
                        if "recursive structure detected" in str(e):
                            self._validation_state.set_error("Template security error: recursive structure detected")
                            return False
                        continue

            # 2. ゼロ除算の検証
            for node in ast.find_all(nodes.Div):
                try:
                    right_value = self._evaluate_expression(node.right, context, assignments)
                    if right_value == 0:
                        self._validation_state.set_error("Template security error: division by zero is not allowed")
                        return False
                except Exception:
                    continue

            return True

        except Exception as e:
            self._validation_state.set_error(f"Runtime validation error: {e!s}")
            return False

    def _evaluate_expression(self, node: nodes.Node, context: Dict[str, Any], assignments: Dict[str, Any]) -> Any:
        """式を評価する。

        Args:
            node: 評価対象のノード
            context: テンプレートに適用するコンテキスト
            assignments: 変数の割り当て状態

        Returns:
            Any: 評価結果

        Raises:
            ValueError: 再帰的構造が検出された場合
            TypeError: 式の評価に失敗した場合
        """
        try:
            if isinstance(node, nodes.Name):
                # 変数名の評価
                name = node.name
                if name in assignments:
                    return assignments[name]
                elif name in context:
                    return context[name]
                elif self._is_strict_undefined:
                    raise TypeError(f"'{name}' is undefined")
                return None

            elif isinstance(node, nodes.Const):
                # 定数の評価
                return node.value

            elif isinstance(node, nodes.List):
                # リストの評価
                result = [self._evaluate_expression(item, context, assignments) for item in node.items]
                if self._is_recursive_structure(result):
                    raise ValueError("recursive structure detected")
                return result

            elif isinstance(node, nodes.Dict):
                # 辞書の評価 - ノードのキーと値を個別に評価
                result = {}
                for pair in node.items:
                    key = self._evaluate_expression(pair.key, context, assignments)
                    value = self._evaluate_expression(pair.value, context, assignments)
                    result[key] = value
                if self._is_recursive_structure(result):
                    raise ValueError("recursive structure detected")
                return result

            elif isinstance(node, nodes.Call):
                # メソッド呼び出しの評価
                if isinstance(node.node, nodes.Getattr):
                    # オブジェクトのメソッド呼び出し
                    obj = self._evaluate_expression(node.node.node, context, assignments)
                    method_name = node.node.attr

                    # リストのメソッド呼び出しを検証
                    if isinstance(obj, list) and method_name in ["append", "extend"]:
                        args = [self._evaluate_expression(arg, context, assignments) for arg in node.args]
                        # 再帰的構造のチェック
                        if any(arg is obj or self._is_recursive_structure(arg) for arg in args):
                            raise ValueError("recursive structure detected")
                        # メソッドの実行をシミュレート
                        new_list = obj.copy()
                        if method_name == "append":
                            new_list.append(args[0])
                        elif method_name == "extend":
                            new_list.extend(args[0])
                        if self._is_recursive_structure(new_list):
                            raise ValueError("recursive structure detected")
                        return new_list

            elif isinstance(node, nodes.Getattr):
                # 属性アクセスの評価
                obj = self._evaluate_expression(node.node, context, assignments)
                if obj is None:
                    if self._is_strict_undefined:
                        raise TypeError(f"Cannot access attribute '{node.attr}' of None")
                    return None
                return getattr(obj, node.attr)

            elif isinstance(node, nodes.BinExpr):
                # 二項演算の評価
                left = self._evaluate_expression(node.left, context, assignments)
                right = self._evaluate_expression(node.right, context, assignments)
                if isinstance(node, nodes.Div) and right == 0:
                    raise ValueError("division by zero is not allowed")
                return self._evaluate_binary_operation(node, left, right)

            raise TypeError("Cannot evaluate expression")
        except Exception as e:
            if "recursive structure detected" in str(e):
                raise ValueError("recursive structure detected") from e
            raise TypeError("Cannot evaluate expression") from e

    def _evaluate_binary_operation(self, node: nodes.BinExpr, left: Any, right: Any) -> Any:
        """二項演算を評価する。

        Args:
            node: 二項演算ノード
            left: 左辺の値
            right: 右辺の値

        Returns:
            Any: 評価結果

        Raises:
            TypeError: サポートされていない演算子の場合
        """
        if isinstance(node, nodes.Add):
            return left + right
        elif isinstance(node, nodes.Sub):
            return left - right
        elif isinstance(node, nodes.Mul):
            return left * right
        elif isinstance(node, nodes.Div):
            return left / right
        elif isinstance(node, nodes.FloorDiv):
            return left // right
        elif isinstance(node, nodes.Mod):
            return left % right
        elif isinstance(node, nodes.Pow):
            return left**right
        raise TypeError(f"Unsupported binary operator: {type(node).__name__}")

    def _is_recursive_structure(self, value: Any) -> bool:
        """値が再帰的構造かどうかを判定する。

        Args:
            value: チェック対象の値

        Returns:
            bool: 再帰的構造の場合はTrue
        """
        try:
            # 循環参照を検出するための集合
            seen = set()

            def check_recursive(v: Any, depth: int = 0) -> bool:
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
                            result = any(check_recursive(item, depth + 1) for item in v)
                        else:  # dict
                            result = any(check_recursive(item, depth + 1) for item in v.values())
                        if result:
                            return True
                    finally:
                        seen.remove(obj_id)

                return False

            return check_recursive(value)
        except Exception:
            return False

    def _validate_memory_usage(self, content: str) -> bool:
        """メモリ使用量を検証する。

        Args:
            content: 検証対象のコンテンツ

        Returns:
            bool: メモリ使用量が制限内の場合はTrue
        """
        try:
            # バイナリデータの検出
            if "\x00" in content:
                self._validation_state.set_error("Content contains invalid binary data")
                return False

            # メモリ使用量の検証
            content_size = len(content.encode("utf-8"))
            if content_size > self.MAX_MEMORY_SIZE:
                self._validation_state.set_error(f"Memory consumption exceeds maximum limit of {self.MAX_MEMORY_SIZE} bytes")
                return False
            return True
        except UnicodeEncodeError:
            # UTF-8エンコードに失敗した場合は、文字数で概算
            if len(content) * 4 > self.MAX_MEMORY_SIZE:  # 最大4バイト/文字と仮定
                self._validation_state.set_error(f"Memory consumption exceeds maximum limit of {self.MAX_MEMORY_SIZE} bytes")
                return False
            return True
        except Exception as e:
            self._validation_state.set_error(f"Memory usage validation error: {e!s}")
            return False

    def _validate_format_type(self, format_type: int) -> bool:
        """フォーマットタイプを検証する。

        Args:
            format_type: フォーマットタイプ（0-4の整数）

        Returns:
            bool: フォーマットタイプが有効な場合はTrue
        """
        return isinstance(format_type, int) and 0 <= format_type <= 4

    def _render_template(self, template_content: str, context: Dict[str, Any], is_strict_undefined: bool) -> Optional[str]:
        """テンプレートをレンダリングする。

        Args:
            template_content: テンプレートの内容
            context: テンプレートに適用するコンテキスト
            is_strict_undefined: 未定義変数を厳密にチェックするかどうか

        Returns:
            Optional[str]: レンダリング結果（エラーの場合はNone）
        """
        if not template_content:
            self._validation_state.set_error("Template content is not loaded")
            return None

        try:
            env = self._create_environment()
            env.undefined = StrictUndefined if is_strict_undefined else Undefined
            template = env.from_string(template_content)

            # ランタイム検証の実行
            self._runtime_validations(template, context)
            if not self._validation_state.is_valid:
                return None

            rendered = template.render(**context)
            return rendered

        except jinja2.UndefinedError as e:
            self._validation_state.set_error(str(e))
            return None
        except jinja2.TemplateError as e:
            self._validation_state.set_error(str(e))
            return None
        except Exception as e:
            self._validation_state.set_error(f"Template rendering error: {e!s}")
            return None

    def _format_content(self, content: str, format_type: int) -> bool:
        """レンダリング結果をフォーマットする。

        Args:
            content: フォーマット対象のコンテンツ
            format_type: フォーマットタイプ（0-4の整数）

        Returns:
            bool: フォーマットが成功したかどうか
        """
        try:
            self._render_content = self._formatter.format(content, format_type)
            return True
        except Exception as e:
            self._validation_state.set_error(f"Content formatting error: {e!s}")
            return False

    def _create_environment(self) -> Environment:
        """Jinja2環境を作成する。

        カスタムフィルターやセキュリティ設定を含む環境を作成します。
        デフォルトでHTMLエスケープを有効化し、安全性を確保します。

        Returns:
            Environment: 設定済みのJinja2環境
        """

        class CustomUndefined(Undefined):
            """非strictモード用のカスタムUndefinedクラス。

            未定義変数に対して以下の動作を提供します：
            - 属性アクセス: 空文字列を返す
            - 文字列化: 空文字列を返す
            - 演算: 空文字列を返す
            - 比較: False を返す
            """

            def __init__(self, *args: Any, **kwargs: Any) -> None:
                super().__init__(*args, **kwargs)

            def __getattr__(self, name: str) -> "CustomUndefined":
                return self

            def __str__(self) -> str:
                return ""

            def __html__(self) -> str:
                return ""

            def __bool__(self) -> bool:
                return False

            def __eq__(self, other: Any) -> bool:
                return isinstance(other, (CustomUndefined, Undefined))

            # 算術演算子のサポート
            def __add__(self, other: Any) -> str:
                return ""

            def __radd__(self, other: Any) -> str:
                return ""

            def __sub__(self, other: Any) -> str:
                return ""

            def __rsub__(self, other: Any) -> str:
                return ""

            def __mul__(self, other: Any) -> str:
                return ""

            def __rmul__(self, other: Any) -> str:
                return ""

            def __div__(self, other: Any) -> str:
                return ""

            def __rdiv__(self, other: Any) -> str:
                return ""

            def __truediv__(self, other: Any) -> str:
                return ""

            def __rtruediv__(self, other: Any) -> str:
                return ""

            def __floordiv__(self, other: Any) -> str:
                return ""

            def __rfloordiv__(self, other: Any) -> str:
                return ""

            def __mod__(self, other: Any) -> str:
                return ""

            def __rmod__(self, other: Any) -> str:
                return ""

            def __call__(self, *args: Any, **kwargs: Any) -> "CustomUndefined":
                return self

        env = Environment(
            autoescape=True,  # HTMLエスケープをデフォルトで有効化
            undefined=StrictUndefined if self._is_strict_undefined else CustomUndefined,
            extensions=["jinja2.ext.do"],  # 'do'拡張を有効化
        )

        # カスタムフィルターの登録
        env.filters["date"] = self._date_filter
        env.filters["safe"] = self._html_safe_filter  # safeフィルターを安全な実装に変更
        env.filters["html_safe"] = self._html_safe_filter

        return env

    def _date_filter(self, value: Union[str, datetime], format_str: str = "%Y-%m-%d") -> str:
        """日付文字列をフォーマットする。

        Args:
            value: 日付文字列または datetime オブジェクト
            format_str: 出力フォーマット

        Returns:
            フォーマットされた日付文字列

        Raises:
            ValueError: 日付の解析に失敗した場合
        """
        if value is None:
            raise ValueError("Date value cannot be None")

        try:
            if isinstance(value, str):
                # ISO形式の日付文字列をパース
                dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            elif isinstance(value, datetime):
                dt = value
            else:
                raise ValueError("Invalid date format")

            return dt.strftime(format_str)

        except (ValueError, TypeError) as e:
            raise ValueError("Invalid date format") from e

    def _html_safe_filter(self, value: str) -> Markup:
        """HTMLをエスケープせずに出力する。"""
        return HTMLSafetyValidator.create_safe_markup(value)


class HTMLSafetyValidator:
    """HTMLの安全性を検証するクラス。"""

    # 安全でないHTMLパターン
    UNSAFE_PATTERNS: ClassVar[list[str]] = [
        r"<script",  # スクリプトタグ
        r"javascript:",  # JavaScriptプロトコル
        r"data:",  # データURIスキーム
        r"vbscript:",  # VBScriptプロトコル
        r"on\w+\s*=",  # イベントハンドラ属性
    ]

    @staticmethod
    def validate_html_content(value: str) -> bool:
        """HTMLコンテンツの安全性を検証する。

        Args:
            value: 検証対象のHTML文字列

        Returns:
            bool: HTMLが安全な場合はTrue

        Raises:
            ValueError: 安全でないHTML要素が含まれる場合
        """
        if not isinstance(value, str):
            raise ValueError("HTML content must be a string")

        # 安全でないHTMLパターンをチェック
        for pattern in HTMLSafetyValidator.UNSAFE_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                return False
        return True

    @staticmethod
    def create_safe_markup(value: str) -> Markup:
        """安全なMarkupオブジェクトを作成する。

        Args:
            value: HTML文字列

        Returns:
            Markup: 安全なMarkupオブジェクト

        Raises:
            ValueError: 安全でないHTML要素が含まれる場合
        """
        if not HTMLSafetyValidator.validate_html_content(value):
            raise ValueError("HTML content contains potentially unsafe elements")

        # 安全性が確認されたHTMLのみをMarkupとして返す
        return Markup("").join(value)
