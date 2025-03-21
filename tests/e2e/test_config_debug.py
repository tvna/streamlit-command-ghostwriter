#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Streamlit アプリケーションの設定デバッグ機能のテスト

実行方法:
- すべてのテストを実行: python -m pytest tests/e2e/test_config_debug.py -v
- 特定のテストを実行: python -m pytest tests/e2e/test_config_debug.py::test_config_debug_visual -v
"""

from typing import List

import pytest
from playwright.sync_api import Page, expect

# test_utils から関数とテキストリソースをインポート
from .test_utils import check_result_displayed, get_test_file_path, select_tab, texts


def upload_config_file(page: Page, file_name: str) -> None:
    """設定ファイルをアップロードする

    Args:
        page: Playwrightのページオブジェクト
        file_name: アップロードするファイル名
    """
    # タブパネルを取得
    tab_panel = page.locator("div[role='tabpanel']:visible").first

    # 設定定義ファイルのアップロード要素を見つける
    upload_container = tab_panel.locator("div[data-testid='stFileUploader']").first
    expect(upload_container).to_be_visible()

    # ファイルアップロードボタンを見つける
    upload_button = upload_container.locator("button:has-text('Browse files')").first
    expect(upload_button).to_be_visible()

    # ファイルをアップロード
    test_file_path = get_test_file_path(file_name)
    with page.expect_file_chooser() as fc_info:
        upload_button.click()
    file_chooser = fc_info.value
    file_chooser.set_files(test_file_path)

    # アップロード後の処理を待機
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1000)


@pytest.mark.e2e
@pytest.mark.e2e_basic
def test_config_debug_visual(page: Page, streamlit_port: int) -> None:
    """設定デバッグタブでの視覚的デバッグ機能をテスト"""
    # タブ2を選択
    select_tab(page, f"📜 {texts.tab2.menu_title}")

    # 設定ファイルをアップロード
    upload_config_file(page, "cisco_config.toml")

    # 解析結果の表示ボタン[visual]をクリック
    visual_button = page.locator(f"button:has-text('{texts.tab2.generate_visual_button}')").first
    expect(visual_button).to_be_visible()
    visual_button.click()

    # 結果が表示されるまで待機
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)

    # 視覚的な解析結果が表示されることを確認
    check_result_displayed(page)


@pytest.mark.e2e
@pytest.mark.e2e_basic
def test_config_debug_toml(page: Page, streamlit_port: int) -> None:
    """設定デバッグタブでのTOML形式での表示機能をテスト"""
    # タブ2を選択
    select_tab(page, f"📜 {texts.tab2.menu_title}")

    # 設定ファイルをアップロード
    upload_config_file(page, "success_config.yaml")

    # 解析結果の表示ボタン[toml]をクリック
    toml_button = page.locator(f"button:has-text('{texts.tab2.generate_toml_button}')").first
    expect(toml_button).to_be_visible()
    toml_button.click()

    # 結果が表示されるまで待機
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)

    # TOML形式の解析結果が表示されることを確認
    check_result_displayed(page)


@pytest.mark.e2e
@pytest.mark.e2e_basic
def test_config_debug_yaml(page: Page, streamlit_port: int) -> None:
    """設定デバッグタブでのYAML形式での表示機能をテスト"""
    # タブ2を選択
    select_tab(page, f"📜 {texts.tab2.menu_title}")

    # 設定ファイルをアップロード
    upload_config_file(page, "dns_dig_config.csv")

    # 解析結果の表示ボタン[yaml]をクリック
    yaml_button = page.locator(f"button:has-text('{texts.tab2.generate_yaml_button}')").first
    expect(yaml_button).to_be_visible()
    yaml_button.click()

    # 結果が表示されるまで待機
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)

    # YAML形式の解析結果が表示されることを確認
    check_result_displayed(page)


@pytest.mark.e2e
@pytest.mark.e2e_parametrized
@pytest.mark.parametrize(
    ("file_name", "display_format", "expected_content"),
    [
        pytest.param("cisco_config.toml", "visual", ["hostname", "router"], id="TOML_視覚的表示"),
        pytest.param("success_config.yaml", "toml", ["url", "name"], id="YAML_TOML形式表示"),
        pytest.param("dns_dig_config.csv", "yaml", ["resolver", "fqdn", "type"], id="CSV_YAML形式表示"),
    ],
)
def test_config_debug_parametrized(
    page: Page, streamlit_port: int, file_name: str, display_format: str, expected_content: List[str]
) -> None:
    """パラメータ化された設定デバッグ機能のテスト

    設定デバッグタブで各種ファイルをアップロードし、指定された形式で解析結果を表示して、
    期待される内容が含まれていることを確認します。

    Args:
        page: Playwrightのページオブジェクト
        streamlit_port: テスト用のポート番号
        file_name: アップロードするファイル名
        display_format: 表示形式[visual, toml, yaml]
        expected_content: 解析結果に含まれるべき内容のリスト
    """
    # Arrange: 設定デバッグタブを選択
    select_tab(page, f"📜 {texts.tab2.menu_title}")

    # 設定ファイルをアップロード
    upload_config_file(page, file_name)

    # Act: 解析結果の表示ボタンをクリック
    button_text = ""
    if display_format == "visual":
        button_text = texts.tab2.generate_visual_button
    elif display_format == "toml":
        button_text = texts.tab2.generate_toml_button
    elif display_format == "yaml":
        button_text = texts.tab2.generate_yaml_button

    display_button = page.locator(f"button:has-text('{button_text}')").first
    expect(display_button).to_be_visible()
    display_button.click()

    # ページの読み込みを待機 - 待機時間を増やす
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(7000)

    # タブパネルを取得
    tab_panel = page.locator("div[role='tabpanel']:visible").first

    # 成功メッセージが表示されることを確認
    success_message = tab_panel.locator(f"div:has-text('{texts.tab2.success_debug_config}')").first
    expect(success_message).to_be_visible(timeout=15000)

    # Assert: 解析結果が表示されていることを確認
    result_text = ""

    # 表示形式に応じて適切なセレクタを使用
    if display_format == "visual":
        # JSON表示の場合
        json_container = tab_panel.locator("div[data-testid='stJson']").first
        if json_container.count() > 0:
            result_text = json_container.inner_text()

    # テキストエリアの場合 [tomlとyaml形式]
    text_areas = tab_panel.locator("textarea").all()
    for text_area in text_areas:
        area_text = text_area.input_value()
        if area_text:
            result_text += area_text + "\n"

    # テキストエリアやJSON表示が見つからない場合、他の表示方法を確認
    if not result_text:
        # マークダウン要素を確認
        markdown_areas = tab_panel.locator("div.stMarkdown").all()
        for area in markdown_areas:
            area_text = area.inner_text()
            if area_text and not area_text.startswith(texts.tab2.upload_debug_config):
                result_text += area_text + "\n"

    # 何らかの結果が表示されていることを確認
    assert len(result_text.strip()) > 0, f"解析結果が表示されていません({display_format}形式)"

    # 期待される内容が含まれていることを確認
    for content in expected_content:
        assert content.lower() in result_text.lower(), f"期待される内容 '{content}' が解析結果に含まれていません"
