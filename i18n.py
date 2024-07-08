#! /usr/bin/env python

# 言語リソース
LANGUAGES = {
    "日本語": {
        "sidebar": {
            "welcome": """
            このアプリケーションでは、設定ファイル(toml/yaml)とJinjaテンプレートファイルをアップロードして、インフラ構築コマンドなどのテキスト整形ができます。

            ファイルをアップロードして、「テキスト整形の実行」をクリックして結果を確認してください。
            """,
            "syntax_of_each_file": "各ファイルの構文",
            "toml_syntax_doc": "https://toml.io/ja/v1.0.0",
            "yaml_syntax_doc": "https://docs.ansible.com/ansible/2.9_ja/reference_appendices/YAMLSyntax.html",
            "jinja_syntax_doc": "https://jinja.palletsprojects.com/en/3.1.x/templates/",
        },
        "tab1": {
            "menu_title": "テキスト整形",
            "subheader": "設定ファイルとテンプレートを使ったテキスト整形",
            "upload_config": "設定ファイルをアップロード",
            "upload_template": "Jinjaテンプレートをアップロード",
            "generate_text_button": "テキスト整形の実行",
            "generate_markdown_button": "Markdown整形を実行",
            "download_button": "ダウンロード",
            "formatted_text": "テキスト整形の出力結果",
            "success_formatted_text": "テキスト整形に成功",
            "error_toml_parse": "設定ファイルの読み込みに失敗",
            "error_template_generate": "Jinjaテンプレートの読み込みに失敗",
            "error_both_files": "テキスト整形に必要な全ファイルが揃っていません",
        },
        "tab2": {
            "menu_title": "設定デバッグ",
            "subheader": "設定ファイルの構文解析",
            "upload_debug_config": "設定ファイルをアップロード",
            "debug_config_text": "設定ファイルの解析結果",
            "success_debug_config": "設定ファイル解析に成功",
            "error_debug_config": "設定ファイルの読み込みに失敗",
            "error_debug_not_found": "設定ファイルが読み込まれていません",
            "generate_visual_button": "設定ファイル解析の表示 (visual)",
            "generate_json_button": "設定ファイル解析の表示 (json)",
            "generate_yaml_button": "設定ファイル解析の表示 (yaml)",
        },
        "tab3": {
            "menu_title": "詳細オプション",
            "subheader": "詳細オプションの設定",
            "download_filename": "ダウンロード時のファイル名",
            "download_encoding": "ダウンロードファイルの文字コードを指定",
            "download_file_extension": "ダウンロード時のファイル拡張子",
            "append_timestamp_filename": "ファイル名の末尾にタイプスタンプを付与",
            "strict_undefined": "テンプレートの変数チェック厳格化",
            "auto_encoding": "UTF-8以外の文字コードを自動判定して読み込む",
            "format_type": "整形時のフォーマット型",
            "format_type_item0": "フォーマット無し",
            "format_type_item1": "半角スペースを一部削除",
            "format_type_item2": "余分な改行を一部削除",
            "format_type_item3": "半角スペースと余分な改行を一部削除",
            "format_type_item4": "半角スペースの一部と余分な改行を全て削除",
            "subheader_input_file": "入力ファイルの設定",
            "subheader_output_file": "出力ファイルの設定",
            "csv_rows_name": "CSV設定ファイル上のforループ対象の変数名",
        },
        "tab4": {
            "menu_title": "サンプル集",
            "subheader": "サンプル集の表示",
        },
    },
}
