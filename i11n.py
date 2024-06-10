#! /usr/bin/env python

# 言語リソース
LANGUAGES = {
    "日本語": {
        "sidebar_welcome": """
        このアプリケーションでは、設定ファイル(toml/yaml)とJinjaテンプレートファイルをアップロードして、インフラ構築コマンドなどのテキスト整形ができます。

        ファイルをアップロードして、「テキスト整形の実行」をクリックして結果を確認してください。
        """,
        "sidebar_syntax_of_each_file": "各ファイルの構文",
        "sidebar_toml_syntax_doc": "https://toml.io/ja/v1.0.0",
        "sidebar_yaml_syntax_doc": "https://docs.ansible.com/ansible/2.9_ja/reference_appendices/YAMLSyntax.html",
        "sidebar_jinja_syntax_doc": "https://jinja.palletsprojects.com/en/3.1.x/templates/",
        "tab1_menu_convert_text": "テキスト整形",
        "tab1_upload_config": "テキスト整形の設定ファイルをアップロード",
        "tab2_upload_debug_config": "デバッグする設定ファイルをアップロード",
        "tab1_upload_template": "テキスト整形のJinjaテンプレートファイルをアップロード",
        "tab1_generate_text_button": "テキスト整形の実行",
        "tab1_generate_markdown_button": "Markdown整形を実行",
        "tab1_download_button": "ダウンロード",
        "tab1_formatted_text": "テキスト整形の出力結果",
        "tab1_success_formatted_text": "テキスト整形に成功",
        "tab1_success_debug_config": "設定ファイル解析に成功",
        "tab1_error_toml_parse": "設定ファイルの読み込みに失敗",
        "tab1_error_template_generate": "Jinjaテンプレートの読み込みに失敗",
        "tab1_error_both_files": "テキスト整形に必要な全ファイルが揃っていません",
        "tab1_error_debug_not_found": "設定ファイルが読み込まれていません",
        "tab2_menu_debug_config": "設定デバッグ",
        "tab2_debug_config_text": "設定ファイルの解析結果",
        "tab2_error_debug_config": "設定ファイルの読み込みに失敗",
        "tab2_generate_debug_config": "設定ファイル解析の表示",
        "tab3_menu_advanced_option": "詳細オプション",
        "tab3_download_filename": "ダウンロード時のファイル名",
        "tab3_download_file_extension": "ダウンロード時のファイル拡張子",
        "tab3_append_timestamp_filename": "ファイル名の末尾にタイプスタンプを付与",
        "tab3_strict_undefined": "テンプレートの変数チェック厳格化",
        "tab3_remove_multiple_newline": "整形後の余分な改行を削除",
        "tab3_header_generate_text": "### テキスト整形",
    },
}
