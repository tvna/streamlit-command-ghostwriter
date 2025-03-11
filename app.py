import os
from enum import Enum
from io import BytesIO
from typing import Any, Dict, Final, List, Optional

import streamlit as st
import toml
import yaml
from box import Box
from pydantic import BaseModel, PrivateAttr

from features.core import AppCore
from features.transcoder import TextTranscoder
from i18n import LANGUAGES


class ExecuteMode(Enum):
    """実行モードを定義する列挙型。"""

    nothing = 0
    parsed_text = 1
    parsed_markdown = 2
    debug_visual = 3
    debug_toml = 4
    debug_yaml = 5


class TabViewModel(BaseModel):
    """タブの表示モデルを定義するクラス。"""

    __texts_dict: Box = PrivateAttr()
    __execute_mode: ExecuteMode = PrivateAttr(default=ExecuteMode.nothing)

    def __init__(self: "TabViewModel", texts: Box) -> None:
        """
        TabViewModelの初期化メソッド。

        Args:
            texts (Box): テキストデータを含むBoxオブジェクト。
        """
        super().__init__()
        self.__texts_dict = texts

    @property
    def __texts(self: "TabViewModel") -> Box:
        """テキストデータを取得します。

        Returns:
            Box: テキストデータ。
        """
        return self.__texts_dict

    def set_execute_mode(
        self: "TabViewModel",
        is_parsed_text: bool,
        is_parsed_markdown: bool,
        is_debug_visual: bool,
        is_debug_toml: bool,
        is_debug_yaml: bool,
    ) -> "TabViewModel":
        """実行モードを設定します。

        Args:
            is_parsed_text (bool): パースされたテキストモードを有効にするかどうか。
            is_parsed_markdown (bool): パースされたMarkdownモードを有効にするかどうか。
            is_debug_visual (bool): デバッグビジュアルモードを有効にするかどうか。
            is_debug_toml (bool): デバッグTOMLモードを有効にするかどうか。
            is_debug_yaml (bool): デバッグYAMLモードを有効にするかどうか。

        Returns:
            TabViewModel: 自身のインスタンス。
        """
        mode_mapping = {
            is_parsed_text: ExecuteMode.parsed_text,
            is_parsed_markdown: ExecuteMode.parsed_markdown,
            is_debug_visual: ExecuteMode.debug_visual,
            is_debug_toml: ExecuteMode.debug_toml,
            is_debug_yaml: ExecuteMode.debug_yaml,
        }

        for condition, mode in mode_mapping.items():
            if condition:
                self.__execute_mode = mode
                return self

        self.__execute_mode = ExecuteMode.nothing
        return self

    def show_tab1(
        self: "TabViewModel", result: Optional[str], first_error_message: Optional[str], second_error_message: Optional[str]
    ) -> None:
        """タブ1のレスポンスコンテンツを表示します。

        Args:
            result (Optional[str]): 表示する結果。
            first_error_message (Optional[str]): 最初のエラーメッセージ。
            second_error_message (Optional[str]): 2番目のエラーメッセージ。
        """
        if first_error_message or second_error_message:
            self.__show_tab1_error(first_error_message, second_error_message)
            return

        if self.__execute_mode not in (ExecuteMode.parsed_text, ExecuteMode.parsed_markdown):
            return

        if result is None:
            st.warning(self.__texts.tab1.error_both_files)
            return

        match self.__execute_mode:
            case ExecuteMode.parsed_text:
                st.success(self.__texts.tab1.success_formatted_text)
                st.container(border=True).text_area(self.__texts.tab1.formatted_text, result, key="tab1_result_textarea", height=500)

            case ExecuteMode.parsed_markdown:
                st.success(self.__texts.tab1.success_formatted_text)
                st.container(border=True).markdown(result)

    def __show_tab1_error(self: "TabViewModel", first_error_message: Optional[str], second_error_message: Optional[str]) -> None:
        """タブ1のエラーコンテンツを表示します。

        Args:
            first_error_message (Optional[str]): 最初のエラーメッセージ。
            second_error_message (Optional[str]): 2番目のエラーメッセージ。
        """
        if first_error_message:
            st.error(first_error_message)
        if second_error_message:
            st.error(second_error_message)

    def show_tab2(self: "TabViewModel", parsed_config: Optional[Dict[str, Any]], error_message: Optional[str]) -> None:
        """タブ2のレスポンスコンテンツを表示します。

        Args:
            parsed_config (Optional[Dict[str, Any]]): パースされた設定。
            error_message (Optional[str]): エラーメッセージ。
        """
        if error_message:
            st.error(error_message)

        if self.__execute_mode not in (ExecuteMode.debug_visual, ExecuteMode.debug_toml, ExecuteMode.debug_yaml):
            return

        if parsed_config is None:
            st.warning(f"{self.__texts.tab2.error_debug_not_found}")
            return

        st.success(self.__texts.tab2.success_debug_config)

        match self.__execute_mode:
            case ExecuteMode.debug_visual:
                st.container(border=True).json(parsed_config)

            case ExecuteMode.debug_toml:
                toml_config = toml.dumps(parsed_config)
                st.text_area(self.__texts.tab2.debug_config_text, toml_config, key="tab2_result_textarea", height=500)

            case ExecuteMode.debug_yaml:
                yaml_config = yaml.dump(parsed_config, default_flow_style=False, allow_unicode=True, indent=8)
                st.text_area(self.__texts.tab2.debug_config_text, yaml_config, key="tab2_result_textarea", height=500)

    def show_tab4(self: "TabViewModel") -> None:
        """タブ4のサンプルファイルを表示します。"""
        samples_dir = "./assets/examples"
        for filename in sorted(os.listdir(samples_dir)):
            if not filename.endswith((".toml", ".yml", ".yaml", ".csv", ".j2", ".jinja2")):
                continue

            with open(os.path.join(samples_dir, filename), mode="rb") as file:
                bytes_data = TextTranscoder(BytesIO(file.read())).convert()
                if isinstance(bytes_data, BytesIO):
                    content = bytes_data.getvalue().decode("utf-8")
                    st.text_area(label=filename, value=content, height=250)


