import os
from io import BytesIO
from typing import Final, Optional

import streamlit as st
from box import Box

from features.core import GhostwriterCore
from features.transcoder import TextTranscoder
from i18n import LANGUAGES


class TabViewModel:
    def __init__(self: "TabViewModel", texts: Box) -> None:
        self.__texts: Final[Box] = texts
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
            st.warning(self.__texts.tab1.error_both_files)

    def __show_tab1_result(self: "TabViewModel", result_text: str) -> None:
        """Show tab1 success content."""

        if self.__execute_mode == 1:
            st.success(self.__texts.tab1.success_formatted_text)
            st.container(border=True).text_area(self.__texts.tab1.formatted_text, result_text, key="tab1_result_textarea", height=500)
        elif self.__execute_mode == 2:
            st.success(self.__texts.tab1.success_formatted_text)
            st.container(border=True).markdown(result_text)

    def __show_tab1_error(self: "TabViewModel", first_error_message: Optional[str], second_error_message: Optional[str]) -> None:
        """Show tab1 error content."""

        if first_error_message:
            st.error(first_error_message)
        if second_error_message:
            st.error(second_error_message)

    def show_tab2(self: "TabViewModel", parsed_config: Optional[str], error_message: Optional[str]) -> None:
        """Show tab2 response content."""

        if error_message:
            st.error(error_message)
        if self.__execute_mode < 3:
            return
        elif not parsed_config:
            st.warning(f"{self.__texts.tab2.error_debug_not_found}")
            return

        st.success(self.__texts.tab2.success_debug_config)
        st.text_area(self.__texts.tab2.debug_config_text, parsed_config, key="tab2_result_textarea", height=500)

    def show_tab4(self: "TabViewModel") -> None:
        samples_dir = "./assets/examples"
        for filename in sorted(os.listdir(samples_dir)):
            if not filename.endswith((".toml", ".yml", ".yaml", ".csv", ".j2", ".jinja2")):
                continue

            with open(os.path.join(samples_dir, filename), mode="rb") as file:
                text_file = TextTranscoder(BytesIO(file.read())).convert()
                if text_file is None:
                    continue

                st.text_area(label=filename, value=text_file.getvalue().decode("utf-8"), height=250)


