#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Streamlit アプリケーションの基本的なUI要素のテスト

実行方法:
- すべてのテストを実行: python -m pytest tests/e2e/test_basic_ui.py -v
- 特定のテストを実行: python -m pytest tests/e2e/test_basic_ui.py::test_app_title -v
"""

import pytest
from playwright.sync_api import Page, expect
from pytest_benchmark.fixture import BenchmarkFixture

from .test_utils import click_button, select_tab, texts


@pytest.mark.e2e
@pytest.mark.e2e_basic
@pytest.mark.benchmark
def test_app_title(page: Page, streamlit_port: int, benchmark: BenchmarkFixture) -> None:
    """アプリケーションのタイトルが正しく表示されることを確認"""

    def _check_title() -> None:
        # Streamlit アプリのタイトルを検証
        title = page.locator("h1:has-text('Command ghostwriter')")
        expect(title).to_be_visible()
        expect(title).to_contain_text("Command ghostwriter")

    benchmark(_check_title)


@pytest.mark.e2e
@pytest.mark.e2e_basic
@pytest.mark.benchmark
def test_input_field(page: Page, streamlit_port: int, benchmark: BenchmarkFixture) -> None:
    """入力フィールドが機能することを確認"""
    # タブを選択
    select_tab(page, f"📝 {texts.tab1.menu_title}")

    def _check_input_fields() -> None:
        # ファイルアップロードボタンを見つける
        upload_button = page.locator("button:has-text('Browse files')").first
        expect(upload_button).to_be_visible()

        # CLIコマンド生成ボタンを見つける
        cli_button = page.locator(f"button:has-text('{texts.tab1.generate_text_button}')").first
        expect(cli_button).to_be_visible()

    benchmark(_check_input_fields)


@pytest.mark.e2e
@pytest.mark.e2e_basic
def test_button_click(page: Page, streamlit_port: int) -> None:
    """ボタンクリックが機能することを確認"""
    # タブを選択
    select_tab(page, f"📝 {texts.tab1.menu_title}")

    # ボタンをクリック
    click_button(page, texts.tab1.generate_text_button)


@pytest.mark.e2e
@pytest.mark.e2e_basic
def test_sidebar_interaction(page: Page, streamlit_port: int) -> None:
    """サイドバーの操作が機能することを確認"""
    # サイドバーを開く - Streamlitの新しいUIでは、ハンバーガーメニューをクリックする必要がある
    sidebar = page.locator("section[data-testid='stSidebar']")
    expect(sidebar).to_be_visible()

    # サイドバー内のエキスパンダーを操作
    expander = page.locator(f"details summary:has-text('{texts.sidebar.syntax_of_each_file}')").first
    expect(expander).to_be_visible()

    # エキスパンダーが閉じている場合は開く
    details = page.locator("details").first
    if not details.get_attribute("open"):
        expander.click()
        page.wait_for_timeout(500)  # アニメーションの完了を待つ

    # エキスパンダー内のリンクを確認[存在するかどうかだけを確認]
    link = page.locator("a:has-text('toml syntax docs')").first
    # 表示状態ではなく存在を確認
    expect(link).to_be_attached()


@pytest.mark.e2e
@pytest.mark.e2e_basic
def test_download_functionality(page: Page, streamlit_port: int) -> None:
    """ダウンロード機能が動作することを確認"""
    # タブを選択
    select_tab(page, f"📝 {texts.tab1.menu_title}")

    # ダウンロードボタンを見つける
    download_button = page.locator("div[data-testid='stDownloadButton'] button").first
    expect(download_button).to_be_visible()

    # ダウンロードボタンは初期状態では無効になっている
    expect(download_button).to_have_attribute("disabled", "")


@pytest.mark.e2e
@pytest.mark.e2e_basic
def test_responsive_design(page: Page, streamlit_port: int) -> None:
    """レスポンシブデザインが機能することを確認"""
    # モバイルビューに設定
    page.set_viewport_size({"width": 375, "height": 667})  # iPhone 8 サイズ

    # ページを再読み込み
    page.reload()
    page.wait_for_load_state("networkidle")

    # モバイルビューでの表示を確認
    # ハンバーガーメニューが表示されることを確認
    hamburger_button = page.locator("div[data-testid='stSidebarCollapsedControl']").first
    expect(hamburger_button).to_be_visible()

    # デスクトップビューに戻す
    page.set_viewport_size({"width": 1280, "height": 720})


@pytest.mark.e2e
@pytest.mark.e2e_parametrized
@pytest.mark.parametrize(
    ("tab_name", "expected_element"),
    [
        pytest.param(
            f"📝 {texts.tab1.menu_title}", f"button:has-text('{texts.tab1.generate_text_button}')", id="e2e_tab_navigation_command_gen"
        ),
        pytest.param(
            f"📜 {texts.tab2.menu_title}", f"button:has-text('{texts.tab2.generate_visual_button}')", id="e2e_tab_navigation_config_debug"
        ),
        pytest.param(f"🛠️ {texts.tab3.menu_title}", f"h3:has-text('{texts.tab3.subheader_input_file}')", id="e2e_tab_navigation_settings"),
        pytest.param(f"💼 {texts.tab4.menu_title}", f"h3:has-text('{texts.tab4.subheader}')", id="e2e_tab_navigation_samples"),
    ],
)
def test_tab_navigation_parametrized(page: Page, streamlit_port: int, tab_name: str, expected_element: str) -> None:
    """パラメータ化されたタブナビゲーションのテスト

    各タブに切り替えて、期待される要素が表示されることを確認します。

    Args:
        page: Playwrightのページオブジェクト
        streamlit_port: テスト用のポート番号
        tab_name: テスト対象のタブ名
        expected_element: タブ内に表示されるべき要素のセレクタ
    """
    from .conftest import _wait_for_streamlit

    # Streamlitサーバーが応答することを確認
    assert _wait_for_streamlit(timeout=5, interval=1, port=streamlit_port), "Streamlit server is not responding before test."

    # Arrange: タブボタンを取得
    tab_button = page.locator(f"button[role='tab']:has-text('{tab_name}')").first
    expect(tab_button).to_be_visible()

    # Act: タブをクリック
    tab_button.click()

    # ページの読み込みを待機
    page.wait_for_timeout(3000)
    page.wait_for_load_state("networkidle")

    # Assert: タブパネルが表示されていることを確認
    tab_panel = page.locator("div[role='tabpanel']:visible").first
    expect(tab_panel).to_be_visible()

    # 期待される要素が表示されていることを確認
    expected = page.locator(expected_element).first
    expect(expected).to_be_visible()


@pytest.mark.e2e
@pytest.mark.e2e_basic
def test_sample_file_content(page: Page, streamlit_port: int) -> None:
    """サンプルファイルの内容が表示されていることを確認"""
    # タブを選択
    select_tab(page, f"📝 {texts.tab1.menu_title}")

    # サンプルファイルの内容を確認
    cisco_config_textarea = page.locator("textarea[name='cisco_config']").first
    cisco_template_textarea = page.locator("textarea[name='cisco_template']").first
    dns_dig_config_textarea = page.locator("textarea[name='dns_dig_config']").first
    dns_dig_tmpl_textarea = page.locator("textarea[name='dns_dig_tmpl']").first

    # サンプルファイルの内容が表示されていることを確認
    cisco_config_text = cisco_config_textarea.input_value()
    assert "hostname" in cisco_config_text, "Content validation failed for cisco_config.toml.\nExpected to find 'hostname' in content"
    assert "interfaces" in cisco_config_text, "Content validation failed for cisco_config.toml.\nExpected to find 'interfaces' in content"

    cisco_template_text = cisco_template_textarea.input_value()
    assert "enable" in cisco_template_text, "Content validation failed for cisco_template.jinja2.\nExpected to find 'enable' in content"
    assert "for vlan in global.vlans" in cisco_template_text, (
        "Content validation failed for cisco_template.jinja2.\nExpected to find 'for vlan in global.vlans' in content"
    )

    dns_dig_config_text = dns_dig_config_textarea.input_value()
    assert "resolver" in dns_dig_config_text, "Content validation failed for dns_dig_config.csv.\nExpected to find 'resolver' in content"
    assert "fqdn" in dns_dig_config_text, "Content validation failed for dns_dig_config.csv.\nExpected to find 'fqdn' in content"

    dns_dig_tmpl_text = dns_dig_tmpl_textarea.input_value()
    assert "for row in csv_rows" in dns_dig_tmpl_text, (
        "Content validation failed for dns_dig_tmpl.j2.\nExpected to find 'for row in csv_rows' in content"
    )
    assert "dig @" in dns_dig_tmpl_text, "Content validation failed for dns_dig_tmpl.j2.\nExpected to find 'dig @' in content"
