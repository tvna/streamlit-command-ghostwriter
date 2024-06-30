import re
from io import BytesIO
from typing import Any, Dict, Optional

from jinja2 import Environment, FileSystemLoader, StrictUndefined, Template, TemplateSyntaxError, UndefinedError


class GhostwriterRender:
    def __init__(self: "GhostwriterRender") -> None:
        self.__template_content: Optional[str] = None
        self.__render_content: Optional[str] = None
        self.__error_message: Optional[str] = None

    def load_template_file(self: "GhostwriterRender", template_file: BytesIO) -> "GhostwriterRender":
        try:
            self.__template_content = template_file.read().decode("utf-8")
        except (AttributeError, UnicodeDecodeError) as e:
            self.__error_message = str(e)

        return self

    def validate_template(self: "GhostwriterRender") -> bool:
        template = self.__template_content

        if template is None:
            return False

        try:
            env = Environment(autoescape=True)
            env.parse(template)
            return True

        except TemplateSyntaxError as e:
            self.__error_message = str(e)
            return False

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
            if is_strict_undefined:
                env: Environment = Environment(loader=FileSystemLoader("."), undefined=StrictUndefined, autoescape=True)
                strict_template: Template = env.from_string(template_str)
                render_content = strict_template.render(context)
            else:
                template: Template = Template(template_str)
                render_content = template.render(context)

        except (FileNotFoundError, TypeError, UndefinedError, TemplateSyntaxError, ValueError) as e:
            self.__error_message = str(e)
            return False

        try:
            self.__render_content = self.__format_context(render_content, format_type)
        except ValueError:
            self.__error_message = "Unsupported format type"
            return False

        return True

    @property
    def render_content(self: "GhostwriterRender") -> Optional[str]:
        """Jinja2テンプレートをレンダリングして文字列を返す。エラーが発生した場合はNoneを返す。"""
        return self.__render_content

    @property
    def error_message(self: "GhostwriterRender") -> Optional[str]:
        return self.__error_message
