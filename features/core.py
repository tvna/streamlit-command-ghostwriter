#! /usr/bin/env python
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, Final, Optional

from pydantic import BaseModel, PrivateAttr

from features.config_parser import ConfigParser
from features.document_render import DocumentRender
from features.transcoder import TextTranscoder


class AppCore(BaseModel):
    __config_dict: Optional[Dict[str, Any]] = PrivateAttr(default=None)
    __render: Optional[DocumentRender] = PrivateAttr(default=None)
    __formatted_text: Optional[str] = PrivateAttr(default=None)
    __config_error_message: Optional[str] = PrivateAttr(default=None)
    __template_error_message: Optional[str] = PrivateAttr(default=None)

    __config_error_header = PrivateAttr()
    __template_error_header = PrivateAttr()

    def __init__(self: "AppCore", config_error_header: Optional[str] = None, template_error_header: Optional[str] = None) -> None:
        super().__init__()

        self.__config_error_header = config_error_header
        self.__template_error_header = template_error_header

    def load_config_file(self: "AppCore", config_file: Optional[BytesIO], csv_rows_name: str, enable_auto_transcoding: bool) -> "AppCore":
        """Load config file for template args."""

        # 呼び出しされるたびに、前回の結果をリセットする
        self.__config_dict = None

        if not (isinstance(config_file, BytesIO) and hasattr(config_file, "name")):
            return self

        config_filename = config_file.name
        if enable_auto_transcoding is True:
            config_file = TextTranscoder(config_file).convert(is_allow_fallback=False)

        if config_file is None:
            error_header = self.__template_error_header
            self.__config_error_message = f"{error_header}: Failed auto decoding in '{config_filename}'"
            return self

        parser = ConfigParser(config_file)
        parser.csv_rows_name = csv_rows_name
        parser.parse()

        if parser.error_message is None:
            self.__config_dict = parser.parsed_dict
            return self

        error_header = self.__config_error_header
        self.__config_error_message = f"{error_header}: {parser.error_message} in '{config_filename}'"
        return self

    def load_template_file(self: "AppCore", template_file: Optional[BytesIO], enable_auto_transcoding: bool) -> "AppCore":
        """Load jinja template file."""

        if template_file is None:
            return self

        template_filename = template_file.name
        if enable_auto_transcoding is True:
            template_file = TextTranscoder(template_file).convert(is_allow_fallback=False)

        if template_file is None:
            error_header = self.__template_error_header
            self.__template_error_message = f"{error_header}: Failed auto decoding in '{template_filename}'"
            return self

        render = DocumentRender(template_file)
        if render.is_valid_template is False:
            error_header = self.__template_error_header
            self.__template_error_message = f"{error_header}: {render.error_message} in '{template_filename}'"

        self.__template_filename = template_filename
        self.__render = render

        return self

    def apply(self: "AppCore", format_type: int, is_strict_undefined: bool) -> "AppCore":
        """Apply context-dict for loaded template."""

        self.__formatted_text = None

        render = self.__render
        config_dict = self.__config_dict

        if config_dict is None or render is None:
            return self

        if render.apply_context(config_dict, format_type, is_strict_undefined) is False:
            error_header = self.__template_error_header
            self.__template_error_message = f"{error_header}: {render.error_message} in '{self.__template_filename}'"
            return self

        self.__formatted_text = render.render_content
        self.__template_error_message = None

        return self

    def get_download_filename(
        self: "AppCore", filename: Optional[str], file_ext: Optional[str], is_append_timestamp: bool
    ) -> Optional[str]:
        """Get filename for download contents."""

        if filename is None or file_ext is None:
            return None

        suffix: Final[str] = f"_{datetime.today().strftime(r'%Y-%m-%d_%H%M%S')}" if is_append_timestamp is True else ""

        return f"{filename}{suffix}.{str(file_ext)}"

    def get_download_content(self: "AppCore", encode: str) -> Optional[bytes]:
        if self.__formatted_text is None:
            return None

        try:
            return self.__formatted_text.encode(encode)
        except LookupError:
            return None

    @property
    def config_dict(self: "AppCore") -> Optional[Dict[str, Any]]:
        return self.__config_dict

    @config_dict.setter
    def config_dict(self: "AppCore", config: Optional[Dict[str, Any]]) -> None:
        """Set config dict for template args."""
        self.__config_dict = config

    @property
    def formatted_text(self: "AppCore") -> Optional[str]:
        return self.__formatted_text

    @property
    def config_error_message(self: "AppCore") -> Optional[str]:
        return self.__config_error_message

    @property
    def template_error_message(self: "AppCore") -> Optional[str]:
        return self.__template_error_message

    @property
    def is_ready_formatted(self: "AppCore") -> bool:
        if self.__formatted_text is None:
            return False
        return True
