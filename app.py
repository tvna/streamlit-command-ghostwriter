#! /usr/bin/env python
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, Optional

import streamlit as st

from features.command_render import GhostwriterRender
from features.config_parser import GhostwriterParser
from i11n import LANGUAGES


def handle_config_file(config_file: Optional[BytesIO], texts: Dict[str, str]) -> Optional[Dict[str, Any]]:
    if config_file is None:
        return None

    parser = GhostwriterParser()
    parser.load_config_file(config_file).parse()
    config_data = parser.parsed_dict

    if config_data is None:
        st.error(f"{texts['error_toml_parse']}: {parser.error_message} in '{config_file.name}'")
        return None

    return config_data


def handle_template_file(
    template_file: Optional[BytesIO], config_data: Optional[Dict[str, Any]], is_strict_undefined: bool, texts: Dict[str, str]
) -> Optional[str]:
    if template_file is None:
        return None

    render = GhostwriterRender(is_strict_undefined)
    render.load_template_file(template_file).apply_context(config_data)
    formatted_text = render.render_content

    if formatted_text is None:
        st.error(f"{texts['error_template_generate']}: {render.error_message} in '{template_file.name}'")
        return None

    if not (config_data or template_file):
        st.error(texts["error_both_files"])
        return None

    return formatted_text


def display_formatted_text(is_submit_text: bool, is_submit_markdown: bool, display_text: Optional[str], texts: Dict[str, str]) -> None:

    if not (is_submit_text or is_submit_markdown):
        return None

    if display_text is None:
        return None

    if is_submit_text:
        st.success(texts["success_formatted_text"])
        st.text_area(texts["formatted_text"], display_text, height=500)
        return None

    if is_submit_markdown:
        st.success(texts["success_formatted_text"])
        st.container(border=True).markdown(display_text)


def parse_filename(filename: str, file_extension: str, is_append_timestamp: bool) -> str:
    """Parse filename with timestamp and extension."""
    suffix = f"_{datetime.today().strftime(r'%Y-%m-%d_%H%M%S')}" if is_append_timestamp else ""
    return f"{filename}{suffix}.{str(file_extension)}"


def handle_debug_config_file(config_file: Optional[BytesIO], texts: Dict[str, str]) -> tuple[Optional[str], Optional[str]]:

    config_text: Optional[str] = None
    config_filename: Optional[str] = None

    if config_file is None:
        return config_text, config_filename

    debug_parser = GhostwriterParser()
    debug_parser.load_config_file(config_file)
    config_data = debug_parser.parsed_dict

    if config_data is None:
        st.error(f"{texts['error_debug_config']}: {debug_parser.error_message}")
        return config_text, config_filename

    return debug_parser.parsed_str, config_file.name


def main() -> None:
    """Generate Streamlit web screens."""

    texts: Dict[str, str] = LANGUAGES["日本語"]

    st.set_page_config(page_title="Command ghostwriter", page_icon=":ghost:", layout="wide", initial_sidebar_state="expanded")
    st.title("Command ghostwriter :ghost:")
    formatted_text: Optional[str] = None

    with st.sidebar:
        st.write(texts["welcome"])
        with st.expander(texts["advanced_option"], expanded=False):
            download_filename = st.text_input(texts["download_filename"], "command")
            is_append_timestamp = st.toggle(texts["append_timestamp_filename"], value=True)
            download_file_ext = st.radio(texts["download_file_extension"], ["txt", "md"])
            is_strict_undefined = st.toggle(texts["strict_undefined"], value=True)
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
            config_file = st.container(border=True).file_uploader(texts["upload_config"], type=["toml", "yaml", "yml"], key="config_file")
            config_data = handle_config_file(config_file, texts)

        with row1_col2:
            template_file = st.container(border=True).file_uploader(texts["upload_template"], type=["jinja2", "j2"], key="template_file")

        row2_col1, row2_col2, row2_col3 = st.columns(3)
        with row2_col1:
            is_submit_text = st.button(texts["generate_text_button"], use_container_width=True)

        with row2_col2:
            is_submit_markdown = st.button(texts["generate_markdown_button"], use_container_width=True)

        with row2_col3:
            is_download_disabled = False if is_submit_text or is_submit_markdown else True

            st.download_button(
                texts["download_button"],
                formatted_text or "No data available",
                parse_filename(download_filename, download_file_ext, is_append_timestamp),  # type: ignore
                disabled=is_download_disabled,
                use_container_width=True,
            )

        formatted_text = handle_template_file(template_file, config_data, is_strict_undefined, texts)
        display_formatted_text(is_submit_text, is_submit_markdown, formatted_text, texts)

    with tab2:
        with st.container(border=True):
            debug_config_file = st.file_uploader(texts["upload_config"], type=["toml", "yaml", "yml"], key="debug_config_file")
            debug_config_text, debug_config_filename = handle_debug_config_file(debug_config_file, texts)
            generate_debug = st.button(texts["generate_debug_config"])

            if generate_debug:
                if debug_config_text is not None:
                    st.success(texts["success_debug_config"])
                    st.text_area(texts["debug_config_text"], debug_config_text, height=500)
                else:
                    st.error(f"{texts['error_debug_config']} in '{debug_config_filename}'")


if __name__ == "__main__":
    main()
