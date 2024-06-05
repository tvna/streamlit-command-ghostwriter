#! /usr/bin/env python
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, Optional

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
        self: "AppModel", template_file: Optional[BytesIO], error_header: str, is_strict_undefined: bool, is_clear_dup_lines: bool
    ) -> bool:
        config_data = self.__config_dict
        if config_data is None:
            return False

        if not (template_file and hasattr(template_file, "name")):
            return False

        render = GhostwriterRender(is_strict_undefined, is_clear_dup_lines)
        render.load_template_file(template_file).apply_context(config_data)

        if isinstance(render.error_message, str):
            self.__template_error_message = f"{error_header}: {render.error_message} in '{template_file.name}'"
            return False

        self.__formatted_text = render.render_content

        return True

    def get_download_filename(
        self: "AppModel", download_filename: Optional[str], download_file_ext: Optional[str], is_append_timestamp: bool
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


def show_tab1_result(
    is_submit_text: bool,
    is_submit_markdown: bool,
    texts: Dict[str, str],
    result_text: Optional[str],
    first_error_message: Optional[str],
    second_error_message: Optional[str],
) -> None:

    if isinstance(first_error_message, str):
        st.error(first_error_message)
        return None

    if isinstance(second_error_message, str):
        st.error(second_error_message)
        return None

    if not (is_submit_text or is_submit_markdown):
        return None

    if not result_text:
        st.error(texts["error_both_files"])
        return None

    # display raw text
    if is_submit_text:
        st.success(texts["success_formatted_text"])
        st.text_area(texts["formatted_text"], result_text, height=500)
        return None

    # display markdown document
    if is_submit_markdown:
        st.success(texts["success_formatted_text"])
        st.container(border=True).markdown(result_text)
        return None


def show_tab2_result(
    is_submit: bool, texts: Dict[str, str], parsed_config: Optional[str], filename: Optional[str], error_message: Optional[str]
) -> None:

    if not is_submit:
        return None

    if error_message:
        st.error(error_message)
        return None

    if parsed_config is None:
        st.error(f"{texts['error_debug_config']} in '{filename}'")
        return None

    st.success(texts["success_debug_config"])
    st.text_area(texts["debug_config_text"], parsed_config, height=500)


def main() -> None:
    """Generate Streamlit web screens."""

    texts: Dict[str, str] = LANGUAGES["日本語"]

    st.set_page_config(page_title="Command ghostwriter", page_icon=":ghost:", layout="wide", initial_sidebar_state="expanded")
    st.title("Command ghostwriter :ghost:")

    with st.sidebar:
        st.write(texts["welcome"])

        with st.expander(texts["syntax_of_each_file"], expanded=True):
            st.markdown(
                f"""
            - [toml syntax docs]({texts["toml_syntax_doc"]})
            - [yaml syntax docs]({texts["yaml_syntax_doc"]})
            - [jinja syntax docs]({texts["jinja_syntax_doc"]})
            """
            )

    tab1, tab2, tab3 = st.tabs([texts["tab_convert_text"], texts["tab_debug_config"], "詳細設定"])

    with tab1:
        tab1_model = AppModel()
        tab1_row1_col1, tab1_row1_col2 = st.columns(2)
        with tab1_row1_col1.container(border=True):
            st.file_uploader(texts["upload_config"], type=["toml", "yaml", "yml"], key="tab1_config_file")

        with tab1_row1_col2.container(border=True):
            st.file_uploader(texts["upload_template"], type=["jinja2", "j2"], key="tab1_template_file")

        tab1_row2_col1, tab1_row2_col2, tab1_row2_col3 = st.columns(3)
        tab1_row2_col1.button(texts["generate_text_button"], use_container_width=True, key="tab1_execute_text")
        tab1_row2_col2.button(texts["generate_markdown_button"], use_container_width=True, key="tab1_execute_markdown")
        tab1_row2_col3.download_button(
            label=texts["download_button"],
            data=tab1_model.formatted_text or "No data available",
            file_name=tab1_model.get_download_filename(
                st.session_state.get("download_filename", "command"),
                st.session_state.get("download_file_ext", "txt"),
                st.session_state.get("is_append_timestamp", True),
            ),
            disabled=False if tab1_model.is_ready_formatted else True,
            use_container_width=True,
        )

        tab1_model.load_config_file(st.session_state.get("tab1_config_file"), texts["error_toml_parse"])
        tab1_model.load_template_file(
            st.session_state.get("tab1_template_file"),
            texts["error_template_generate"],
            st.session_state.get("is_strict_undefined", True),
            st.session_state.get("is_remove_multiple_newline", True),
        )
        show_tab1_result(
            st.session_state.get("tab1_execute_text", False),
            st.session_state.get("tab1_execute_markdown", False),
            texts,
            tab1_model.formatted_text,
            tab1_model.config_error_message,
            tab1_model.template_error_message,
        )

    with tab2:
        tab2_model = AppModel()
        tab2_row1_col1, _ = st.columns(2)
        with tab2_row1_col1.container(border=True):
            st.file_uploader(texts["upload_debug_config"], type=["toml", "yaml", "yml"], key="tab2_config_file")
            tab2_model.load_config_file(st.session_state.get("tab2_config_file"), texts["error_debug_config"])
            if isinstance(tab2_model.config_str, str):
                st.session_state.update({"tab2_result": tab2_model.config_str})

        tab2_row2_col1, _, _ = st.columns(3)
        tab2_row2_col1.button(texts["generate_debug_config"], use_container_width=True, key="tab2_execute")

        show_tab2_result(
            st.session_state.get("tab2_execute", False),
            texts,
            st.session_state.get("tab2_result"),
            tab2_model.get_uploaded_filename(st.session_state.get("tab2_config_file")),
            tab2_model.config_error_message,
        )

    with tab3:
        tab3_row1_col1, _ = st.columns(2)
        with tab3_row1_col1.container(border=True):
            st.session_state.download_filename = st.text_input(texts["download_filename"], "command")
            st.session_state.is_append_timestamp = st.toggle(texts["append_timestamp_filename"], value=True)
            st.session_state.download_file_ext = st.radio(texts["download_file_extension"], ["txt", "md"])
            st.session_state.is_strict_undefined = st.toggle(texts["strict_undefined"], value=True)
            st.session_state.is_remove_multiple_newline = st.toggle(texts["remove_multiple_newline"], value=True)


if __name__ == "__main__":
    main()
