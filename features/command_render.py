from io import BytesIO
from typing import Any, Dict, Optional

from jinja2 import Environment, FileSystemLoader, StrictUndefined, Template, TemplateSyntaxError, UndefinedError


class GhostwriterRender:
    def __init__(self: "GhostwriterRender", is_strict_undefined: bool = True) -> None:
        self.__template_content: Optional[str] = None
        self.__render_content: Optional[str] = None
        self.__error_message: Optional[str] = None
        self.__is_strict_undefined: bool = is_strict_undefined

    def load_template_file(self: "GhostwriterRender", template_file: BytesIO) -> "GhostwriterRender":
        try:
            self.__template_content = template_file.read().decode("utf-8")
        except (AttributeError, UnicodeDecodeError) as e:
            self.__error_message = str(e)

        return self

    def apply_context(self: "GhostwriterRender", context: Optional[Dict[str, Any]]) -> bool:
        if self.__template_content is None:
            return False

        try:
            if self.__is_strict_undefined:
                env: Environment = Environment(loader=FileSystemLoader("."), undefined=StrictUndefined)
                strict_template: Template = env.from_string(self.__template_content)
                self.__render_content = strict_template.render(context)
                return True

            template: Template = Template(self.__template_content)
            self.__render_content = template.render(context)

        except (FileNotFoundError, TypeError, UndefinedError, TemplateSyntaxError) as e:
            self.__error_message = str(e)
            return False

        return True

    @property
    def render_content(self: "GhostwriterRender") -> Optional[str]:
        """Jinja2テンプレートをレンダリングして文字列を返す。エラーが発生した場合はNoneを返す。"""
        return self.__render_content

    @property
    def error_message(self: "GhostwriterRender") -> Optional[str]:
        return self.__error_message
