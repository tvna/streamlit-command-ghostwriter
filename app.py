#! /usr/bin/env python
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, Optional, Tuple

import streamlit as st

from features.command_render import GhostwriterRender
from features.config_parser import GhostwriterParser
from i11n import LANGUAGES


class AppModel:
    def __init__(self: "AppModel") -> None:
        self.__config_dict: Optional[Dict[str, Any]] = None
        self.__config_str: Optional[str] = None
        self.__formatted_text: Optional[str] = None
        self.__config_error_message: Optional[str] = None
        self.__template_error_message: Optional[str] = None

    def set_config_dict(self: "AppModel", config: Optional[Dict[str, Any]]) -> None:
        self.__config_dict = config

    def load_config_file(self: "AppModel", config_file: Optional[BytesIO], error_header: str) -> bool:
        # 呼び出しされるたびに、前回の結果をリセットする
        self.__config_dict = None
        self.__config_str = None

        if not (config_file and hasattr(config_file, "name")):
            return False

        parser = GhostwriterParser()
        parser.load_config_file(config_file).parse()

        if isinstance(parser.error_message, str):
            self.__config_error_message = f"{error_header}: {parser.error_message} in '{config_file.name}'"
            return False

        self.__config_dict = parser.parsed_dict
        self.__config_str = parser.parsed_str

        return True

    def load_template_file(
        self: "AppModel",
        template_file: Optional[BytesIO],
        error_header: str,
        is_strict_undefined: bool,
        is_clear_dup_lines: bool,
    ) -> bool:
        self.__formatted_text = None

        if not template_file:
            return False

        render = GhostwriterRender(is_strict_undefined, is_clear_dup_lines)
        if not render.load_template_file(template_file).validate_template():
            self.__template_error_message = f"{error_header}: {render.error_message} in '{template_file.name}'"
            return False

        if self.__config_dict is None:
            return False

        if not render.apply_context(self.__config_dict):
            self.__template_error_message = f"{error_header}: {render.error_message} in '{template_file.name}'"
            return False

        self.__formatted_text = render.render_content
        return True

    def get_download_filename(
        self: "AppModel",
        download_filename: Optional[str],
        download_file_ext: Optional[str],
        is_append_timestamp: bool,
    ) -> Optional[str]:
        if download_filename is None or download_file_ext is None:
            return None

        suffix = f"_{datetime.today().strftime(r'%Y-%m-%d_%H%M%S')}" if is_append_timestamp else ""
        filename = f"{download_filename}{suffix}.{str(download_file_ext)}"

        return filename

    def get_uploaded_filename(self: "AppModel", file: Optional[BytesIO]) -> Optional[str]:
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

    def show_tab1(
        self: "TabViewModel",
        is_submit_text: bool,
        is_submit_markdown: bool,
        result_text: Optional[str],
        error_messages: Tuple[Optional[str], Optional[str]],
    ) -> None:
        first_error_message, second_error_message = error_messages
        if first_error_message or second_error_message:
            self.__show_tab1_error(first_error_message, second_error_message)
        elif (is_submit_text or is_submit_markdown) and isinstance(result_text, str):
            self.__show_tab1_result(is_submit_text, is_submit_markdown, result_text)
        elif is_submit_text or is_submit_markdown:
            st.warning(self.__texts["tab1_error_both_files"])

    def __show_tab1_result(self: "TabViewModel", is_submit_text: bool, is_submit_markdown: bool, result_text: str) -> None:
        if is_submit_text:
            st.success(self.__texts["tab1_success_formatted_text"])
            st.container(border=True).text_area(self.__texts["tab1_formatted_text"], result_text, height=500)
        elif is_submit_markdown:
            st.success(self.__texts["tab1_success_formatted_text"])
            st.container(border=True).markdown(result_text)

    def __show_tab1_error(self: "TabViewModel", first_error_message: Optional[str], second_error_message: Optional[str]) -> None:
        if first_error_message:
            st.error(first_error_message)
        if second_error_message:
            st.error(second_error_message)

    def show_tab2(
        self: "TabViewModel", is_submit: bool, parsed_config: Optional[str], filename: Optional[str], error_message: Optional[str]
    ) -> None:
        if not is_submit:
            return
        if error_message:
            st.error(error_message)
        elif parsed_config is None:
            st.warning(f"{self.__texts['tab2_error_debug_not_found']}")
        else:
            st.success(self.__texts["tab2_success_debug_config"])
            st.text_area(self.__texts["tab2_debug_config_text"], parsed_config, height=500)


def main() -> None:
    """Generate Streamlit web screens."""

    texts: Dict[str, str] = LANGUAGES["日本語"]
    st.session_state.update(
        {
            "tab1_result_content": st.session_state.get("tab1_result_content"),
            "tab2_result_content": st.session_state.get("tab2_result_content"),
        }
    )

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
        tab1_model = AppModel()
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

        tab1_model.load_config_file(st.session_state.get("tab1_config_file"), texts["tab1_error_toml_parse"])
        tab1_model.load_template_file(
            st.session_state.get("tab1_template_file"),
            texts["tab1_error_template_generate"],
            st.session_state.get("is_strict_undefined", True),
            st.session_state.get("is_remove_multiple_newline", True),
        )

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

        tab_view_model = TabViewModel(texts)
        tab_view_model.show_tab1(
            st.session_state.get("tab1_execute_text", False),
            st.session_state.get("tab1_execute_markdown", False),
            st.session_state.get("tab1_result_content", None),
            (st.session_state.get("tab1_error_config", None), st.session_state.get("tab1_error_template", None)),
        )

    with tab2:
        tab2_model = AppModel()
        tab2_row1_col1, _ = st.columns(2)
        with tab2_row1_col1.container(border=True):
            st.file_uploader(
                texts["tab2_upload_debug_config"],
                type=["toml", "yaml", "yml"],
                key="tab2_config_file",
            )
            tab2_model.load_config_file(st.session_state.get("tab2_config_file"), texts["tab2_error_debug_config"])
            st.session_state.update({"tab2_result_content": tab2_model.config_str})

        tab2_row2_col1, _, _ = st.columns(3)
        tab2_row2_col1.button(texts["tab2_generate_debug_config"], use_container_width=True, key="tab2_execute")
        st.session_state.update({"tab2_error_config": tab2_model.config_error_message})

        tab_view_model = TabViewModel(texts)
        tab_view_model.show_tab2(
            st.session_state.get("tab2_execute", False),
            st.session_state.get("tab2_result_content"),
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
