#! /usr/bin/env python
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, Optional

import streamlit as st

from features.command_render import GhostwriterRender
from features.config_parser import GhostwriterParser
from i11n import LANGUAGES


class AppModel:
    def __init__(self: "AppModel", config_error_header: Optional[str] = None, template_error_header: Optional[str] = None) -> None:
        self.__config_dict: Optional[Dict[str, Any]] = None
        self.__config_str: Optional[str] = None
        self.__render: Optional[GhostwriterRender] = None
        self.__formatted_text: Optional[str] = None
        self.__config_error_message: Optional[str] = None
        self.__template_error_message: Optional[str] = None

        self.__config_error_header = config_error_header
        self.__template_error_header = template_error_header

    def set_config_dict(self: "AppModel", config: Optional[Dict[str, Any]]) -> None:
        """Set config dict for template args."""

        self.__config_dict = config

    def load_config_file(self: "AppModel", config_file: Optional[BytesIO]) -> bool:
        """Load config file for template args."""

        # 呼び出しされるたびに、前回の結果をリセットする
        self.__config_dict = None
        self.__config_str = None

        if not (config_file and hasattr(config_file, "name")):
            return False

        parser = GhostwriterParser()
        parser.load_config_file(config_file).parse()

        if isinstance(parser.error_message, str):
            error_header = self.__config_error_header
            self.__config_error_message = f"{error_header}: {parser.error_message} in '{config_file.name}'"
            return False

        self.__config_dict = parser.parsed_dict
        self.__config_str = parser.parsed_str

        return True

    def load_template_file(
        self: "AppModel", template_file: Optional[BytesIO], is_strict_undefined: bool, is_clear_dup_lines: bool
    ) -> "AppModel":
        """Load jinja template file."""

        self.__formatted_text = None

        if not template_file:
            return self

        render = GhostwriterRender(is_strict_undefined, is_clear_dup_lines)
        if not render.load_template_file(template_file).validate_template():
            error_header = self.__template_error_header
            self.__template_error_message = f"{error_header}: {render.error_message} in '{template_file.name}'"

        self.__template_filename = template_file.name
        self.__render = render

        return self

    def apply_context(self: "AppModel") -> "AppModel":
        """Apply context-dict for loaded template."""

        if self.__config_dict is None or self.__render is None:
            return self

        render = self.__render

        if not render.apply_context(self.__config_dict):
            error_header = self.__template_error_header
            self.__template_error_message = f"{error_header}: {render.error_message} in '{self.__template_filename}'"
            return self

        self.__formatted_text = render.render_content
        return self

    def get_download_filename(
        self: "AppModel",
        download_filename: Optional[str],
        download_file_ext: Optional[str],
        is_append_timestamp: bool,
    ) -> Optional[str]:
        """Get filename for download contents."""

        if download_filename is None or download_file_ext is None:
            return None

        suffix = f"_{datetime.today().strftime(r'%Y-%m-%d_%H%M%S')}" if is_append_timestamp else ""
        filename = f"{download_filename}{suffix}.{str(download_file_ext)}"

        return filename

    def get_uploaded_filename(self: "AppModel", file: Optional[BytesIO]) -> Optional[str]:
        """Get filename for uploaded contents."""

        return file.name if isinstance(file, BytesIO) else None

    @property
    def config_dict(self: "AppModel") -> Optional[Dict[str, Any]]:
        return self.__config_dict

    @property
    def config_str(self: "AppModel") -> Optional[str]:
        return self.__config_str

    @property
    def formatted_text(self: "AppModel") -> Optional[str]:
        return self.__formatted_text

    @property
    def config_error_message(self: "AppModel") -> Optional[str]:
        return self.__config_error_message

    @property
    def template_error_message(self: "AppModel") -> Optional[str]:
        return self.__template_error_message

    @property
    def is_ready_formatted(self: "AppModel") -> bool:
        if self.__formatted_text is None:
            return False
        return True


