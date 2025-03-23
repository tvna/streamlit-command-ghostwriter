#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Streamlit アプリケーションの詳細設定タブとサンプル集タブのテスト

実行方法:
- すべてのテストを実行: python -m pytest tests/e2e/test_other_tabs.py -v
- 特定のテストを実行: python -m pytest tests/e2e/test_other_tabs.py::test_advanced_settings -v
"""

import pytest
from playwright.sync_api import Page, expect

# test_utils から関数とテキストリソースをインポート
from .test_utils import select_tab, texts


@pytest.mark.e2e
@pytest.mark.e2e_basic
def test_advanced_settings(page: Page) -> None:
    """詳細設定タブでの設定変更機能をテスト"""
    # タブ3を選択
    select_tab(page, f"🛠️ {texts.tab3.menu_title}")

    # 入力ファイルの設定セクションが表示されることを確認
    input_settings_header = page.locator(f"h3:has-text('{texts.tab3.subheader_input_file}')").first
    expect(input_settings_header).to_be_visible()

    # コマンド生成タブに戻る
    select_tab(page, f"📝 {texts.tab1.menu_title}")


@pytest.mark.e2e
@pytest.mark.e2e_basic
def test_sample_collection(page: Page) -> None:
    """サンプル集タブでのサンプルファイル表示機能をテスト"""
    # タブ4を選択
    select_tab(page, f"💼 {texts.tab4.menu_title}")

    # サンプル集の表示セクションが表示されることを確認
    sample_header = page.locator(f"h3:has-text('{texts.tab4.subheader}')").first
    expect(sample_header).to_be_visible()

    # サンプルファイルのテキストエリアが表示されることを確認
    # cisco_config.tomlのテキストエリア
    cisco_config_textarea = page.locator("textarea[aria-label='cisco_config.toml']").first
    expect(cisco_config_textarea).to_be_visible()

    # cisco_template.jinja2のテキストエリア
    cisco_template_textarea = page.locator("textarea[aria-label='cisco_template.jinja2']").first
    expect(cisco_template_textarea).to_be_visible()

    # dns_dig_config.csvのテキストエリア
    dns_dig_config_textarea = page.locator("textarea[aria-label='dns_dig_config.csv']").first
    expect(dns_dig_config_textarea).to_be_visible()

    # dns_dig_tmpl.j2のテキストエリア
    dns_dig_tmpl_textarea = page.locator("textarea[aria-label='dns_dig_tmpl.j2']").first
    expect(dns_dig_tmpl_textarea).to_be_visible()

    # success_config.yamlのテキストエリア
    success_config_textarea = page.locator("textarea[aria-label='success_config.yaml']").first
    expect(success_config_textarea).to_be_visible()

    # success_template.j2のテキストエリア
    success_template_textarea = page.locator("textarea[aria-label='success_template.j2']").first
    expect(success_template_textarea).to_be_visible()

    # サンプルファイルの内容が表示されていることを確認
    cisco_config_text = cisco_config_textarea.input_value()
    assert "hostname" in cisco_config_text, "cisco_config.tomlの内容が正しく表示されていません"
    assert "interfaces" in cisco_config_text, "cisco_config.tomlの内容が正しく表示されていません"

    cisco_template_text = cisco_template_textarea.input_value()
    assert "enable" in cisco_template_text, "cisco_template.jinja2の内容が正しく表示されていません"
    assert "for vlan in global.vlans" in cisco_template_text, "cisco_template.jinja2の内容が正しく表示されていません"

    dns_dig_config_text = dns_dig_config_textarea.input_value()
    assert "resolver" in dns_dig_config_text, "dns_dig_config.csvの内容が正しく表示されていません"
    assert "fqdn" in dns_dig_config_text, "dns_dig_config.csvの内容が正しく表示されていません"

    dns_dig_tmpl_text = dns_dig_tmpl_textarea.input_value()
    assert "for row in csv_rows" in dns_dig_tmpl_text, "dns_dig_tmpl.j2の内容が正しく表示されていません"
    assert "dig @" in dns_dig_tmpl_text, "dns_dig_tmpl.j2の内容が正しく表示されていません"
