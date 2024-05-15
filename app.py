#! /usr/bin/env python
from datetime import datetime
from io import BytesIO
from typing import Dict, Optional

import streamlit as st

from features.command_render import GhostwriterRender
from features.config_parser import GhostwriterParser
from i11n import LANGUAGES


def parse_filename(filename: str, file_extension: str, is_append_timestamp: bool) -> str:
    """Parse filename with timestamp and extension."""
    suffix = f"_{datetime.today().strftime(r'%Y-%m-%d_%H%M%S')}" if is_append_timestamp else ""
    return f"{filename}{suffix}.{str(file_extension)}"


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

            config_data = None
            if config_file is not None:
                parser = GhostwriterParser(config_file)
                config_data = parser.parsed_dict
                if config_data is None:
                    st.error(f"{texts['error_toml_parse']}: {parser.error_message} in '{config_file.name}'")

        with row1_col2:
            template_file = st.container(border=True).file_uploader(texts["upload_template"], type=["jinja2", "j2"], key="template_file")

        row2_col1, row2_col2, row2_col3 = st.columns(3)
        with row2_col1:
            generate_text = st.button(texts["generate_text_button"], use_container_width=True)

        with row2_col2:
            generate_markdown = st.button(texts["generate_markdown_button"], use_container_width=True)

        with row2_col3:
            is_download_disabled = False if generate_text or generate_markdown else True

            st.download_button(
                texts["download_button"],
                formatted_text or "No data available",
                parse_filename(download_filename, download_file_ext, is_append_timestamp),  # type: ignore
                disabled=is_download_disabled,
                use_container_width=True,
            )

        if generate_text:
            generate_markdown = False
            if config_data is not None and template_file is not None:
                render = GhostwriterRender(template_file, config_data, is_strict_undefined)
                formatted_text = render.render_content
                if formatted_text:
                    st.success(texts["success_formatted_text"])
                    st.text_area(texts["formatted_text"], formatted_text, height=500)
                else:
                    st.error(f"{texts['error_template_generate']}: {render.error_message} in '{template_file.name}'")
            else:
                st.error(texts["error_both_files"])

        if generate_markdown:
            generate_text = False
            if config_data is not None and template_file is not None:
                render = GhostwriterRender(template_file, config_data, is_strict_undefined)
                formatted_text = render.render_content
                if formatted_text:
                    st.success(texts["success_formatted_text"])
                    st.container(border=True).markdown(formatted_text)
                else:
                    st.error(f"{texts['error_template_generate']}: {render.error_message} in '{template_file.name}'")
            else:
                st.error(texts["error_both_files"])

    with tab2:
        with st.container(border=True):
            debug_config_file: Optional[BytesIO] = st.file_uploader(
                texts["upload_config"],
                type=["toml", "yaml", "yml"],
                key="debug_config_file",
            )
            debug_config_text: Optional[str]

            if debug_config_file is not None:
                debug_parser = GhostwriterParser(debug_config_file)
                config_data = debug_parser.parsed_dict
                if config_data is None:
                    st.error(f"{texts['error_debug_config']}: {debug_parser.error_message}")
                debug_config_filename: str = debug_config_file.name
                debug_config_text = debug_parser.parsed_str
            else:
                config_data = None
                debug_config_text = None
                debug_config_filename = "None"

            generate_debug = st.button(texts["generate_debug_config"])

        if generate_debug:
            if debug_config_text is not None:
                st.success(texts["success_debug_config"])
                st.text_area(texts["debug_config_text"], debug_config_text, height=500)
            else:
                st.error(f"{texts['error_debug_config']} in '{debug_config_filename}'")


if __name__ == "__main__":
    main()