def main() -> None:
    """StreamlitのWeb画面を生成します。"""

    app_title: Final[str] = "Command ghostwriter"
    app_icon: Final[str] = ":ghost:"
    default_format_type: Final[int] = 3
    config_file_exts: Final[List[str]] = ["toml", "yaml", "yml", "csv"]
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

        tab1_model = AppCore(texts.tab1.error_toml_parse, texts.tab1.error_template_generate)
        tab1_model.load_config_file(
            st.session_state.get("tab1_config_file"),
            st.session_state.get("csv_rows_name", "csv_rows"),
            st.session_state.get("enable_auto_transcoding", True),
            st.session_state.get("enable_fill_nan", True),
            st.session_state.get("fill_nan_with", "#"),
        ).load_template_file(
            st.session_state.get("tab1_template_file"),
            st.session_state.get("enable_auto_transcoding", True),
        ).apply(
            st.session_state.get("result_format_type", f"{default_format_type}: default"),
            st.session_state.get("strict_undefined", True),
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
            st.session_state.get("tab2_execute_visual", False),
            st.session_state.get("tab2_execute_toml", False),
            st.session_state.get("tab2_execute_yaml", False),
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

        tab2_model = AppCore(texts.tab2.error_debug_config)
        tab2_model.load_config_file(
            st.session_state.get("tab2_config_file"),
            st.session_state.get("csv_rows_name", "csv_rows"),
            st.session_state.get("enable_auto_transcoding", True),
            st.session_state.get("enable_fill_nan", True),
            st.session_state.get("fill_nan_with", "#"),
        )

        tab2_row2[0].button(texts.tab2.generate_visual_button, use_container_width=True, key="tab2_execute_visual")
        tab2_row2[1].button(texts.tab2.generate_toml_button, use_container_width=True, key="tab2_execute_toml")
        tab2_row2[2].button(texts.tab2.generate_yaml_button, use_container_width=True, key="tab2_execute_yaml")

        st.session_state.update(
            {
                "tab2_result_content": tab2_model.config_dict,
                "tab2_error_config": tab2_model.config_error_message,
            }
        )

        tab2_view_model = TabViewModel(texts)
        tab2_view_model.set_execute_mode(
            st.session_state.get("tab1_execute_text", False),
            st.session_state.get("tab1_execute_markdown", False),
            st.session_state.get("tab2_execute_visual", False),
            st.session_state.get("tab2_execute_toml", False),
            st.session_state.get("tab2_execute_yaml", False),
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
            with st.container(border=True):
                st.toggle(texts.tab3.enable_fill_nan, value=True, key="enable_fill_nan")
                st.text_input(texts.tab3.fill_nan_with, value="#", key="fill_nan_with")
            st.container(border=True).toggle(texts.tab3.strict_undefined, value=True, key="strict_undefined")
            st.container(border=True).toggle(texts.tab3.auto_transcoding, value=True, key="enable_auto_transcoding")

        with tab3_row1[1].container(border=True):
            st.subheader(texts.tab3.subheader_output_file)
            with st.container(border=True):
                st.selectbox(
                    texts.tab3.format_type,
                    (x for x in texts.tab3.format_type_items),
                    index=default_format_type,
                    format_func=lambda x: f"{x!s}: {texts.tab3.format_type_items[x]}",
                    key="result_format_type",
                )
                st.selectbox(texts.tab3.download_encoding, ["Shift_JIS", "utf-8"], key="download_encoding")
            with st.container(border=True):
                st.text_input(texts.tab3.download_filename, "command", key="download_filename")
                st.toggle(texts.tab3.append_timestamp_filename, value=True, key="is_append_timestamp")
                st.radio(texts.tab3.download_file_extension, ["txt", "md"], horizontal=True, key="download_file_ext")

    with tabs[3]:
        st.subheader(":briefcase: " + texts.tab4.subheader, divider="rainbow")
        tab4_view_model = TabViewModel(texts)
        tab4_view_model.show_tab4()


if __name__ == "__main__":
    main()
