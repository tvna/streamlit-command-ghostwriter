"""テンプレートのレンダリングと検証を行うモジュール。

このモジュールは、テンプレートファイルの検証、レンダリング、フォーマットを行う機能を提供します。
主な機能:
- テンプレートファイルの構文とセキュリティの検証
- コンテキストデータの適用とレンダリング
- レンダリング結果のフォーマット処理

クラス階層：
- DocumentRender: メインのレンダリングクラス
  - FileValidator: ファイルサイズの検証
  - ContentFormatter: フォーマット処理
  - TemplateSecurityValidator: テンプレートのセキュリティ検証

検証プロセス:
1. ファイルサイズの検証
   - FileValidatorによるサイズ制限のチェック
   - ファイルポインタの位置を保持したまま検証

2. テンプレートの検証
   - 構文チェック
   - セキュリティチェック（禁止タグ、属性）
   - 再帰的構造の検出

3. コンテキストの適用
   - 変数の型チェック
   - 未定義変数の検証
   - メモリ使用量の制限

4. 出力フォーマット
   - 空白行の処理（保持/圧縮/削除）
   - 改行の正規化

典型的な使用方法:
```python
with open('template.txt', 'rb') as f:
    template_file = BytesIO(f.read())
    renderer = DocumentRender(template_file)
    if renderer.is_valid_template:
        renderer.apply_context({'name': 'World'}, format_type=2)  # NORMALIZE_BREAKS
        result = renderer.render_content
```
"""

from datetime import datetime
from io import BytesIO
from typing import (
    Any,
    Callable,
    ClassVar,
    Dict,
    Optional,
    TypeVar,
    Union,
)

import jinja2
from jinja2 import Environment, nodes
from jinja2.runtime import StrictUndefined, Undefined

