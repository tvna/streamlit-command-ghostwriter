from io import BytesIO
from typing import Any, Dict, Optional

from jinja2 import Environment, FileSystemLoader, StrictUndefined, Template, TemplateSyntaxError, UndefinedError


class GhostwriterRender:
    def __init__(self, is_strict_undefined: bool = True) -> None:
        self.__template_content: Optional[str] = None
        self.__render_content: Optional[str] = None
        self.__error_message: Optional[str] = None
        self.__is_strict_undefined: bool = is_strict_undefined

    def load_template_file(self, template_file: BytesIO):
        try:
            self.__template_content = template_file.read().decode("utf-8")
        except (AttributeError, UnicodeDecodeError) as e:
            self.__error_message = str(e)

        return self

    def apply_context(self, context: Dict[str, Any]) -> bool:
        self.__context_dict: Dict[str, Any] = context

        try:
            if self.__template_content is None:
                return False

            if self.__is_strict_undefined:
                env: Environment = Environment(loader=FileSystemLoader("."), undefined=StrictUndefined)
                strict_template: Template = env.from_string(self.__template_content)
                self.__render_content = strict_template.render(self.__context_dict)
            else:
                template: Template = Template(self.__template_content)
                self.__render_content = template.render(self.__context_dict)
            return True
        except (FileNotFoundError, TypeError, UndefinedError, TemplateSyntaxError) as e:
            self.__error_message = str(e)
            return False

    @property
    def render_content(self) -> Optional[str]:
        """Jinja2テンプレートをレンダリングして文字列を返す。エラーが発生した場合はNoneを返す。"""
        return self.__render_content

    @property
    def error_message(self) -> Optional[str]:
        return self.__error_message
