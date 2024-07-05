import re
from io import BytesIO
from typing import Any, Dict, Optional

import jinja2 as j2
from pydantic import BaseModel, PrivateAttr


class GhostwriterRender(BaseModel):
    __template_content: Optional[str] = PrivateAttr(default=None)
    __is_valid_template: bool = PrivateAttr(default=False)
    __render_content: Optional[str] = PrivateAttr(default=None)
    __error_message: Optional[str] = PrivateAttr(default=None)

    def __init__(self: "GhostwriterRender", template_file: BytesIO) -> None:
        super().__init__()

        try:
            template = template_file.read().decode("utf-8")
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
    def is_valid_template(self: "GhostwriterRender") -> bool:
        return self.__is_valid_template

    def __remove_whitespaces(self: "GhostwriterRender", source_text: str) -> str:
        return re.sub(r"^\s+$\n", "\n", source_text, flags=re.MULTILINE)

    def __format_context(self: "GhostwriterRender", source_text: str, format_type: int) -> str:
        """Format the context according to the formatting level."""

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

    def apply_context(self: "GhostwriterRender", context: Dict[str, Any], format_type: int = 3, is_strict_undefined: bool = True) -> bool:
        template_str = self.__template_content

        if template_str is None:
            return False

        try:
            if is_strict_undefined is True:
                env: j2.Environment = j2.Environment(loader=j2.FileSystemLoader("."), undefined=j2.StrictUndefined, autoescape=True)
                strict_template: j2.Template = env.from_string(template_str)
                raw_render_content = strict_template.render(context)
            else:
                template: j2.Template = j2.Template(template_str)
                raw_render_content = template.render(context)

        except (FileNotFoundError, TypeError, j2.UndefinedError, j2.TemplateSyntaxError, ValueError) as e:
            self.__error_message = str(e)
            return False

        try:
            self.__render_content = self.__format_context(raw_render_content, format_type)
            return True
        except ValueError:
            self.__error_message = "Unsupported format type"
            return False

    @property
    def render_content(self: "GhostwriterRender") -> Optional[str]:
        """Jinja2テンプレートをレンダリングして文字列を返す。エラーが発生した場合はNoneを返す。"""
        return self.__render_content

    @property
    def error_message(self: "GhostwriterRender") -> Optional[str]:
        return self.__error_message
