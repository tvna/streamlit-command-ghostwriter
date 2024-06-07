import re
from io import BytesIO
from typing import Any, Dict, Optional

from jinja2 import Environment, FileSystemLoader, StrictUndefined, Template, TemplateSyntaxError, UndefinedError


class GhostwriterRender:
    def __init__(self: "GhostwriterRender", is_strict_undefined: bool = True, is_remove_multiple_newline: bool = True) -> None:
        self.__template_content: Optional[str] = None
        self.__render_content: Optional[str] = None
        self.__error_message: Optional[str] = None
        self.__is_strict_undefined: bool = is_strict_undefined
        self.__is_remove_multiple_newline: bool = is_remove_multiple_newline

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
            env = Environment()
            env.parse(template)
            return True

        except TemplateSyntaxError as e:
            self.__error_message = str(e)
            return False

    def __remove_whitespaces_and_multiple_newlines(self: "GhostwriterRender", source_text: str) -> str:
        replace_whitespaces = re.sub(r"^\s+$\n", "\n", source_text, flags=re.MULTILINE)
        return re.sub(r"\n\n+", "\n\n", replace_whitespaces)

    def apply_context(self: "GhostwriterRender", context: Dict[str, Any]) -> bool:
        template_str = self.__template_content

        if template_str is None:
            return False

        try:
            if self.__is_strict_undefined:
                env: Environment = Environment(loader=FileSystemLoader("."), undefined=StrictUndefined)
                strict_template: Template = env.from_string(template_str)
                render_content = strict_template.render(context)
            else:
                template: Template = Template(template_str)
                render_content = template.render(context)

        except (FileNotFoundError, TypeError, UndefinedError, TemplateSyntaxError) as e:
            self.__error_message = str(e)
            return False

        self.__render_content = (
            self.__remove_whitespaces_and_multiple_newlines(render_content) if self.__is_remove_multiple_newline else render_content
        )

        return True

    @property
    def render_content(self: "GhostwriterRender") -> Optional[str]:
        """Jinja2テンプレートをレンダリングして文字列を返す。エラーが発生した場合はNoneを返す。"""
        return self.__render_content

    @property
    def error_message(self: "GhostwriterRender") -> Optional[str]:
        return self.__error_message
