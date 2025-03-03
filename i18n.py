#! /usr/bin/env python

# 言語リソース
LANGUAGES = {
    "日本語": {
        "sidebar": {
            "welcome": """
            このアプリケーションでは、設定定義ファイル(toml/yaml)とJinjaテンプレートファイルの組み合わせにより、インフラ構築コマンドのコマンド生成ができます。

            各ファイルをアップロードし、「CLIコマンド生成」をクリックして結果を確認してください。
            """,
            "syntax_of_each_file": "各ファイルの構文",
            "toml_syntax_doc": "https://toml.io/ja/v1.0.0",
            "yaml_syntax_doc": "https://docs.ansible.com/ansible/2.9_ja/reference_appendices/YAMLSyntax.html",
            "jinja_syntax_doc": "https://jinja.palletsprojects.com/en/3.1.x/templates/",
        },
        "tab1": {
            "menu_title": "コマンド生成",
            "subheader": "ファイルの組み合わせによるコマンド生成",
            "upload_config": "設定定義ファイルをアップロード",
            "upload_template": "Jinjaテンプレートファイルをアップロード",
            "generate_text_button": "CLIコマンド生成",
            "generate_markdown_button": "Markdown生成",
            "download_button": "ダウンロード",
            "formatted_text": "CLIコマンド生成の出力結果",
            "success_formatted_text": "CLIコマンド生成に成功",
            "error_toml_parse": "設定定義ファイルの読み込みに失敗",
            "error_template_generate": "Jinjaテンプレートの読み込みに失敗",
            "error_both_files": "必要な全ファイルが揃っていません",
        },
        "tab2": {
            "menu_title": "設定デバッグ",
            "subheader": "構文解析による設定デバッグ",
            "upload_debug_config": "設定定義ファイルをアップロード",
            "debug_config_text": "設定定義ファイルの解析結果",
            "success_debug_config": "設定定義ファイル解析に成功",
            "error_debug_config": "設定定義ファイルの読み込みに失敗",
            "error_debug_not_found": "設定定義ファイルが読み込まれていません",
            "generate_visual_button": "解析結果の表示 (visual)",
            "generate_toml_button": "解析結果の表示 (toml)",
            "generate_yaml_button": "解析結果の表示 (yaml)",
        },
        "tab3": {
            "menu_title": "詳細設定",
            "subheader": "詳細設定",
            "download_filename": "ダウンロード時のファイル名",
            "download_encoding": "ダウンロードファイルの文字コード",
            "download_file_extension": "ダウンロード時のファイル拡張子",
            "append_timestamp_filename": "ファイル名の末尾にタイプスタンプを付与",
            "strict_undefined": "テンプレートの変数チェック厳格化",
            "auto_transcoding": "UTF-8以外の文字コードを自動判定して読み込む",
            "format_type": "出力フォーマット",
            "format_type_items": {
                0: "フォーマット指定無し",
                1: "半角スペースを一部削除",
                2: "余分な改行を一部削除",
                3: "半角スペースと余分な改行を一部削除",
                4: "半角スペースの一部と余分な改行を全て削除",
            },
            "subheader_input_file": "入力ファイルの設定",
            "subheader_output_file": "出力ファイルの設定",
            "csv_rows_name": "CSV設定定義ファイル上のforループ対象の変数名",
        },
        "tab4": {
            "menu_title": "サンプル集",
            "subheader": "サンプル集の表示",
        },
    },
}
