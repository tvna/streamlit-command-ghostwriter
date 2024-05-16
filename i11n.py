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
        "syntax_of_each_file": "各ファイルの構文",
        "toml_syntax_doc": "https://toml.io/ja/v1.0.0",
        "yaml_syntax_doc": "https://docs.ansible.com/ansible/2.9_ja/reference_appendices/YAMLSyntax.html",
        "jinja_syntax_doc": "https://jinja.palletsprojects.com/en/3.1.x/templates/",
        "tab_convert_text": "テキスト整形",
        "tab_debug_config": "設定デバッグ",
        "upload_config": "設定ファイルをアップロード",
        "upload_debug_config": "設定ファイル(解析用)をアップロード",
        "upload_template": "テンプレートファイルをアップロード",
        "generate_text_button": "テキスト整形の実行",
        "generate_markdown_button": "Markdown整形を実行",
        "generate_debug_config": "設定ファイル解析の表示",
        "download_button": "ダウンロード",
        "formatted_text": "テキスト整形の出力結果",
        "debug_config_text": "設定ファイルの解析結果",
        "success_formatted_text": "テキスト整形に成功しました。",
        "success_debug_config": "設定ファイル解析に成功しました。",
        "error_toml_parse": "設定ファイル解析に失敗しました。",
        "error_template_generate": "テキスト整形に失敗しました。",
        "error_both_files": "設定ファイルとJinjaテンプレートファイルの両方をアップロードしてください。",
        "error_debug_config": "設定ファイル解析に失敗しました。",
    },
}