class TabViewModel:
    def __init__(self: "TabViewModel", texts: Dict[str, str]) -> None:
        self.__texts = texts
        self.__execute_mode: int = 0

    def set_execute_mode(self: "TabViewModel", is_text: bool, is_markdown: bool, is_debug: bool) -> "TabViewModel":
        """Set execute mode."""

        self.__execute_mode = 0

        if is_text:
            self.__execute_mode = 1
            return self

        if is_markdown:
            self.__execute_mode = 2
            return self

        if is_debug:
            self.__execute_mode = 3
            return self

        return self

    def show_tab1(
        self: "TabViewModel", result_text: Optional[str], first_error_message: Optional[str], second_error_message: Optional[str]
    ) -> None:
        """Show tab1 response content."""

        if first_error_message or second_error_message:
            self.__show_tab1_error(first_error_message, second_error_message)
        elif (3 > self.__execute_mode > 0) and isinstance(result_text, str):
            self.__show_tab1_result(result_text)
        elif 3 > self.__execute_mode > 0:
            st.warning(self.__texts["tab1_error_both_files"])

    def __show_tab1_result(self: "TabViewModel", result_text: str) -> None:
        """Show tab1 success content."""

        if self.__execute_mode == 1:
            st.success(self.__texts["tab1_success_formatted_text"])
            st.container(border=True).text_area(self.__texts["tab1_formatted_text"], result_text, key="tab1_result_textarea", height=500)
        elif self.__execute_mode == 2:
            st.success(self.__texts["tab1_success_formatted_text"])
            st.container(border=True).markdown(result_text)

    def __show_tab1_error(self: "TabViewModel", first_error_message: Optional[str], second_error_message: Optional[str]) -> None:
        """Show tab1 error content."""

        if first_error_message:
            st.error(first_error_message)
        if second_error_message:
            st.error(second_error_message)

    def show_tab2(self: "TabViewModel", parsed_config: Optional[str], filename: Optional[str], error_message: Optional[str]) -> None:
        """Show tab2 response content."""

        if error_message:
            st.error(error_message)
        if self.__execute_mode < 3:
            return
        elif not filename or not parsed_config:
            st.warning(f"{self.__texts['tab2_error_debug_not_found']}")
            return

        st.success(self.__texts["tab2_success_debug_config"])
        st.text_area(self.__texts["tab2_debug_config_text"], parsed_config, key="tab2_result_textarea", height=500)


