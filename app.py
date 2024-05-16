#! /usr/bin/env python
from datetime import datetime
from io import BytesIO
from typing import Dict, Optional

import streamlit as st

from features.command_render import GhostwriterRender
from features.config_parser import GhostwriterParser
from i11n import LANGUAGES


def handle_config_file(config_file: Optional[BytesIO], texts: Dict[str, str]) -> None:
    if config_file is None:
        return None

    parser = GhostwriterParser()
    parser.load_config_file(config_file).parse()
    config_data = parser.parsed_dict

    if config_data is None:
        st.session_state.tab1_error_message = f"{texts['error_toml_parse']}: {parser.error_message} in '{config_file.name}'"
        return None

    st.session_state.config_data = config_data


def handle_template_file(template_file: Optional[BytesIO], texts: Dict[str, str]) -> None:
    config_data = st.session_state.config_data
    if not (template_file and config_data):
        return None

    render = GhostwriterRender(st.session_state.is_strict_undefined, st.session_state.is_remove_multiple_newline)
    render.load_template_file(template_file).apply_context(config_data)
    formatted_text = render.render_content

    if formatted_text is None:
        error_message = f"{texts['error_template_generate']}: {render.error_message} in '{template_file.name}'"
        st.session_state.tab1_error_message = error_message
        st.session_state.tab1_result_text = None
        return None

    st.session_state.tab1_result_text = formatted_text

    suffix = f"_{datetime.today().strftime(r'%Y-%m-%d_%H%M%S')}" if st.session_state.is_append_timestamp else ""
    st.session_state.download_full_filename = f"{st.session_state.download_filename}{suffix}.{str(st.session_state.download_file_ext)}"


def handle_debug_config_file(config_file: Optional[BytesIO], texts: Dict[str, str]) -> None:

    if config_file is None:
        st.session_state.tab2_error_message = f"{texts['error_not_found_debug_config']}"
        return None

    debug_parser = GhostwriterParser()
    debug_parser.load_config_file(config_file).parse()
    config_data = debug_parser.parsed_dict

    print(f"debug_parser.error_message: {debug_parser.error_message}")

    if config_data is None:
        st.session_state.tab2_error_message = f"{texts['error_debug_config']}: {debug_parser.error_message}"
        return None

    st.session_state.debug_config_text = debug_parser.parsed_str
    st.session_state.debug_config_filename = config_file.name


def show_tab1_result(is_submit_text: bool, is_submit_markdown: bool, texts: Dict[str, str]) -> None:

    if not (is_submit_text or is_submit_markdown):
        return None

    display_text = st.session_state.tab1_result_text

    if isinstance(st.session_state.tab1_error_message, str):
        st.error(st.session_state.tab1_error_message)
        return None

    if st.session_state.config_data is None or display_text is None:
        st.error(texts["error_both_files"])
        return None

    if is_submit_text:
        st.success(texts["success_formatted_text"])
        st.text_area(texts["formatted_text"], display_text, height=500)
        return None

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

    texts: Dict[str, str] = LANGUAGES["日本語"]
    st.session_state.config_file = None
    st.session_state.config_data = None
    st.session_state.template_file = None
    st.session_state.download_full_filename = None
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
        with row1_col1:
            with st.container(border=True):
                config_file = st.file_uploader(texts["upload_config"], type=["toml", "yaml", "yml"])
                handle_config_file(config_file, texts)

        with row1_col2:
            with st.container(border=True):
                template_file = st.file_uploader(texts["upload_template"], type=["jinja2", "j2"])
                handle_template_file(template_file, texts)

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

            st.download_button(
                label=texts["download_button"],
                data=st.session_state.tab1_result_text or "No data available",
                file_name=st.session_state.download_full_filename,
                disabled=is_download_disabled,
                use_container_width=True,
            )

        show_tab1_result(is_submit_text, is_submit_markdown, texts)

    with tab2:
        with st.container(border=True):
            debug_config_file = st.file_uploader(texts["upload_debug_config"], type=["toml", "yaml", "yml"])
            handle_debug_config_file(debug_config_file, texts)
            is_submit_debug = st.button(texts["generate_debug_config"])

            show_tab2_result(is_submit_debug, texts)


if __name__ == "__main__":
    main()
