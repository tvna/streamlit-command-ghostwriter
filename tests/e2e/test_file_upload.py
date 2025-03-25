#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Streamlit アプリケーションのファイルアップロード機能のテスト

実行方法:
- すべてのテストを実行: python -m pytest tests/e2e/test_file_upload.py -v
- 特定のテストを実行: python -m pytest tests/e2e/test_file_upload.py::test_file_upload -v
"""

import pytest
from playwright.sync_api import Page, expect

# test_utils から関数とテキストリソースをインポート
from .test_utils import get_test_file_path, select_tab, texts


@pytest.mark.e2e
@pytest.mark.e2e_basic
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
@pytest.mark.e2e_basic
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
@pytest.mark.e2e_basic
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
@pytest.mark.e2e_parametrized
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
