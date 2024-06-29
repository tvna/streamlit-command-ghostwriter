#! /usr/bin/env python
import re
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, Final, Optional

from features.command_render import GhostwriterRender
from features.config_parser import GhostwriterParser
from features.text_transcoder import TextTranscoder


class GhostwriterCore:
    def __init__(self: "GhostwriterCore", config_error_header: Optional[str] = None, template_error_header: Optional[str] = None) -> None:
        self.__config_dict: Optional[Dict[str, Any]] = None
        self.__config_str: Optional[str] = None
        self.__render: Optional[GhostwriterRender] = None
        self.__formatted_text: Optional[str] = None
        self.__config_error_message: Optional[str] = None
        self.__template_error_message: Optional[str] = None

        self.__config_error_header = config_error_header
        self.__template_error_header = template_error_header

    def set_config_dict(self: "GhostwriterCore", config: Optional[Dict[str, Any]]) -> "GhostwriterCore":
        """Set config dict for template args."""

        self.__config_dict = config

        return self

    def load_config_file(
        self: "GhostwriterCore", config_file: Optional[BytesIO], csv_rows_name: str, is_auto_encoding: bool
    ) -> "GhostwriterCore":
        """Load config file for template args."""

        # 呼び出しされるたびに、前回の結果をリセットする
        self.__config_dict = None
        self.__config_str = None

        if not (config_file and hasattr(config_file, "name")):
            return self

        if is_auto_encoding:
            trans = TextTranscoder(config_file)
            config_file = trans.challenge_to_utf8()

        parser = GhostwriterParser()
        parser.set_csv_rows_name(csv_rows_name)
        parser.load_config_file(config_file).parse()

        if isinstance(parser.error_message, str):
            error_header = self.__config_error_header
            self.__config_error_message = f"{error_header}: {parser.error_message} in '{config_file.name}'"
            return self

        self.__config_dict = parser.parsed_dict
        self.__config_str = parser.parsed_str

        return self

    def load_template_file(self: "GhostwriterCore", template_file: Optional[BytesIO], is_auto_encoding: bool) -> "GhostwriterCore":
        """Load jinja template file."""

        self.__formatted_text = None

        if not template_file:
            return self

        if is_auto_encoding:
            trans = TextTranscoder(template_file)
            template_file = trans.challenge_to_utf8()

        render = GhostwriterRender()
        if not render.load_template_file(template_file).validate_template():
            error_header = self.__template_error_header
            self.__template_error_message = f"{error_header}: {render.error_message} in '{template_file.name}'"

        self.__template_filename = template_file.name
        self.__render = render

        return self

    def apply_context(self: "GhostwriterCore", format_type_str: str, is_strict_undefined: bool) -> "GhostwriterCore":
        """Apply context-dict for loaded template."""

        render = self.__render
        config_dict = self.__config_dict

        if config_dict is None or render is None:
            return self

        format_type_buffer = re.findall("^[0-9]+", format_type_str)
        if len(format_type_buffer) != 1:
            return self

        if not render.apply_context(config_dict, int(format_type_buffer[0]), is_strict_undefined):
            error_header = self.__template_error_header
            self.__template_error_message = f"{error_header}: {render.error_message} in '{self.__template_filename}'"
            return self

        self.__formatted_text = render.render_content
        return self

    def get_download_filename(
        self: "GhostwriterCore", filename: Optional[str], file_ext: Optional[str], is_append_timestamp: bool
    ) -> Optional[str]:
        """Get filename for download contents."""

        if filename is None or file_ext is None:
            return None

        suffix: Final[str] = f"_{datetime.today().strftime(r'%Y-%m-%d_%H%M%S')}" if is_append_timestamp else ""

        return f"{filename}{suffix}.{str(file_ext)}"

    def get_uploaded_filename(self: "GhostwriterCore", file: Optional[BytesIO]) -> Optional[str]:
        """Get filename for uploaded contents."""

        return file.name if isinstance(file, BytesIO) else None

    @property
    def config_dict(self: "GhostwriterCore") -> Optional[Dict[str, Any]]:
        return self.__config_dict

    @property
    def config_str(self: "GhostwriterCore") -> Optional[str]:
        return self.__config_str

    @property
    def formatted_text(self: "GhostwriterCore") -> Optional[str]:
        return self.__formatted_text

    @property
    def config_error_message(self: "GhostwriterCore") -> Optional[str]:
        return self.__config_error_message

    @property
    def template_error_message(self: "GhostwriterCore") -> Optional[str]:
        return self.__template_error_message

    @property
    def is_ready_formatted(self: "GhostwriterCore") -> bool:
        if self.__formatted_text is None:
            return False
        return True
