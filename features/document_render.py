import re
import sys
from io import BytesIO
from typing import Any, ClassVar, Dict, Optional

import jinja2 as j2
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, field_validator


class DocumentRender(BaseModel):
    # Constants for size limits
    MAX_FILE_SIZE_BYTES: ClassVar[int] = 30 * 1024 * 1024  # 30MB
    MAX_MEMORY_SIZE_BYTES: ClassVar[int] = 250 * 1024 * 1024  # 250MB

    # Public fields for validation
    template_file: BytesIO = Field(..., description="テンプレートファイルのバイナリデータ")

    # Private attributes
    __template_content: Optional[str] = PrivateAttr(default=None)
    __is_valid_template: bool = PrivateAttr(default=False)
    __render_content: Optional[str] = PrivateAttr(default=None)
    __error_message: Optional[str] = PrivateAttr(default=None)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @field_validator("template_file")
    def _validate_file_size(cls, v: BytesIO) -> BytesIO:  # noqa: N805
        """
        ファイルサイズのバリデーションを行います。

        Args:
            v: 検証するファイルオブジェクト

        Returns:
            検証済みのファイルオブジェクト

        Raises:
            ValueError: ファイルサイズが上限を超えている場合
        """
        # Check file size
        v.seek(0, 2)  # Move to the end of the file
        file_size = v.tell()  # Get current position (file size)
        v.seek(0)  # Reset position to the beginning

        if file_size > cls.MAX_FILE_SIZE_BYTES:
            raise ValueError(f"File size exceeds the maximum limit of 30MB (actual: {file_size / (1024 * 1024):.2f}MB)")
        return v

    def __init__(self, template_file: BytesIO) -> None:
        """
        DocumentRenderの初期化メソッド。

        Args:
            template_file: テンプレートファイルのバイナリデータ
        """
        # Pydanticモデルの初期化
        super().__init__(template_file=template_file)

        try:
            template = self.template_file.read().decode("utf-8")
        except (AttributeError, UnicodeDecodeError) as e:
            self.__error_message = str(e)
            return

        try:
            env = j2.Environment(autoescape=True)
            env.parse(template)
            self.__template_content = template
            self.__is_valid_template = True

        except j2.TemplateSyntaxError as e:
            self.__error_message = str(e)

    @property
    def is_valid_template(self) -> bool:
        """
        テンプレートが有効かどうかを示すプロパティ。

        Returns:
            テンプレートが有効であればTrue、無効であればFalse
        """
        return self.__is_valid_template

    def __remove_whitespaces(self, source_text: str) -> str:
        """
        空白行を削除します。

        Args:
            source_text: 空白を削除するテキスト

        Returns:
            空白行が削除されたテキスト
        """
        return re.sub(r"^\s+$\n", "\n", source_text, flags=re.MULTILINE)

    def __format_context(self, source_text: str, format_type: int) -> str:
        """
        フォーマットレベルに応じてコンテキストをフォーマットします。

        Args:
            source_text: フォーマットするテキスト
            format_type: フォーマットの種類を示す整数

        Returns:
            フォーマットされたテキスト

        Raises:
            ValueError: 無効なフォーマットタイプが指定された場合
        """
        match format_type:
            case 0:
                # raw text
                return source_text
            case 1:
                # remove spaces from space-only lines
                return self.__remove_whitespaces(source_text)
            case 2:
                # remove some duplicate line breaks
                return re.sub(r"\n\n+", "\n\n", source_text)
            case 3:
                # 1 & 2
                replaced_text = self.__remove_whitespaces(source_text)
                return re.sub(r"\n\n+", "\n\n", replaced_text)
            case 4:
                # 1 & remove all duplicate line breaks
                replaced_text = self.__remove_whitespaces(source_text)
                return re.sub(r"\n\n+", "\n", replaced_text)

        raise ValueError

    def _validate_memory_size(self, obj: Any) -> bool:  # noqa: ANN401
        """
        メモリサイズのバリデーションを行います。

        Args:
            obj: 検証するオブジェクト

        Returns:
            メモリサイズが上限以内の場合はTrue、超える場合はFalse
        """
        try:
            memory_size = sys.getsizeof(obj)
            if memory_size > self.MAX_MEMORY_SIZE_BYTES:
                self.__error_message = (
                    f"Memory consumption exceeds the maximum limit of 250MB (actual: {memory_size / (1024 * 1024):.2f}MB)"
                )
                return False
            return True
        except (MemoryError, OverflowError) as e:
            self.__error_message = f"Memory error while checking size: {e!s}"
            return False

    def apply_context(self, context: Dict[str, Any], format_type: int = 3, is_strict_undefined: bool = True) -> bool:
        """
        テンプレートにコンテキストを適用します。

        Args:
            context: テンプレートに適用するコンテキスト
            format_type: フォーマットの種類(デフォルトは3)
            is_strict_undefined: 未定義の変数に対して厳密にチェックするかどうか(デフォルトはTrue)

        Returns:
            成功した場合はTrue、失敗した場合はFalse
        """
        template_str = self.__template_content

        if template_str is None:
            return False

        try:
            if is_strict_undefined is True:
                env: j2.Environment = j2.Environment(loader=j2.FileSystemLoader("."), undefined=j2.StrictUndefined, autoescape=True)
                strict_template: j2.Template = env.from_string(template_str)
                raw_render_content = strict_template.render(context)
            else:
                template: j2.Template = j2.Template(template_str, autoescape=True)
                raw_render_content = template.render(context)

        except (FileNotFoundError, TypeError, j2.UndefinedError, j2.TemplateSyntaxError, ValueError) as e:
            self.__error_message = str(e)
            return False

        try:
            formatted_content = self.__format_context(raw_render_content, format_type)

            # メモリサイズのバリデーション
            if not self._validate_memory_size(formatted_content):
                return False

            self.__render_content = formatted_content
            return True
        except ValueError:
            self.__error_message = "Unsupported format type"
            return False

    @property
    def render_content(self) -> Optional[str]:
        """
        Jinja2テンプレートをレンダリングして文字列を返します。

        Returns:
            レンダリングされたコンテンツ、エラーが発生した場合はNone
        """
        return self.__render_content

    @property
    def error_message(self) -> Optional[str]:
        """
        エラーメッセージを返します。

        Returns:
            エラーメッセージ、エラーが発生していない場合はNone
        """
        return self.__error_message
