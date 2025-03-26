#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Streamlit アプリケーションの基本的なUI要素のテスト

実行方法:
- すべてのテストを実行: python -m pytest tests/e2e/test_basic_ui.py -v
- 特定のテストを実行: python -m pytest tests/e2e/test_basic_ui.py::test_app_title -v
"""

from typing import List

import pytest
from playwright.sync_api import Page, expect
from pytest_benchmark.fixture import BenchmarkFixture

from .conftest import _wait_for_streamlit
from .helpers import (
    check_result_displayed,
    click_button,
    get_display_button,
    get_result_text,
    get_test_file_path,
    select_tab,
    texts,
    upload_config_and_template,
    verify_result_content,
)


@pytest.mark.e2e
def test_app_title(page: Page, streamlit_port: int, benchmark: BenchmarkFixture) -> None:
    """アプリケーションのタイトルが正しく表示されることを確認"""

    # Streamlitサーバーが応答することを確認
    assert _wait_for_streamlit(timeout=5, interval=1, port=streamlit_port), "Streamlit server is not responding before test"

    def _check_title() -> None:
        # Streamlit アプリのタイトルを検証
        title = page.locator("h1:has-text('Command ghostwriter')")
        expect(title).to_be_visible()
        expect(title).to_contain_text("Command ghostwriter")

    benchmark(_check_title)


@pytest.mark.e2e
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
def test_button_click(page: Page, streamlit_port: int) -> None:
    """ボタンクリックが機能することを確認"""
    # タブを選択
    select_tab(page, f"📝 {texts.tab1.menu_title}")

    # ボタンをクリック
    click_button(page, texts.tab1.generate_text_button)


@pytest.mark.e2e
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
def test_cli_command_generation(page: Page, streamlit_port: int, benchmark: BenchmarkFixture) -> None:
    """CSVファイルとJinjaテンプレートを使用してCLIコマンドを生成する機能をテスト"""

    # Streamlitサーバーが応答することを確認
    assert _wait_for_streamlit(timeout=5, interval=1, port=streamlit_port), "Streamlit server is not responding before test"

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


@pytest.mark.e2e
def test_file_upload(page: Page, streamlit_port: int) -> None:
    """ファイルアップロード機能が動作することを確認"""
    # タブを選択
    select_tab(page, f"📝 {texts.tab1.menu_title}")

    # ファイルアップロード要素を見つける
    upload_container = page.locator("div[data-testid='stFileUploader']").first
    expect(upload_container).to_be_visible()

    # ファイルアップロードボタンを見つける
    upload_button = page.locator("button:has-text('Browse files')").first
    expect(upload_button).to_be_visible()

    # テスト用のファイルパスを指定
    test_file_path = get_test_file_path("sample.txt")

    # ファイルアップロード処理
    with page.expect_file_chooser() as fc_info:
        upload_button.click()
    file_chooser = fc_info.value
    file_chooser.set_files(test_file_path)

    # アップロード後の処理を待機
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1000)


@pytest.mark.e2e
def test_jinja_template_upload(page: Page, streamlit_port: int) -> None:
    """Jinjaテンプレートファイルのアップロード機能が動作することを確認"""
    # タブを選択
    select_tab(page, f"📝 {texts.tab1.menu_title}")

    # Jinjaテンプレートファイルのアップロード要素を見つける
    # 2番目のファイルアップローダーを選択
    upload_containers = page.locator("div[data-testid='stFileUploader']").all()
    # Pythonのassert文を使用して要素の数を確認
    assert len(upload_containers) > 1, "ファイルアップローダーが2つ以上見つかりません"

    # 2番目のアップロードコンテナを取得
    jinja_upload_container = upload_containers[1]
    expect(jinja_upload_container).to_be_visible()

    # ラベルを確認
    upload_label = jinja_upload_container.locator("div[data-testid='stMarkdownContainer']").first
    expect(upload_label).to_contain_text(texts.tab1.upload_template)

    # ファイルアップロードボタンを見つける
    upload_button = jinja_upload_container.locator("button:has-text('Browse files')").first
    expect(upload_button).to_be_visible()

    # テスト用のファイルパスを指定
    test_file_path = get_test_file_path("sample.txt")

    # ファイルアップロード処理
    with page.expect_file_chooser() as fc_info:
        upload_button.click()
    file_chooser = fc_info.value
    file_chooser.set_files(test_file_path)

    # アップロード後の処理を待機
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1000)


@pytest.mark.e2e
def test_config_file_upload_tab2(page: Page, streamlit_port: int) -> None:
    """タブ2の設定定義ファイルのアップロード機能が動作することを確認"""
    # タブ2を選択
    select_tab(page, f"📜 {texts.tab2.menu_title}")

    # 設定定義ファイルのアップロード要素を見つける
    # タブパネル内のファイルアップローダーを探す
    tab_panel = page.locator("div[role='tabpanel']:visible").first
    upload_container = tab_panel.locator("div[data-testid='stFileUploader']").first
    expect(upload_container).to_be_visible()

    # ラベルを確認
    upload_label = upload_container.locator("div[data-testid='stMarkdownContainer']").first
    expect(upload_label).to_contain_text(texts.tab2.upload_debug_config)

    # ファイルアップロードボタンを見つける
    upload_button = upload_container.locator("button:has-text('Browse files')").first
    expect(upload_button).to_be_visible()

    # テスト用のファイルパスを指定
    test_file_path = get_test_file_path("sample.txt")

    # ファイルアップロード処理
    with page.expect_file_chooser() as fc_info:
        upload_button.click()
    file_chooser = fc_info.value
    file_chooser.set_files(test_file_path)

    # アップロード後の処理を待機
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1000)


@pytest.mark.e2e
@pytest.mark.parametrize(
    ("tab_name", "upload_index", "file_type", "file_name"),
    [
        pytest.param(f"📝 {texts.tab1.menu_title}", 0, texts.tab1.upload_config, "dns_dig_config.csv", id="e2e_upload_csv_config"),
        pytest.param(f"📝 {texts.tab1.menu_title}", 1, texts.tab1.upload_template, "dns_dig_tmpl.j2", id="e2e_upload_jinja_template"),
        pytest.param(f"📜 {texts.tab2.menu_title}", 0, texts.tab2.upload_debug_config, "cisco_config.toml", id="e2e_upload_toml_config"),
    ],
)
def test_file_upload_parametrized(
    page: Page, streamlit_port: int, tab_name: str, upload_index: int, file_type: str, file_name: str
) -> None:
    """パラメータ化されたファイルアップロードのテスト

    各タブで指定されたインデックスのファイルアップローダーにファイルをアップロードし、
    アップロードが成功することを確認します。

    Args:
        page: Playwrightのページオブジェクト
        streamlit_port: テスト用のポート番号
        tab_name: テスト対象のタブ名
        upload_index: ファイルアップローダーのインデックス
        file_type: アップロードするファイルの種類[表示用]
        file_name: アップロードするファイル名
    """
    # Arrange: タブを選択
    select_tab(page, tab_name)

    # タブパネルが表示されていることを確認
    tab_panel = page.locator("div[role='tabpanel']:visible").first
    expect(tab_panel).to_be_visible()

    # ファイルアップロード要素を取得 - タブパネル内で検索するように変更
    upload_containers = tab_panel.locator("div[data-testid='stFileUploader']").all()
    assert len(upload_containers) > upload_index, (
        f"Not enough file uploaders found.\nExpected at least {upload_index + 1} uploaders\nFound: {len(upload_containers)}"
    )

    upload_container = upload_containers[upload_index]
    assert upload_container.count() > 0, "File uploader element not found"

    # ファイルアップロードボタンを見つける
    upload_button = upload_container.locator("button:has-text('Browse files')").first
    expect(upload_button).to_be_visible()

    # テスト用のファイルパスを準備
    test_file_path = get_test_file_path(file_name)

    # Act: ファイルをアップロード
    with page.expect_file_chooser() as fc_info:
        upload_button.click()
    file_chooser = fc_info.value
    file_chooser.set_files(test_file_path)

    # ページの読み込みを待機 - 待機時間を増やす
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(3000)

    # Assert: アップロードされたファイル名が表示されていることを確認
    uploaded_file_text = upload_container.inner_text()
    assert file_name in uploaded_file_text, (
        f"Uploaded file name not displayed.\nExpected file name: {file_name}\nActual text: {uploaded_file_text}"
    )


@pytest.mark.e2e
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
@pytest.mark.parametrize(
    ("file_name", "display_format", "expected_content"),
    [
        pytest.param("cisco_config.toml", "visual", ["hostname", "router"], id="e2e_config_debug_toml_visual"),
        pytest.param("success_config.yaml", "toml", ["url", "name"], id="e2e_config_debug_yaml_to_toml"),
        pytest.param("dns_dig_config.csv", "yaml", ["resolver", "fqdn", "type"], id="e2e_config_debug_csv_to_yaml"),
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
    upload_config_file(page, file_name)

    # Act: 解析結果の表示ボタンをクリック
    display_button = get_display_button(page, display_format)
    expect(display_button).to_be_visible()
    display_button.click()

    # ページの読み込みを待機
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(7000)

    # タブパネルを取得
    tab_panel = page.locator("div[role='tabpanel']:visible").first

    # 成功メッセージが表示されることを確認
    success_message = tab_panel.locator(f"div:has-text('{texts.tab2.success_debug_config}')").first
    expect(success_message).to_be_visible(timeout=15000)

    # Assert: 解析結果の検証
    result_text = get_result_text(tab_panel, display_format)
    verify_result_content(result_text, expected_content, display_format)


@pytest.mark.e2e
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