def main() -> None:
    """Generate Streamlit web screens."""

    app_title: Final[str] = "Command ghostwriter"
    app_icon: Final[str] = ":ghost:"
    default_format_type: Final[int] = 3
    config_file_exts: Final[list] = ["toml", "yaml", "yml", "csv"]
    default_language = "日本語"

    texts: Final[Box] = Box(LANGUAGES[default_language])

    st.session_state.update(
        {
            "tab1_result_content": st.session_state.get("tab1_result_content"),
            "tab2_result_content": st.session_state.get("tab2_result_content"),
        }
    )

    st.set_page_config(page_title=app_title, page_icon=app_icon, layout="wide", initial_sidebar_state="expanded")
    st.title(f"{app_title} {app_icon}")

    with st.sidebar:
        st.write(texts.sidebar.welcome)
        st.expander(texts.sidebar.syntax_of_each_file, expanded=True).markdown(
            f"""
            - [toml syntax docs]({texts.sidebar.toml_syntax_doc})
            - [yaml syntax docs]({texts.sidebar.yaml_syntax_doc})
            - [jinja syntax docs]({texts.sidebar.jinja_syntax_doc})
            """
        )

    tabs = st.tabs(
        [
            ":memo: " + texts.tab1.menu_title,
            ":scroll: " + texts.tab2.menu_title,
            ":hammer_and_wrench: " + texts.tab3.menu_title,
            ":briefcase: " + texts.tab4.menu_title,
        ]
    )

    with tabs[0]:
        st.subheader(":memo: " + texts.tab1.subheader, divider="rainbow")
        tab1_row1 = st.columns(2)
        tab1_row2 = st.columns(3)

        tab1_row1[0].container(border=True).file_uploader(texts.tab1.upload_config, type=config_file_exts, key="tab1_config_file")
        tab1_row1[1].container(border=True).file_uploader(texts.tab1.upload_template, type=["jinja2", "j2"], key="tab1_template_file")

        tab1_row2[0].button(texts.tab1.generate_text_button, use_container_width=True, key="tab1_execute_text")
        tab1_row2[1].button(texts.tab1.generate_markdown_button, use_container_width=True, key="tab1_execute_markdown")

        tab1_model = GhostwriterCore(texts.tab1.error_toml_parse, texts.tab1.error_template_generate)
        tab1_model.load_config_file(
            st.session_state.get("tab1_config_file"),
            st.session_state.get("csv_rows_name", "csv_rows"),
            st.session_state.get("is_auto_transcoding", True),
        ).load_template_file(
            st.session_state.get("tab1_template_file"),
            st.session_state.get("is_auto_transcoding", True),
        ).apply(
            st.session_state.get("result_format_type", f"{default_format_type}: default"),
            st.session_state.get("is_strict_undefined", True),
        )

        st.session_state.update(
            {
                "tab1_result_content": tab1_model.formatted_text,
                "tab1_error_config": tab1_model.config_error_message,
                "tab1_error_template": tab1_model.template_error_message,
            }
        )

        tab1_row2[2].download_button(
            label=texts.tab1.download_button,
            data=tab1_model.get_download_content(st.session_state.get("download_encoding", "Shift_JIS")) or "No data available",
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
            st.session_state.get("tab1_result_content"),
            st.session_state.get("tab1_error_config"),
            st.session_state.get("tab1_error_template"),
        )

    with tabs[1]:
        st.subheader(":scroll: " + texts.tab2.subheader, divider="rainbow")
        tab2_row1 = st.columns(2)
        tab2_row2 = st.columns(3)

        tab2_row1[0].container(border=True).file_uploader(texts.tab2.upload_debug_config, type=config_file_exts, key="tab2_config_file")

        tab2_model = GhostwriterCore(texts.tab2.error_debug_config)
        tab2_model.load_config_file(
            st.session_state.get("tab2_config_file"),
            st.session_state.get("csv_rows_name", "csv_rows"),
            st.session_state.get("is_auto_transcoding", True),
        )

        tab2_row2[0].button(texts.tab2.generate_debug_config, use_container_width=True, key="tab2_execute")

        st.session_state.update(
            {
                "tab2_result_content": tab2_model.config_str,
                "tab2_error_config": tab2_model.config_error_message,
            }
        )

        tab2_view_model = TabViewModel(texts)
        tab2_view_model.set_execute_mode(
            st.session_state.get("tab1_execute_text", False),
            st.session_state.get("tab1_execute_markdown", False),
            st.session_state.get("tab2_execute", False),
        ).show_tab2(
            st.session_state.get("tab2_result_content"),
            st.session_state.get("tab2_error_config"),
        )

    with tabs[2]:
        st.subheader(":hammer_and_wrench: " + texts.tab3.subheader, divider="rainbow")
        tab3_row1 = st.columns(2)

        with tab3_row1[0].container(border=True):
            st.subheader(texts.tab3.subheader_input_file)
            st.container(border=True).text_input(texts.tab3.csv_rows_name, value="csv_rows", key="csv_rows_name")
            st.container(border=True).toggle(texts.tab3.strict_undefined, value=True, key="is_strict_undefined")
            st.container(border=True).toggle(texts.tab3.auto_encoding, value=True, key="is_auto_transcoding")

        with tab3_row1[1].container(border=True):
            st.subheader(texts.tab3.subheader_output_file)
            st.container(border=True).selectbox(
                texts.tab3.format_type,
                (
                    "0: " + texts.tab3.format_type_item0,
                    "1: " + texts.tab3.format_type_item1,
                    "2: " + texts.tab3.format_type_item2,
                    "3: " + texts.tab3.format_type_item3,
                    "4: " + texts.tab3.format_type_item4,
                ),
                index=default_format_type,
                key="result_format_type",
            )
            st.container(border=True).text_input(texts.tab3.download_filename, "command", key="download_filename")
            st.container(border=True).selectbox(texts.tab3.download_encoding, ["Shift_JIS", "utf-8"], key="download_encoding")
            st.container(border=True).toggle(texts.tab3.append_timestamp_filename, value=True, key="is_append_timestamp")
            st.container(border=True).radio(texts.tab3.download_file_extension, ["txt", "md"], horizontal=True, key="download_file_ext")

    with tabs[3]:
        st.subheader(":briefcase: " + texts.tab4.subheader, divider="rainbow")
        tab4_view_model = TabViewModel(texts)
        tab4_view_model.show_tab4()


if __name__ == "__main__":
    main()
