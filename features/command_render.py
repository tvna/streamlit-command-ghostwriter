from io import BytesIO
from typing import Any, Dict, Optional

from jinja2 import Environment, FileSystemLoader, StrictUndefined, Template, TemplateSyntaxError, UndefinedError


class GhostwriterRender:
    def __init__(self, template_file: BytesIO, context: Dict[str, Any], is_strict_undefined: bool = True) -> None:
        self.__render_content: Optional[str] = None
        self.__context_dict: Dict[str, Any] = context
        self.__is_strict_undefined: bool = is_strict_undefined
        self.__error_message: str = "Not failed"

        try:
            template_content: str = template_file.read().decode("utf-8")
        except (AttributeError, UnicodeDecodeError) as e:
            self.__error_message = str(e)
            return None

        try:
            if self.__is_strict_undefined:
                env: Environment = Environment(loader=FileSystemLoader("."), undefined=StrictUndefined)
                strict_template: Template = env.from_string(template_content)
                self.__render_content = strict_template.render(self.__context_dict)
            else:
                template: Template = Template(template_content)
                self.__render_content = template.render(self.__context_dict)
        except (TypeError, UndefinedError, TemplateSyntaxError) as e:
            self.__error_message = str(e)
            return None

    @property
    def render_content(self) -> Optional[str]:
        """Jinja2テンプレートをレンダリングして文字列を返す。エラーが発生した場合はNoneを返す。"""

        return self.__render_content

    @property
    def error_message(self) -> str:
        return self.__error_message
