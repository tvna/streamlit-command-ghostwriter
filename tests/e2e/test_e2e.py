#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""StreamlitアプリケーションのE2Eテストモジュール.

このモジュールは、StreamlitアプリケーションのUIコンポーネントとその機能を検証するE2Eテストを提供します:

  - 基本的なUI要素のテスト
    - アプリケーションタイトル
    - 入力フィールド
    - ボタン操作
    - サイドバー操作
    - ダウンロード機能
    - レスポンシブデザイン

  - タブ機能のテスト
    - コマンド生成タブ
    - 設定デバッグタブ
    - 詳細設定タブ
    - サンプル集タブ

  - ファイル操作のテスト
    - 各種設定ファイルのアップロード
    - テンプレートファイルのアップロード
    - 結果の検証

実行方法:
  すべてのテストを実行:
    python -m pytest tests/e2e/test_e2e.py -v

  特定のテストを実行:
    python -m pytest tests/e2e/test_e2e.py::test_ui_app_title -v

  ヘッドレスモードで実行:
    python -m pytest tests/e2e/test_e2e.py

  ブラウザを表示して実行:
    python -m pytest tests/e2e/test_e2e.py --headed
"""

from typing import List

import pytest
from playwright.sync_api import Page, expect
from pytest_benchmark.fixture import BenchmarkFixture

from .helpers import StreamlitTestHelper, TestData, texts


@pytest.mark.e2e
def test_ui_app_title(page: Page, benchmark: BenchmarkFixture) -> None:
    """アプリケーションのタイトル表示をテスト.

    アプリケーションのタイトルが正しく表示され、期待される文字列を含んでいることを確認します。

    Args:
        page: Playwrightのページオブジェクト
        benchmark: ベンチマーク実行用のフィクスチャ

    Note:
        - タイトルの表示を確認
        - タイトルのテキストを検証
        - 処理時間をベンチマーク
    """

    def _check_title() -> None:
        # Streamlit アプリのタイトルを検証
        title = page.locator("h1:has-text('Command ghostwriter')")
        expect(title).to_be_visible()
        expect(title).to_contain_text("Command ghostwriter")

    benchmark(_check_title)


@pytest.mark.e2e
def test_ui_input_field(page: Page, benchmark: BenchmarkFixture) -> None:
    """入力フィールドの機能をテスト.

    コマンド生成タブの入力フィールドが正しく表示され、操作可能であることを確認します。

    Args:
        page: Playwrightのページオブジェクト
        benchmark: ベンチマーク実行用のフィクスチャ

    Note:
        - ファイルアップロードボタンの表示を確認
        - CLIコマンド生成ボタンの表示を確認
        - 処理時間をベンチマーク
    """

    # タブを選択
    helper = StreamlitTestHelper(page)
    helper.select_tab(f"📝 {texts.tab1.menu_title}")

    def _check_input_fields() -> None:
        # ファイルアップロードボタンを見つける
        upload_button = page.locator("button:has-text('Browse files')").first
        expect(upload_button).to_be_visible()

        # CLIコマンド生成ボタンを見つける
        cli_button = page.locator(f"button:has-text('{texts.tab1.generate_text_button}')").first
        expect(cli_button).to_be_visible()

    benchmark(_check_input_fields)


@pytest.mark.e2e
def test_ui_button_click(page: Page) -> None:
    """ボタンクリック操作をテスト.

    コマンド生成タブのボタンが正しくクリック操作に応答することを確認します。

    Args:
        page: Playwrightのページオブジェクト

    Note:
        - タブの切り替えを確認
        - ボタンのクリック操作を実行
    """

    # タブを選択
    helper = StreamlitTestHelper(page)
    helper.select_tab(f"📝 {texts.tab1.menu_title}")

    # ボタンをクリック
    helper.click_button(texts.tab1.generate_text_button)


@pytest.mark.e2e
def test_ui_sidebar_interaction(page: Page) -> None:
    """サイドバーの操作機能をテスト.

    サイドバーの表示と各種操作が正しく機能することを確認します。

    Args:
        page: Playwrightのページオブジェクト

    Note:
        - サイドバーの表示を確認
        - エキスパンダーの操作を確認
        - リンクの存在を確認
    """

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
def test_ui_download_functionality(page: Page) -> None:
    """ダウンロード機能をテスト.

    ダウンロードボタンの表示状態と初期状態での無効化を確認します。

    Args:
        page: Playwrightのページオブジェクト

    Note:
        - ダウンロードボタンの表示を確認
        - 初期状態での無効化を確認
    """

    # タブを選択
    helper = StreamlitTestHelper(page)
    helper.select_tab(f"📝 {texts.tab1.menu_title}")

    # ダウンロードボタンを見つける
    download_button = page.locator("div[data-testid='stDownloadButton'] button").first
    expect(download_button).to_be_visible()

    # ダウンロードボタンは初期状態では無効になっている
    expect(download_button).to_have_attribute("disabled", "")


@pytest.mark.e2e
def test_ui_responsive_design(page: Page) -> None:
    """レスポンシブデザインをテスト.

    異なる画面サイズでのUIの適応性を確認します。

    Args:
        page: Playwrightのページオブジェクト

    Note:
        - モバイルビューでの表示を確認
        - ハンバーガーメニューの表示を確認
        - デスクトップビューでの表示を確認
    """

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
def test_ui_advanced_settings_in_tab3(page: Page) -> None:
    """詳細設定タブの機能をテスト.

    詳細設定タブの表示と設定変更機能を確認します。

    Args:
        page: Playwrightのページオブジェクト

    Note:
        - タブの切り替えを確認
        - 設定セクションの表示を確認
        - 元のタブへの復帰を確認
    """

    helper = StreamlitTestHelper(page)

    # タブ3を選択
    helper.select_tab(f"🛠️ {texts.tab3.menu_title}")

    # 入力ファイルの設定セクションが表示されることを確認
    input_settings_header = page.locator(f"h3:has-text('{texts.tab3.subheader_input_file}')").first
    expect(input_settings_header).to_be_visible()

    # コマンド生成タブに戻る
    helper.select_tab(f"📝 {texts.tab1.menu_title}")


@pytest.mark.e2e
def test_ui_sample_collection_in_tab4(page: Page) -> None:
    """サンプル集タブの機能をテスト.

    サンプル集タブでの各種サンプルファイルの表示と内容を確認します。

    Args:
        page: Playwrightのページオブジェクト

    Note:
        - タブの切り替えを確認
        - 各サンプルファイルの表示を確認
        - サンプルファイルの内容を検証
    """

    helper = StreamlitTestHelper(page)

    # タブ4を選択
    helper = StreamlitTestHelper(page)
    helper.select_tab(f"💼 {texts.tab4.menu_title}")

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

    # wget_config.yamlのテキストエリア
    success_config_textarea = page.locator("textarea[aria-label='success_config.yaml']").first
    expect(success_config_textarea).to_be_visible()

    # wget_template.j2のテキストエリア
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
def test_tab_navigation_parametrized(page: Page, tab_name: str, expected_element: str) -> None:
    """タブナビゲーション機能をパラメータ化してテスト.

    各タブへの切り替えと、タブ固有の要素の表示を確認します。

    Args:
        page: Playwrightのページオブジェクト
        tab_name: テスト対象のタブ名
        expected_element: タブ内に表示されるべき要素のセレクタ

    Note:
        - タブボタンの表示を確認
        - タブの切り替えを実行
        - タブパネルの表示を確認
        - 期待される要素の表示を確認
    """

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
@pytest.mark.parametrize(
    ("config_file", "template_file", "button_text"),
    [
        pytest.param(
            "dns_dig_config.csv",
            "dns_dig_tmpl.j2",
            texts.tab1.generate_text_button,
            id="e2e_command_gen_with_dns_dig_config_to_file",
        ),
        pytest.param(
            "dns_dig_config.csv",
            "dns_dig_tmpl.j2",
            texts.tab1.generate_markdown_button,
            id="e2e_command_gen_with_dns_dig_config_to_markdown",
        ),
        pytest.param(
            "wget_config.yaml",
            "wget_template.j2",
            texts.tab1.generate_text_button,
            id="e2e_command_gen_with_wget_config_to_file",
        ),
        pytest.param(
            "wget_config.yaml",
            "wget_template.j2",
            texts.tab1.generate_markdown_button,
            id="e2e_command_gen_with_wget_config_to_markdown",
        ),
        pytest.param(
            "cisco_config.toml",
            "cisco_template.jinja2",
            texts.tab1.generate_text_button,
            id="e2e_command_gen_with_cisco_config_to_file",
        ),
        pytest.param(
            "cisco_config.toml",
            "cisco_template.jinja2",
            texts.tab1.generate_markdown_button,
            id="e2e_command_gen_with_cisco_config_to_markdown",
        ),
    ],
)
def test_command_generation_parametrized_in_tab1(
    page: Page, config_file: str, template_file: str, button_text: str, benchmark: BenchmarkFixture
) -> None:
    """コマンド生成機能をパラメータ化してテスト.

    各種設定ファイルとテンプレートファイルの組み合わせで、
    コマンド生成機能が正しく動作することを確認します。

    Args:
        page: Playwrightのページオブジェクト
        config_file: アップロードする設定ファイル名
        template_file: アップロードするテンプレートファイル名
        button_text: クリックするボタンのテキスト
        benchmark: ベンチマーク実行用のフィクスチャ

    Note:
        - ファイルのアップロードを確認
        - コマンド生成ボタンの操作を確認
        - 生成結果の表示を確認
        - 処理時間をベンチマーク
    """

    # Arrange: コマンド生成タブを選択
    helper = StreamlitTestHelper(page)
    helper.select_tab(f"📝 {texts.tab1.menu_title}")

    def _execute() -> None:
        # Act: 設定ファイルとテンプレートファイルをアップロード
        helper.upload_config_and_template(config_file, template_file)

        # Act: コマンド生成ボタンをクリック
        command_button = page.locator(f"button:has-text('{button_text}')").first
        expect(command_button).to_be_visible()
        command_button.click()

        # ページの読み込みを待機 - 待機時間を増やす
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(5000)

        # Assert: 生成結果が表示されていることを確認
        helper.check_result_displayed()

    benchmark(_execute)


@pytest.mark.e2e
def test_file_upload_in_tab1(page: Page, benchmark: BenchmarkFixture) -> None:
    """ファイルアップロード機能をテスト.

    コマンド生成タブでのファイルアップロード機能が正しく動作することを確認します。

    Args:
        page: Playwrightのページオブジェクト
        benchmark: ベンチマーク実行用のフィクスチャ

    Note:
        - アップロード要素の表示を確認
        - ファイル選択操作を実行
        - アップロード完了を確認
        - 処理時間をベンチマーク
    """

    # タブを選択
    helper = StreamlitTestHelper(page)
    helper.select_tab(f"📝 {texts.tab1.menu_title}")

    # ファイルアップロード要素を見つける
    upload_container = page.locator("div[data-testid='stFileUploader']").first
    expect(upload_container).to_be_visible()

    # ファイルアップロードボタンを見つける
    upload_button = page.locator("button:has-text('Browse files')").first
    expect(upload_button).to_be_visible()

    # テスト用のファイルパスを指定
    test_file_path = TestData.get_test_file_path("sample.txt")

    def _execute() -> None:
        # ファイルアップロード処理
        with page.expect_file_chooser() as fc_info:
            upload_button.click()
        file_chooser = fc_info.value
        file_chooser.set_files(test_file_path)

        # アップロード後の処理を待機
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)

    benchmark(_execute)


@pytest.mark.e2e
def test_jinja_template_upload_in_tab1(page: Page, benchmark: BenchmarkFixture) -> None:
    """Jinjaテンプレートファイルのアップロード機能をテスト.

    コマンド生成タブでのJinjaテンプレートファイルのアップロード機能が
    正しく動作することを確認します。

    Args:
        page: Playwrightのページオブジェクト
        benchmark: ベンチマーク実行用のフィクスチャ

    Note:
        - テンプレートアップロード要素の表示を確認
        - ファイル選択操作を実行
        - アップロード完了を確認
        - 処理時間をベンチマーク
    """

    # タブを選択
    helper = StreamlitTestHelper(page)
    helper.select_tab(f"📝 {texts.tab1.menu_title}")

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
    test_file_path = TestData.get_test_file_path("sample.txt")

    def _execute() -> None:
        # ファイルアップロード処理
        with page.expect_file_chooser() as fc_info:
            upload_button.click()
        file_chooser = fc_info.value
        file_chooser.set_files(test_file_path)

        # アップロード後の処理を待機
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)

    benchmark(_execute)


@pytest.mark.e2e
@pytest.mark.parametrize(
    ("tab_name", "upload_index", "file_type", "file_name"),
    [
        pytest.param(f"📝 {texts.tab1.menu_title}", 0, texts.tab1.upload_config, "dns_dig_config.csv", id="e2e_upload_csv_config"),
        pytest.param(f"📝 {texts.tab1.menu_title}", 1, texts.tab1.upload_template, "dns_dig_tmpl.j2", id="e2e_upload_jinja_template"),
        pytest.param(f"📜 {texts.tab2.menu_title}", 0, texts.tab2.upload_debug_config, "cisco_config.toml", id="e2e_upload_toml_config"),
    ],
)
def test_file_upload_parametrized_in_tab1(
    page: Page, tab_name: str, upload_index: int, file_type: str, file_name: str, benchmark: BenchmarkFixture
) -> None:
    """ファイルアップロード機能をパラメータ化してテスト.

    各タブの各アップロード要素で、ファイルアップロード機能が
    正しく動作することを確認します。

    Args:
        page: Playwrightのページオブジェクト
        tab_name: テスト対象のタブ名
        upload_index: ファイルアップローダーのインデックス
        file_type: アップロードするファイルの種類[表示用]
        file_name: アップロードするファイル名
        benchmark: ベンチマーク実行用のフィクスチャ

    Note:
        - タブの切り替えを確認
        - アップロード要素の表示を確認
        - ファイル選択操作を実行
        - アップロード完了を確認
        - 処理時間をベンチマーク
    """

    # Arrange: タブを選択
    helper = StreamlitTestHelper(page)
    helper.select_tab(tab_name)

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
    test_file_path = TestData.get_test_file_path(file_name)

    def _execute() -> None:
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

    benchmark(_execute)


@pytest.mark.e2e
@pytest.mark.parametrize(
    ("file_name", "display_format", "expected_content"),
    [
        pytest.param("cisco_config.toml", "visual", ["hostname", "router"], id="e2e_cisco_config_debug_to_visual"),
        pytest.param("cisco_config.toml", "toml", ["hostname", "router"], id="e2e_cisco_config_debug_to_toml"),
        pytest.param("cisco_config.toml", "yaml", ["hostname", "router"], id="e2e_cisco_config_debug_to_yaml"),
        pytest.param("wget_config.yaml", "visual", ["url", "name"], id="e2e_success_config_debug_yaml_to_visual"),
        pytest.param("wget_config.yaml", "toml", ["url", "name"], id="e2e_success_config_debug_yaml_to_toml"),
        pytest.param("wget_config.yaml", "yaml", ["url", "name"], id="e2e_success_config_debug_yaml_to_yaml"),
        pytest.param("dns_dig_config.csv", "visual", ["resolver", "fqdn", "type"], id="e2e_dns_dig_config_debug_csv_to_visual"),
        pytest.param("dns_dig_config.csv", "toml", ["resolver", "fqdn", "type"], id="e2e_dns_dig_config_debug_csv_to_toml"),
        pytest.param("dns_dig_config.csv", "yaml", ["resolver", "fqdn", "type"], id="e2e_dns_dig_config_debug_csv_to_yaml"),
    ],
)
def test_config_debug_parametrized_in_tab2(
    page: Page, file_name: str, display_format: str, expected_content: List[str], benchmark: BenchmarkFixture
) -> None:
    """設定デバッグ機能をパラメータ化してテスト.

    各種設定ファイルを異なる表示形式で解析し、
    結果が正しく表示されることを確認します。

    Args:
        page: Playwrightのページオブジェクト
        file_name: アップロードするファイル名
        display_format: 表示形式[visual, toml, yaml]
        expected_content: 解析結果に含まれるべき内容のリスト
        benchmark: ベンチマーク実行用のフィクスチャ

    Note:
        - ファイルのアップロードを確認
        - 表示形式の切り替えを確認
        - 解析結果の表示を確認
        - 結果の内容を検証
        - 処理時間をベンチマーク
    """

    # Arrange: 設定デバッグタブを選択
    helper = StreamlitTestHelper(page)
    helper.select_tab(f"📜 {texts.tab2.menu_title}")

    def _execute() -> None:
        helper.upload_debug_config_file(file_name)

        # Act: 解析結果の表示ボタンをクリック
        display_button = helper.get_display_button(display_format)
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
        result_text = helper.get_result_text(tab_panel, display_format)
        helper.verify_result_content(result_text, expected_content, display_format)

    benchmark(_execute)
