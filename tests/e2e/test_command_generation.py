#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Streamlit アプリケーションのコマンド生成機能のテスト

実行方法:
- すべてのテストを実行: python -m pytest tests/e2e/test_command_generation.py -v
- 特定のテストを実行: python -m pytest tests/e2e/test_command_generation.py::test_cli_command_generation -v
"""

import pytest
from playwright.sync_api import Page, expect
from pytest_benchmark.fixture import BenchmarkFixture

# test_utils から関数とテキストリソースをインポート
from .conftest import _wait_for_streamlit
from .test_utils import check_result_displayed, select_tab, texts, upload_config_and_template


@pytest.mark.e2e
@pytest.mark.benchmark
def test_cli_command_generation(page: Page, streamlit_port: int, benchmark: BenchmarkFixture) -> None:
    """CSVファイルとJinjaテンプレートを使用してCLIコマンドを生成する機能をテスト"""
    # タブを選択
    select_tab(page, f"📝 {texts.tab1.menu_title}")

    # 設定ファイルとテンプレートファイルをアップロード
    upload_config_and_template(page, "dns_dig_config.csv", "dns_dig_tmpl.j2")

    def _generate_command() -> None:
        # CLIコマンド生成ボタンをクリック
        cli_button = page.locator(f"button:has-text('{texts.tab1.generate_text_button}')").first
        expect(cli_button).to_be_visible()
        cli_button.click()

        # 結果が表示されるまで待機
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)

        # 生成されたコマンドが表示されることを確認
        check_result_displayed(page)

    benchmark(_generate_command)


@pytest.mark.e2e
def test_markdown_generation(page: Page, streamlit_port: int) -> None:
    """YAMLファイルとJinjaテンプレートを使用してMarkdownを生成する機能をテスト"""
    # タブを選択
    select_tab(page, f"📝 {texts.tab1.menu_title}")

    # 設定ファイルとテンプレートファイルをアップロード
    upload_config_and_template(page, "success_config.yaml", "success_template.j2")

    # Markdown生成ボタンをクリック
    markdown_button = page.locator(f"button:has-text('{texts.tab1.generate_markdown_button}')").first
    expect(markdown_button).to_be_visible()
    markdown_button.click()

    # 結果が表示されるまで待機
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)

    # 生成されたMarkdownが表示されることを確認
    check_result_displayed(page)


@pytest.mark.e2e
def test_toml_config_processing(page: Page, streamlit_port: int) -> None:
    """TOMLファイルとJinjaテンプレートを使用してコマンドを生成する機能をテスト"""
    # タブを選択
    select_tab(page, f"📝 {texts.tab1.menu_title}")

    # 設定ファイルとテンプレートファイルをアップロード
    upload_config_and_template(page, "cisco_config.toml", "cisco_template.jinja2")

    # CLIコマンド生成ボタンをクリック
    cli_button = page.locator(f"button:has-text('{texts.tab1.generate_text_button}')").first
    expect(cli_button).to_be_visible()
    cli_button.click()

    # 結果が表示されるまで待機
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)

    # 生成されたコマンドが表示されることを確認
    check_result_displayed(page)


@pytest.mark.e2e
@pytest.mark.e2e_parametrized
@pytest.mark.benchmark
@pytest.mark.parametrize(
    ("config_file", "template_file", "button_text"),
    [
        pytest.param("dns_dig_config.csv", "dns_dig_tmpl.j2", texts.tab1.generate_text_button, id="e2e_command_gen_csv_cli"),
        pytest.param("success_config.yaml", "success_template.j2", texts.tab1.generate_markdown_button, id="e2e_command_gen_yaml_markdown"),
        pytest.param("cisco_config.toml", "cisco_template.jinja2", texts.tab1.generate_text_button, id="e2e_command_gen_toml_cli"),
    ],
)
def test_command_generation_parametrized(
    page: Page, streamlit_port: int, config_file: str, template_file: str, button_text: str, benchmark: BenchmarkFixture
) -> None:
    """パラメータ化されたコマンド生成機能のテスト

    コマンド生成タブで設定ファイルとテンプレートファイルをアップロードし、
    指定されたボタンをクリックして結果が生成されることを確認します。
    また、ダウンロードボタンが有効になることも確認します。

    Args:
        page: Playwrightのページオブジェクト
        streamlit_port: テスト用のポート番号
        config_file: アップロードする設定ファイル名
        template_file: アップロードするテンプレートファイル名
        button_text: クリックするボタンのテキスト
        benchmark: ベンチマーク実行用のフィクスチャ
    """
    # Streamlitサーバーが応答することを確認
    assert _wait_for_streamlit(timeout=5, interval=1, port=streamlit_port), "Streamlit server is not responding before test"

    # Arrange: コマンド生成タブを選択
    select_tab(page, f"📝 {texts.tab1.menu_title}")

    # 設定ファイルとテンプレートファイルをアップロード
    upload_config_and_template(page, config_file, template_file)

    def _generate_and_verify() -> None:
        # Act: コマンド生成ボタンをクリック
        command_button = page.locator(f"button:has-text('{button_text}')").first
        expect(command_button).to_be_visible()
        command_button.click()

        # ページの読み込みを待機 - 待機時間を増やす
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(5000)

        # Assert: 生成結果が表示されていることを確認
        check_result_displayed(page)

    benchmark(_generate_and_verify)