from features.validate_template import TemplateSecurityValidator, ValidationState  # type: ignore
from features.validate_uploaded_file import FileValidator  # type: ignore


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

    テンプレートファイルの検証、レンダリング、フォーマットを一貫して処理します。
    セキュリティチェック、メモリ使用量の制限、出力フォーマットの制御を提供します。

    Attributes:
        MAX_FILE_SIZE: テンプレートファイルの最大サイズ [バイト]
        MAX_MEMORY_SIZE: レンダリング結果の最大メモリ使用量 [バイト]
    """

    MAX_FILE_SIZE: ClassVar[int] = 30 * 1024 * 1024  # 30MB
    MAX_MEMORY_SIZE: ClassVar[int] = 150 * 1024 * 1024  # 150MB

    def __init__(self, template_file: BytesIO) -> None:
        """DocumentRenderインスタンスを初期化する。

        Args:
            template_file: テンプレートファイル（BytesIO）

        Note:
            初期検証に失敗した場合、エラー状態を保持します。
            エラー状態は is_valid_template と error_message プロパティで確認できます。
        """
        self._validation_state = ValidationState()
        self._file_validator = FileValidator(max_size_bytes=self.MAX_FILE_SIZE)

        try:
            self._file_validator.validate_size(template_file)
        except ValueError as e:
            self._validation_state.set_error(str(e))
            self._initial_validation_passed = False
            return
        except IOError as e:
            self._validation_state.set_error(f"Failed to validate template file: {e!s}")
            self._initial_validation_passed = False
            return

        self._template_file = template_file
        self._template_content: Optional[str] = None
        self._render_content: Optional[str] = None
        self._is_strict_undefined: bool = True
        self._formatter = ContentFormatter()
        self._security_validator = TemplateSecurityValidator()

        self._ast: Optional[nodes.Template] = None

        # 初期検証を実行
        template_content, ast = self._security_validator.validate_template_file(self._template_file, self._validation_state)
        if template_content is None or ast is None:
            self._initial_validation_passed = False
        else:
            self._initial_validation_passed = True
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

    def _validate_file_size(self) -> bool:
        """ファイルサイズを検証する。

        テンプレートファイルのサイズが制限値を超えていないかチェックします。
        ファイルポインタの位置を保持したまま検証を行います。

        Returns:
            ファイルサイズが制限内の場合はTrue
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

    def _validate_preconditions(self, context: Dict[str, Any], format_type: int) -> bool:
        """前提条件を検証する。

        レンダリング処理の前提条件が満たされているかチェックします。
        - 初期検証が完了していること
        - フォーマットタイプが有効であること
        - テンプレート内容とASTが利用可能であること

        Args:
            context: テンプレートに適用するコンテキスト
            format_type: フォーマットタイプ [0-4の整数]

        Returns:
            前提条件を満たす場合はTrue
        """
        if not self._initial_validation_passed:
            return False

        if not self._validate_format_type(format_type):
            self._validation_state.set_error("Unsupported format type")
            return False

        if self._template_content is None:
            self._validation_state.set_error("Template content is not loaded")
            return False

        if self._ast is None:
            self._validation_state.set_error("AST is not available")
            return False

        return True

    def _validate_format_type(self, format_type: int) -> bool:
        """フォーマットタイプを検証する。

        指定されたフォーマットタイプが有効な範囲内かチェックします。

        Args:
            format_type: フォーマットタイプ [0-4の整数]

        Returns:
            フォーマットタイプが有効な場合はTrue
        """
        return isinstance(format_type, int) and 0 <= format_type <= 4

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
            self._validation_state.set_error(str(e))
        elif isinstance(e, jinja2.TemplateError):
            self._validation_state.set_error(str(e))
        else:
            self._validation_state.set_error(f"Template rendering error: {e!s}")
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
        if not self._validate_preconditions(context, format_type):
            return False

        try:
            self._is_strict_undefined = is_strict_undefined

            # ランタイム検証の実行（再帰的構造の検出を含む）
            if self._ast is None:
                self._validation_state.set_error("AST is not available")
                return False

            security_result = self._security_validator.validate_runtime_security(self._ast, context)
            if not security_result.is_valid:
                self._validation_state.set_error(security_result.error_message)
                return False

            # テンプレートのレンダリング
            env = self._create_environment()
            if self._template_content is None:
                self._validation_state.set_error("Template content is not loaded")
                return False

            template = env.from_string(self._template_content)

            try:
                rendered = template.render(**context)
            except Exception as e:
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

        except Exception as e:
            return self._handle_rendering_error(e)

    def _validate_memory_usage(self, content: str) -> bool:
        """メモリ使用量を検証する。

        レンダリング結果のメモリ使用量が制限値を超えていないかチェックします。
        バイナリデータの検出とUTF-8エンコードのサイズ計算を行います。

        Args:
            content: 検証対象のコンテンツ

        Returns:
            メモリ使用量が制限内の場合はTrue
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

    def _format_content(self, content: str, format_type: int) -> bool:
        """レンダリング結果をフォーマットする。

        指定されたフォーマットタイプに従ってコンテンツを整形します。
        フォーマット結果は内部状態として保持されます。

        Args:
            content: フォーマット対象のコンテンツ
            format_type: フォーマットタイプ [0-4の整数]

        Returns:
            フォーマットが成功したかどうか
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
        from functools import wraps

        T = TypeVar("T")

        def undefined_operation(func: Callable[..., T]) -> Callable[["CustomUndefined", Any], str]:
            """未定義変数に対する演算を処理するデコレータ。

            Args:
                func: デコレート対象の関数

            Returns:
                常に空文字列を返す関数
            """

            @wraps(func)
            def wrapper(self: "CustomUndefined", other: Any) -> str:
                return ""

            return wrapper

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

            def __eq__(self, other: object) -> bool:
                return isinstance(other, (CustomUndefined, Undefined))

            # 算術演算子のサポート
            @undefined_operation
            def __add__(self, other: Any) -> str:
                return ""

            @undefined_operation
            def __radd__(self, other: Any) -> str:
                return ""

            @undefined_operation
            def __sub__(self, other: Any) -> str:
                return ""

            @undefined_operation
            def __rsub__(self, other: Any) -> str:
                return ""

            @undefined_operation
            def __mul__(self, other: Any) -> str:
                return ""

            @undefined_operation
            def __rmul__(self, other: Any) -> str:
                return ""

            @undefined_operation
            def __div__(self, other: Any) -> str:
                return ""

            @undefined_operation
            def __rdiv__(self, other: Any) -> str:
                return ""

            @undefined_operation
            def __truediv__(self, other: Any) -> str:
                return ""

            @undefined_operation
            def __rtruediv__(self, other: Any) -> str:
                return ""

            @undefined_operation
            def __floordiv__(self, other: Any) -> str:
                return ""

            @undefined_operation
            def __rfloordiv__(self, other: Any) -> str:
                return ""

            @undefined_operation
            def __mod__(self, other: Any) -> str:
                return ""

            @undefined_operation
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
        env.filters["safe"] = self._security_validator.html_safe_filter  # safeフィルターを安全な実装に変更
        env.filters["html_safe"] = self._security_validator.html_safe_filter

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
