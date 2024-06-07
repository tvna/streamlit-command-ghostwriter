#! /usr/bin/env python

# 言語リソース
LANGUAGES = {
    "日本語": {
        "welcome": """
        このアプリケーションでは、設定ファイル(toml/yaml)とJinjaテンプレートファイルをアップロードして、インフラ構築コマンドなどのテキスト整形ができます。

        ファイルをアップロードして、「テキスト整形の実行」をクリックして結果を確認してください。
        """,
        "advanced_option": "詳細オプション",
        "download_filename": "ダウンロード時のファイル名",
        "download_file_extension": "ダウンロード時のファイル拡張子",
        "append_timestamp_filename": "ファイル名の末尾にタイプスタンプを付与",
        "strict_undefined": "テンプレートの変数チェック厳格化",
        "remove_multiple_newline": "整形後の余分な改行を削除",
        "syntax_of_each_file": "各ファイルの構文",
        "toml_syntax_doc": "https://toml.io/ja/v1.0.0",
        "yaml_syntax_doc": "https://docs.ansible.com/ansible/2.9_ja/reference_appendices/YAMLSyntax.html",
        "jinja_syntax_doc": "https://jinja.palletsprojects.com/en/3.1.x/templates/",
        "tab_convert_text": "テキスト整形",
        "tab_debug_config": "設定デバッグ",
        "upload_config": "テキスト整形の設定ファイルをアップロード",
        "upload_debug_config": "デバッグする設定ファイルをアップロード",
        "upload_template": "テキスト整形のJinjaテンプレートファイルをアップロード",
        "generate_text_button": "テキスト整形の実行",
        "generate_markdown_button": "Markdown整形を実行",
        "generate_debug_config": "設定ファイル解析の表示",
        "download_button": "ダウンロード",
        "formatted_text": "テキスト整形の出力結果",
        "debug_config_text": "設定ファイルの解析結果",
        "success_formatted_text": "テキスト整形に成功",
        "success_debug_config": "設定ファイル解析に成功",
        "error_toml_parse": "設定ファイルの読み込みに失敗",
        "error_template_generate": "Jinjaテンプレートの読み込みに失敗",
        "error_both_files": "テキスト整形に必要な全ファイルが揃っていません",
        "error_debug_config": "設定ファイルの読み込みに失敗",
    },
}
