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
        pass

    def handle_config_file(
        self: "AppModel", config_file: Optional[BytesIO], error_message: str
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        if config_file is None:
            return None, None

        parser = GhostwriterParser()
        parser.load_config_file(config_file).parse()
        config_data = parser.parsed_dict

        if config_data is None or isinstance(parser.error_message, str):
            return None, f"{error_message}: {parser.error_message} in '{config_file.name}'"

        return config_data, None

    def handle_template_file(
        self: "AppModel",
        template_file: Optional[BytesIO],
        config_data: Optional[Dict[str, Any]],
        error_message: str,
        is_strict_undefined: bool,
        is_remove_multiple_newline: bool,
    ) -> Tuple[Optional[str], Optional[str]]:
        if not (template_file and config_data):
            return None, None

        render = GhostwriterRender(is_strict_undefined, is_remove_multiple_newline)
        is_successful = render.load_template_file(template_file).apply_context(config_data)
        formatted_text = render.render_content

        if not is_successful or formatted_text is None or isinstance(render.error_message, str):
            return None, f"{error_message}: {render.error_message} in '{template_file.name}'"

        return formatted_text, None

    def init_download_filename(
        self: "AppModel", download_filename: Optional[str], download_file_ext: Optional[str], is_append_timestamp: bool
    ) -> Optional[str]:

        if download_filename is None or download_file_ext is None:
            return None

        suffix = f"_{datetime.today().strftime(r'%Y-%m-%d_%H%M%S')}" if is_append_timestamp else ""
        filename = f"{download_filename}{suffix}.{str(download_file_ext)}"

        return filename

    def handle_debug_config_file(
        self: "AppModel", config_file: Optional[BytesIO], error_message: str
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:

        if config_file is None:
            return None, None, None

        debug_parser = GhostwriterParser()
        debug_parser.load_config_file(config_file).parse()
        config_text = debug_parser.parsed_str

        if config_text is None or isinstance(debug_parser.error_message, str):
            return None, None, f"{error_message}: {debug_parser.error_message}"

        return config_text, config_file.name, None


def show_tab1_result(is_submit_text: bool, is_submit_markdown: bool, texts: Dict[str, str]) -> None:

    if not (is_submit_text or is_submit_markdown):
        return None

    if isinstance(st.session_state.tab1_error_message, str):
        st.error(st.session_state.tab1_error_message)
        return None

    display_text = st.session_state.tab1_result_text
    if st.session_state.config_data is None or display_text is None:
        st.error(texts["error_both_files"])
        return None

    # display raw text
    if is_submit_text:
        st.success(texts["success_formatted_text"])
        st.text_area(texts["formatted_text"], display_text, height=500)
        return None

    # display markdown document
    st.success(texts["success_formatted_text"])
    st.container(border=True).markdown(display_text)


def show_tab2_result(is_submit: bool, texts: Dict[str, str]) -> None:

    if not is_submit:
        return None

    debug_config_text = st.session_state.debug_config_text

    if isinstance(st.session_state.tab2_error_message, str):
        st.error(st.session_state.tab2_error_message)
        return None

    if debug_config_text is None:
        st.error(f"{texts['error_debug_config']} in '{st.session_state.debug_config_filename}'")
        return None

    st.success(texts["success_debug_config"])
    st.text_area(texts["debug_config_text"], debug_config_text, height=500)


def main() -> None:
    """Generate Streamlit web screens."""

    model = AppModel()
    texts: Dict[str, str] = LANGUAGES["日本語"]
    st.session_state.config_file = None
    st.session_state.config_data = None
    st.session_state.template_file = None
    st.session_state.debug_config_text = None
    st.session_state.debug_config_filename = None
    st.session_state.tab1_result_text = None
    st.session_state.tab2_result_text = None
    st.session_state.tab1_error_message = None
    st.session_state.tab2_error_message = None

    st.set_page_config(page_title="Command ghostwriter", page_icon=":ghost:", layout="wide", initial_sidebar_state="expanded")
    st.title("Command ghostwriter :ghost:")

    with st.sidebar:
        st.write(texts["welcome"])

        with st.expander(texts["advanced_option"], expanded=False):
            st.session_state.download_filename = st.text_input(texts["download_filename"], "command")
            st.session_state.is_append_timestamp = st.toggle(texts["append_timestamp_filename"], value=True)
            st.session_state.download_file_ext = st.radio(texts["download_file_extension"], ["txt", "md"])
            st.session_state.is_strict_undefined = st.toggle(texts["strict_undefined"], value=True)
            st.session_state.is_remove_multiple_newline = st.toggle(texts["remove_multiple_newline"], value=True)

        with st.expander(texts["syntax_of_each_file"], expanded=False):
            st.markdown(
                f"""
            - [toml syntax docs]({texts["toml_syntax_doc"]})
            - [yaml syntax docs]({texts["yaml_syntax_doc"]})
            - [jinja syntax docs]({texts["jinja_syntax_doc"]})
            """
            )

    tab1, tab2 = st.tabs([texts["tab_convert_text"], texts["tab_debug_config"]])

    with tab1:
        row1_col1, row1_col2 = st.columns(2)
        with row1_col1.container(border=True):
            config_file = st.file_uploader(texts["upload_config"], type=["toml", "yaml", "yml"])
            config_data, error_message = model.handle_config_file(config_file, texts["error_toml_parse"])
            st.session_state.update({"config_data": config_data, "tab1_error_message": error_message})

        with row1_col2.container(border=True):
            template_file = st.file_uploader(texts["upload_template"], type=["jinja2", "j2"])
            result, error_message = model.handle_template_file(
                template_file,
                st.session_state.get("config_data"),
                texts["error_template_generate"],
                st.session_state.is_strict_undefined,
                st.session_state.is_remove_multiple_newline,
            )
            st.session_state.update({"tab1_result_text": result, "tab1_error_message": error_message})

        row2_col1, row2_col2, row2_col3 = st.columns(3)
        with row2_col1:
            is_submit_text = st.button(texts["generate_text_button"], use_container_width=True)

        with row2_col2:
            is_submit_markdown = st.button(texts["generate_markdown_button"], use_container_width=True)

        with row2_col3:
            if is_submit_text or is_submit_markdown:
                is_download_disabled = False
            else:
                is_download_disabled = True

            download_filename = model.init_download_filename(
                st.session_state.download_filename,
                st.session_state.download_file_ext,
                st.session_state.is_append_timestamp,
            )

            st.download_button(
                label=texts["download_button"],
                data=st.session_state.tab1_result_text or "No data available",
                file_name=download_filename,
                disabled=is_download_disabled,
                use_container_width=True,
            )

        show_tab1_result(is_submit_text, is_submit_markdown, texts)

    with tab2.container(border=True):
        debug_config_file = st.file_uploader(texts["upload_debug_config"], type=["toml", "yaml", "yml"])
        result, debug_config_filename, error_message = model.handle_debug_config_file(debug_config_file, texts["error_debug_config"])
        st.session_state.update(
            {"debug_config_text": result, "debug_config_filename": debug_config_filename, "tab2_error_message": error_message}
        )
        is_submit_debug = st.button(texts["generate_debug_config"])

        show_tab2_result(is_submit_debug, texts)


if __name__ == "__main__":
    main()
