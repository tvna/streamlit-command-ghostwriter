from typing import Dict, Final, Optional

import streamlit as st

from features.core import GhostwriterCore
from i18n import LANGUAGES


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
    default_format_type: Final[int] = 3

    st.session_state.update({"tab1_result_content": st.session_state.get("tab1_result_content")})
    st.session_state.update({"tab2_result_content": st.session_state.get("tab2_result_content")})

    st.set_page_config(page_title="Command ghostwriter", page_icon=":ghost:", layout="wide", initial_sidebar_state="expanded")
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
            st.file_uploader(texts["tab1_upload_config"], type=["toml", "yaml", "yml", "csv"], key="tab1_config_file")

        with tab1_row1_col2.container(border=True):
            st.file_uploader(texts["tab1_upload_template"], type=["jinja2", "j2"], key="tab1_template_file")

        tab1_row2_col1, tab1_row2_col2, tab1_row2_col3 = st.columns(3)
        tab1_row2_col1.button(texts["tab1_generate_text_button"], use_container_width=True, key="tab1_execute_text")
        tab1_row2_col2.button(texts["tab1_generate_markdown_button"], use_container_width=True, key="tab1_execute_markdown")

        tab1_model = GhostwriterCore(texts["tab1_error_toml_parse"], texts["tab1_error_template_generate"])
        tab1_model.load_config_file(
            st.session_state.get("tab1_config_file"), st.session_state.get("csv_rows_name", "csv_rows")
        ).load_template_file(st.session_state.get("tab1_template_file")).apply_context(
            st.session_state.get("result_format_type", f"{default_format_type}: default"),
            st.session_state.get("is_strict_undefined", True),
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
        tab2_model = GhostwriterCore(texts["tab2_error_debug_config"])
        tab2_row1_col1, _ = st.columns(2)
        with tab2_row1_col1.container(border=True):
            st.file_uploader(texts["tab2_upload_debug_config"], type=["toml", "yaml", "yml", "csv"], key="tab2_config_file")

        tab2_model.load_config_file(st.session_state.get("tab2_config_file"), st.session_state.get("csv_rows_name", "csv_rows"))

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
            st.session_state.download_filename = st.container(border=True).text_input(texts["tab3_download_filename"], "command")
            st.session_state.is_append_timestamp = st.toggle(texts["tab3_append_timestamp_filename"], value=True)
            st.session_state.download_file_ext = st.container(border=True).radio(
                texts["tab3_download_file_extension"], ["txt", "md"], horizontal=True
            )
            st.session_state.is_strict_undefined = st.toggle(texts["tab3_strict_undefined"], value=True)
            st.session_state.result_format_type = st.container(border=True).selectbox(
                texts["tab3_format_type"],
                (
                    texts["tab3_format_type_item0"],
                    texts["tab3_format_type_item1"],
                    texts["tab3_format_type_item2"],
                    texts["tab3_format_type_item3"],
                    texts["tab3_format_type_item4"],
                ),
                index=default_format_type,
            )
            st.session_state.csv_rows_name = st.container(border=True).text_input(texts["tab3_csv_rows_name"], "csv_rows")


if __name__ == "__main__":
    main()
