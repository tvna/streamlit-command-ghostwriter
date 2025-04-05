#! /usr/bin/env python
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, Final, Optional

from pydantic import BaseModel, PrivateAttr

from features.config_parser import ConfigParser
from features.document_render import DocumentRender
from features.transcoder import TextTranscoder


class AppCore(BaseModel):
    _config_dict: Optional[Dict[str, Any]] = PrivateAttr(default=None)
    _config_error_header: Optional[str] = PrivateAttr(default=None)
    _config_error_message: Optional[str] = PrivateAttr(default=None)
    _formatted_text: Optional[str] = PrivateAttr(default=None)
    _template_filename: Optional[str] = PrivateAttr(default=None)
    _template_error_header: Optional[str] = PrivateAttr(default=None)
    _template_error_message: Optional[str] = PrivateAttr(default=None)
    _render: Optional[DocumentRender] = PrivateAttr(default=None)

    def __init__(self: "AppCore", config_error_header: Optional[str] = None, template_error_header: Optional[str] = None) -> None:
        """
        AppCoreの初期化メソッド。

        Args:
            config_error_header (Optional[str]): 設定エラーのヘッダー(デフォルトはNone)
            template_error_header (Optional[str]): テンプレートエラーのヘッダー(デフォルトはNone)
        """

        super().__init__()
        self._config_error_header = config_error_header
        self._template_error_header = template_error_header

    def load_config_file(
        self: "AppCore",
        config_file: Optional[BytesIO],
        csv_rows_name: str,
        enable_auto_transcoding: bool,
        enable_fill_nan: bool = False,
        fill_nan_with: str = "#",
    ) -> "AppCore":
        """Load config file for template args.

        Args:
            config_file (Optional[BytesIO]): 設定ファイルのバイナリデータ。
            csv_rows_name (str): CSVの行名。
            enable_auto_transcoding (bool): 自動トランスコーディングを有効にするかどうか。
            enable_fill_nan (bool): NaNを埋めるかどうか(デフォルトはFalse)
            fill_nan_with (str): NaNを埋める際の文字列(デフォルトは"#")

        Returns:
            AppCore: 自身のインスタンス。
        """

        # 呼び出しされるたびに、前回の結果をリセットする
        self._config_dict = None

        if not (isinstance(config_file, BytesIO) and hasattr(config_file, "name")):
            return self

        config_filename: Final[str] = config_file.name
        if enable_auto_transcoding is True:
            config_file = TextTranscoder(config_file).convert(is_allow_fallback=False)

        if config_file is None:
            self._config_error_message = f"{self._template_error_header}: Failed auto decoding in '{config_filename}'"
            return self

        parser = ConfigParser(config_file)
        parser.csv_rows_name = csv_rows_name
        parser.fill_nan_with = fill_nan_with
        parser.enable_fill_nan = enable_fill_nan
        parser.parse()

        if parser.error_message is None:
            self._config_dict = parser.parsed_dict
            return self

        self._config_error_message = f"{self._config_error_header}: {parser.error_message} in '{config_filename}'"
        return self

    def load_template_file(self: "AppCore", template_file: Optional[BytesIO], enable_auto_transcoding: bool) -> "AppCore":
        """Load jinja template file.

        Args:
            template_file (Optional[BytesIO]): テンプレートファイルのバイナリデータ。
            enable_auto_transcoding (bool): 自動トランスコーディングを有効にするかどうか。

        Returns:
            AppCore: 自身のインスタンス。
        """

        if template_file is None:
            return self

        template_filename: Final[str] = template_file.name
        if enable_auto_transcoding is True:
            template_file = TextTranscoder(template_file).convert(is_allow_fallback=False)

        if template_file is None:
            self._template_error_message = f"{self._template_error_header}: Failed auto decoding in '{template_filename}'"
            return self

        render: DocumentRender = DocumentRender(template_file)
        if render.is_valid_template is False:
            self._template_error_message = f"{self._template_error_header}: {render.error_message} in '{template_filename}'"

        self._template_filename = template_filename
        self._render = render

        return self

    def apply(self: "AppCore", format_type: int, is_strict_undefined: bool) -> "AppCore":
        """Apply context-dict for loaded template.

        Args:
            format_type (int): フォーマットの種類を示す整数。
            is_strict_undefined (bool): 未定義の変数に対して厳密にチェックするかどうか。

        Returns:
            AppCore: 自身のインスタンス。
        """

        self._formatted_text = None

        render: Optional[DocumentRender] = self._render
        config_dict: Optional[Dict[str, Any]] = self._config_dict

        if config_dict is None or render is None:
            return self

        if render.apply_context(config_dict, format_type, is_strict_undefined) is False:
            self._template_error_message = f"{self._template_error_header}: {render.error_message} in '{self._template_filename}'"
            return self

        self._formatted_text = render.render_content
        self._template_error_message = None

        return self

    def get_download_filename(
        self: "AppCore", filename: Optional[str], file_ext: Optional[str], is_append_timestamp: bool
    ) -> Optional[str]:
        """Get filename for download contents.

        Args:
            filename (Optional[str]): ダウンロードするファイル名。
            file_ext (Optional[str]): ファイルの拡張子。
            is_append_timestamp (bool): タイムスタンプを追加するかどうか。

        Returns:
            Optional[str]: ダウンロード用のファイル名。
        """

        if filename is None or file_ext is None:
            return None

        datetime_format: Final[str] = r"%Y-%m-%d_%H%M%S"
        suffix: Final[str] = f"_{datetime.today().strftime(datetime_format)}" if is_append_timestamp is True else ""

        return f"{filename}{suffix}.{file_ext!s}"

    def get_download_content(self: "AppCore", encode: str) -> Optional[bytes]:
        """Get the content for download.

        Args:
            encode (str): エンコーディング形式。

        Returns:
            Optional[bytes]: ダウンロード用のコンテンツ、またはNone。
        """
        if self._formatted_text is None:
            return None

        try:
            return self._formatted_text.encode(encode)
        except LookupError:
            return None

    @property
    def config_dict(self: "AppCore") -> Optional[Dict[str, Any]]:
        """Get the configuration dictionary.

        Returns:
            Optional[Dict[str, Any]]: 設定辞書。
        """
        return self._config_dict

    @config_dict.setter
    def config_dict(self: "AppCore", config: Optional[Dict[str, Any]]) -> None:
        """Set config dict for template args.

        Args:
            config (Optional[Dict[str, Any]]): 設定辞書。
        """
        self._config_dict = config

    @property
    def formatted_text(self: "AppCore") -> Optional[str]:
        """Get the formatted text.

        Returns:
            Optional[str]: フォーマットされたテキスト。
        """
        return self._formatted_text

    @property
    def config_error_message(self: "AppCore") -> Optional[str]:
        """Get the configuration error message.

        Returns:
            Optional[str]: 設定エラーメッセージ。
        """
        return self._config_error_message

    @property
    def template_error_message(self: "AppCore") -> Optional[str]:
        """Get the template error message.

        Returns:
            Optional[str]: テンプレートエラーメッセージ。
        """
        return self._template_error_message

    @property
    def is_ready_formatted(self: "AppCore") -> bool:
        """Check if the formatted text is ready.

        Returns:
            bool: フォーマットされたテキストが準備できていればTrue、そうでなければFalse。
        """
        return self._formatted_text is not None