def main() -> None:
    """Generate Streamlit web screens."""
    texts: Dict[str, str] = LANGUAGES["日本語"]

    st.session_state.update({"tab1_result_content": st.session_state.get("tab1_result_content")})
    st.session_state.update({"tab2_result_content": st.session_state.get("tab2_result_content")})

    st.set_page_config(
        page_title="Command ghostwriter",
        page_icon=":ghost:",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.title("Command ghostwriter :ghost:")

    with st.sidebar:
        st.write(texts["sidebar_welcome"])

        with st.expander(texts["sidebar_syntax_of_each_file"], expanded=True):
            st.markdown(
                f"""
            - [toml syntax docs]({texts["sidebar_toml_syntax_doc"]})
            - [yaml syntax docs]({texts["sidebar_yaml_syntax_doc"]})
            - [jinja syntax docs]({texts["sidebar_jinja_syntax_doc"]})
            """
            )

    tab1, tab2, tab3 = st.tabs([texts["tab1_menu_convert_text"], texts["tab2_menu_debug_config"], texts["tab3_menu_advanced_option"]])

    with tab1:
        tab1_row1_col1, tab1_row1_col2 = st.columns(2)
        with tab1_row1_col1.container(border=True):
            st.file_uploader(
                texts["tab1_upload_config"],
                type=["toml", "yaml", "yml"],
                key="tab1_config_file",
            )

        with tab1_row1_col2.container(border=True):
            st.file_uploader(
                texts["tab1_upload_template"],
                type=["jinja2", "j2"],
                key="tab1_template_file",
            )

        tab1_row2_col1, tab1_row2_col2, tab1_row2_col3 = st.columns(3)
        tab1_row2_col1.button(
            texts["tab1_generate_text_button"],
            use_container_width=True,
            key="tab1_execute_text",
        )
        tab1_row2_col2.button(
            texts["tab1_generate_markdown_button"],
            use_container_width=True,
            key="tab1_execute_markdown",
        )

        tab1_model = AppModel(texts["tab1_error_toml_parse"], texts["tab1_error_template_generate"])
        tab1_model.load_config_file(st.session_state.get("tab1_config_file"))
        tab1_model.load_template_file(
            st.session_state.get("tab1_template_file"),
            st.session_state.get("is_strict_undefined", True),
            st.session_state.get("is_remove_multiple_newline", True),
        ).apply_context()

        st.session_state.update({"tab1_result_content": tab1_model.formatted_text})
        st.session_state.update({"tab1_error_config": tab1_model.config_error_message})
        st.session_state.update({"tab1_error_template": tab1_model.template_error_message})

        tab1_row2_col3.download_button(
            label=texts["tab1_download_button"],
            data=st.session_state.get("tab1_result_content", None) or "No data available",
            file_name=tab1_model.get_download_filename(
                st.session_state.get("download_filename", "command"),
                st.session_state.get("download_file_ext", "txt"),
                st.session_state.get("is_append_timestamp", True),
            ),
            disabled=False if tab1_model.is_ready_formatted else True,
            use_container_width=True,
        )

        tab1_view_model = TabViewModel(texts)
        tab1_view_model.set_execute_mode(
            st.session_state.get("tab1_execute_text", False),
            st.session_state.get("tab1_execute_markdown", False),
            st.session_state.get("tab2_execute", False),
        ).show_tab1(
            st.session_state.get("tab1_result_content", None),
            st.session_state.get("tab1_error_config", None),
            st.session_state.get("tab1_error_template", None),
        )

    with tab2:
        tab2_model = AppModel(texts["tab2_error_debug_config"])
        tab2_row1_col1, _ = st.columns(2)
        with tab2_row1_col1.container(border=True):
            st.file_uploader(
                texts["tab2_upload_debug_config"],
                type=["toml", "yaml", "yml"],
                key="tab2_config_file",
            )

        tab2_model.load_config_file(st.session_state.get("tab2_config_file"))

        tab2_row2_col1, _, _ = st.columns(3)
        tab2_row2_col1.button(texts["tab2_generate_debug_config"], use_container_width=True, key="tab2_execute")

        st.session_state.update({"tab2_result_content": tab2_model.config_str})
        st.session_state.update({"tab2_error_config": tab2_model.config_error_message})

        tab2_view_model = TabViewModel(texts)
        tab2_view_model.set_execute_mode(
            st.session_state.get("tab1_execute_text", False),
            st.session_state.get("tab1_execute_markdown", False),
            st.session_state.get("tab2_execute", False),
        ).show_tab2(
            st.session_state.get("tab2_result_content", ""),
            tab2_model.get_uploaded_filename(st.session_state.get("tab2_config_file")),
            st.session_state.get("tab2_error_config", None),
        )

    with tab3:
        tab3_row1_col1, _ = st.columns(2)
        with tab3_row1_col1.container(border=True):
            st.markdown(texts["tab3_header_generate_text"])
            st.session_state.download_filename = st.text_input(texts["tab3_download_filename"], "command")
            st.session_state.is_append_timestamp = st.toggle(texts["tab3_append_timestamp_filename"], value=True)
            st.session_state.download_file_ext = st.radio(texts["tab3_download_file_extension"], ["txt", "md"])
            st.session_state.is_strict_undefined = st.toggle(texts["tab3_strict_undefined"], value=True)
            st.session_state.is_remove_multiple_newline = st.toggle(texts["tab3_remove_multiple_newline"], value=True)


if __name__ == "__main__":
    main()
