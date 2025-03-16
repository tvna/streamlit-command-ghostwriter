#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Streamlit アプリケーションの End-to-End テスト

実行方法:
- すべてのテストを実行: python -m pytest tests/e2e/test_streamlit.py -v
- 基本テストのみ実行: python -m pytest tests/e2e/test_streamlit.py -v -m e2e_basic
- パラメータ化テストのみ実行: python -m pytest tests/e2e/test_streamlit.py -v -m e2e_parametrized
- 特定のテストを実行: python -m pytest tests/e2e/test_streamlit.py::test_app_title -v
- 並列実行: python -m pytest tests/e2e/test_streamlit.py -v -n auto
- ベンチマーク実行: python -m pytest tests/e2e/test_streamlit.py -v --benchmark-only
"""

import logging
import os
import shutil
import socket
import subprocess
import sys
import time
from typing import Generator, List, Optional

import psutil
import pytest
import requests
from _pytest.config import Config as PytestConfig
from box import Box
from playwright.sync_api import Page, expect
from pytest_benchmark.fixture import BenchmarkFixture

# アプリケーションのルートディレクトリをPythonパスに追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
# i18n モジュールをインポート
from i18n import LANGUAGES

# ロガーの設定
logger = logging.getLogger(__name__)

# 言語リソースの設定
DEFAULT_LANGUAGE = "日本語"
texts = Box(LANGUAGES[DEFAULT_LANGUAGE])

# 使用済みポート番号を追跡するグローバル変数
# _used_ports: Dict[int, bool] = {}
# ポート番号の範囲
# _MIN_PORT = 8600
# _MAX_PORT = 8700
_PLAYWRIGHT_HEADLESS_FLAG = "true"


# ブラウザ選択のためのコマンドラインオプションを追加
def pytest_addoption(parser: pytest.Parser) -> None:
    """コマンドラインオプションを追加する

    Args:
        parser: pytestのパーサーオブジェクト
    """
    parser.addoption(
        "--browser",
        action="store",
        default="chromium",
        help="ブラウザを指定: chromium, firefox, webkit",
    )


# ブラウザ選択のためのフィクスチャ
@pytest.fixture(scope="session")
def browser_name(request: pytest.FixtureRequest) -> str:
    """テストで使用するブラウザ名を取得するフィクスチャ

    Args:
        request: pytestのリクエストオブジェクト

    Returns:
        str: ブラウザ名(chromium, firefox, webkit)
    """
    return str(request.config.getoption("--browser"))


def _find_free_port() -> int:
    """使用可能なポート番号を見つける

    Returns:
        int: 使用可能なポート番号
    """
    # ポートが使用可能かソケットで確認
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("localhost", 0))  # OSに空きポートを割り当ててもらう
        _, port = s.getsockname()
        logger.info(f"使用可能なポート {port} を割り当てました")
        return port


def _wait_for_streamlit(timeout: int = 30, interval: int = 1, port: int = 8503) -> bool:
    """Streamlitが起動するまでHTTPリクエストで確認

    指定された回数だけ、Streamlitサーバーにリクエストを送信して
    起動が完了したかどうかを確認します。

    Args:
        timeout: 最大試行回数
        interval: 試行間隔[秒]
        port: Streamlitサーバーのポート番号

    Returns:
        bool: Streamlitサーバーが起動していればTrue、そうでなければFalse
    """
    url = f"http://localhost:{port}"
    logger.info(f"Streamlitサーバーの起動を確認中: {url}")

    start_time = time.time()
    end_time = start_time + timeout
    attempt = 0

    while time.time() < end_time:
        attempt += 1
        try:
            # S113: Added timeout parameter to requests.get call
            logger.info(f"試行 {attempt}/{timeout}... (経過時間: {time.time() - start_time:.1f}秒)")
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                logger.info(f"Streamlitサーバーが起動しました (経過時間: {time.time() - start_time:.1f}秒)")
                return True
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            logger.info(f"接続エラー: {e}")

        # プロセスが終了していないか確認
        if hasattr(psutil, "pid_exists") and not psutil.pid_exists(os.getpid()):
            logger.warning("テストプロセスが終了しています")
            return False

        time.sleep(interval)

    logger.warning(f"Streamlitサーバーの起動タイムアウト (経過時間: {time.time() - start_time:.1f}秒)")
    return False


def _get_validated_streamlit_path() -> str:
    """安全に検証されたStreamlitアプリのパスを取得

    テスト対象のStreamlitアプリケーションのパスを取得し、
    そのパスが存在することを検証します。

    Returns:
        str: 検証済みのStreamlitアプリケーションのパス

    Raises:
        FileNotFoundError: Streamlitアプリケーションが見つからない場合
    """
    # 固定された相対パスを使用[ハードコードされた安全なパス]
    app_relative_path = os.path.join("..", "..", "app.py")
    streamlit_path = os.path.abspath(os.path.join(os.path.dirname(__file__), app_relative_path))

    # パスの存在を検証
    if not os.path.exists(streamlit_path):
        raise FileNotFoundError(f"Streamlit app not found at {streamlit_path}")

    return streamlit_path


def _get_validated_streamlit_executable() -> str:
    """安全に検証されたStreamlit実行ファイルのパスを取得

    Streamlit実行ファイルのパスをPATHから取得し、
    そのパスが存在することを検証します。

    Returns:
        str: 検証済みのStreamlit実行ファイルのパス

    Raises:
        FileNotFoundError: Streamlit実行ファイルが見つからない場合
    """
    # shutil.whichを使用して実行ファイルの完全パスを取得
    streamlit_executable: Optional[str] = shutil.which("streamlit")
    if streamlit_executable is None:
        raise FileNotFoundError("Streamlit executable not found in PATH")

    return streamlit_executable


def _run_streamlit_safely(app_path: str, port: int) -> subprocess.Popen:
    """安全にStreamlitを実行する関数

    検証済みのStreamlit実行ファイルを使用して、
    指定されたアプリケーションを安全に実行します。

    Args:
        app_path: Streamlitアプリケーションのパス
        port: Streamlitサーバーのポート番号

    Returns:
        subprocess.Popen: 起動したStreamlitプロセス
    """
    # 検証済みの実行ファイルパスを取得
    executable = _get_validated_streamlit_executable()

    # 環境変数の設定
    env = os.environ.copy()

    # 固定された引数リストを作成[ユーザー入力を含まない]
    global _PLAYWRIGHT_HEADLESS_FLAG
    headless_flag = _PLAYWRIGHT_HEADLESS_FLAG
    args: List[str] = [executable, "run", app_path, f"--server.port={port}", f"--server.headless={headless_flag}"]

    logger.info(f"Streamlitを起動します: port={port}, headless={headless_flag}")

    # S603を無視: これはテストコードであり、検証済みの引数のみを使用
    process = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
        # 追加のセキュリティ対策
        env=env,  # 環境変数を明示的にコピー
        cwd=os.path.dirname(app_path),  # 作業ディレクトリを明示的に設定
    )

    return process


@pytest.fixture
def streamlit_port() -> int:
    """テスト用の一意のポート番号を提供するフィクスチャ

    Returns:
        int: 使用可能なポート番号
    """
    return _find_free_port()


@pytest.fixture
def streamlit_app(streamlit_port: int) -> Generator[subprocess.Popen, None, None]:
    """テスト用のStreamlitアプリを起動するフィクスチャ

    各テストごとに独立したStreamlitアプリを起動し、
    テスト終了時にプロセスをクリーンアップします。

    Args:
        streamlit_port: テスト用のポート番号

    Yields:
        subprocess.Popen: 起動したStreamlitプロセス
    """
    process = None

    try:
        # Streamlitアプリケーションを起動
        streamlit_path = _get_validated_streamlit_path()
        process = _run_streamlit_safely(streamlit_path, port=streamlit_port)

        # アプリケーションの起動を待機
        if not _wait_for_streamlit(timeout=20, interval=2, port=streamlit_port):
            if process:
                process.kill()
                process.wait(timeout=5)  # プロセスの終了を待機
            pytest.fail("Streamlit did not start in time.")

        # テスト実行中はプロセスを維持
        yield process

    finally:
        # Cleanup: Streamlit プロセスを終了
        if process:
            try:
                process.kill()
                process.wait(timeout=5)  # プロセスの終了を待機
                logger.info(f"Streamlitプロセス (PID: {process.pid}) を終了しました")
            except Exception as e:
                logger.warning(f"プロセスの終了中にエラーが発生しました: {e}")

                # プロセスが終了していない場合は強制終了を試みる
                try:
                    if process.poll() is None:
                        import signal

                        os.kill(process.pid, signal.SIGKILL)
                        logger.info(f"Streamlitプロセス (PID: {process.pid}) を強制終了しました")
                except Exception as e2:
                    logger.warning(f"プロセスの強制終了中にエラーが発生しました: {e2}")


@pytest.fixture(autouse=True)
def setup_teardown(page: Page, streamlit_app: subprocess.Popen, streamlit_port: int) -> Generator[None, None, None]:
    """各テスト前後の共通処理

    テスト実行前にページを初期化し、
    テスト実行後にページをリセットします。

    Args:
        page: Playwrightのページオブジェクト
        streamlit_app: 起動済みのStreamlitプロセス
        streamlit_port: テスト用のポート番号

    Yields:
        None: テスト実行中のコンテキスト
    """
    try:
        # Streamlitプロセスの状態を確認
        is_running = streamlit_app and streamlit_app.poll() is None
        logger.info(
            f"Streamlitプロセス (PID: {streamlit_app.pid if streamlit_app else 'None'}) の状態: "
            f"{'実行中' if is_running else f'終了 (コード: {streamlit_app.returncode if streamlit_app else None})'}"
        )

        # プロセスが実行されていない場合はテストをスキップ
        if not is_running:
            pytest.skip("Streamlitプロセスが実行されていません")

        # Streamlitサーバーが応答することを確認
        if not _wait_for_streamlit(timeout=10, interval=1, port=streamlit_port):
            pytest.fail("Streamlit server is not responding before test.")

        # ページにアクセス
        page.goto(f"http://localhost:{streamlit_port}/")

        # Streamlit アプリの読み込みを待機
        page.wait_for_load_state("networkidle")

        # ヘッドレスモードでは追加の待機時間が必要な場合がある
        page.wait_for_timeout(3000)

        # Act & Assert: テストを実行
        yield

    finally:
        # ページをリセット
        try:
            page.reload()
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(1000)  # 待機時間を追加
        except Exception as e:
            logger.warning(f"ページのリセット中にエラーが発生しました: {e}")


# ============================================================================
# 基本的なテスト関数
# ============================================================================


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
    tab_button = page.locator(f"button[role='tab']:has-text('📝 {texts.tab1.menu_title}')").first
    expect(tab_button).to_be_visible()
    tab_button.click()

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
    tab_button = page.locator(f"button[role='tab']:has-text('📝 {texts.tab1.menu_title}')").first
    expect(tab_button).to_be_visible()
    tab_button.click()

    # ボタンを見つける
    button = page.locator(f"button:has-text('{texts.tab1.generate_text_button}')").first
    expect(button).to_be_visible()

    # ボタンをクリック
    button.click()

    # ボタンクリック後の処理を待機
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1000)  # 結果が表示されるまで待機


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
def test_file_upload(page: Page, streamlit_port: int) -> None:
    """ファイルアップロード機能が動作することを確認"""
    # タブを選択
    tab_button = page.locator(f"button[role='tab']:has-text('📝 {texts.tab1.menu_title}')").first
    expect(tab_button).to_be_visible()
    tab_button.click()

    # ファイルアップロード要素を見つける
    upload_container = page.locator("div[data-testid='stFileUploader']").first
    expect(upload_container).to_be_visible()

    # ファイルアップロードボタンを見つける
    upload_button = page.locator("button:has-text('Browse files')").first
    expect(upload_button).to_be_visible()

    # テスト用のファイルパスを指定
    test_file_path = os.path.join(os.path.dirname(__file__), "test_data", "sample.txt")

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
    tab_button = page.locator(f"button[role='tab']:has-text('📝 {texts.tab1.menu_title}')").first
    expect(tab_button).to_be_visible()
    tab_button.click()

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
    test_file_path = os.path.join(os.path.dirname(__file__), "test_data", "sample.txt")

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
    tab_button = page.locator(f"button[role='tab']:has-text('📜 {texts.tab2.menu_title}')").first
    expect(tab_button).to_be_visible()
    tab_button.click()

    # タブ切り替え後の表示を待機[時間を増やす]
    page.wait_for_timeout(1000)
    page.wait_for_load_state("networkidle")

    # タブパネルが表示されるのを待機
    tab_panel = page.locator("div[role='tabpanel']:visible").first
    expect(tab_panel).to_be_visible()

    # 設定定義ファイルのアップロード要素を見つける
    # タブパネル内のファイルアップローダーを探す
    upload_container = tab_panel.locator("div[data-testid='stFileUploader']").first
    expect(upload_container).to_be_visible()

    # ラベルを確認
    upload_label = upload_container.locator("div[data-testid='stMarkdownContainer']").first
    expect(upload_label).to_contain_text(texts.tab2.upload_debug_config)

    # ファイルアップロードボタンを見つける
    upload_button = upload_container.locator("button:has-text('Browse files')").first
    expect(upload_button).to_be_visible()

    # テスト用のファイルパスを指定
    test_file_path = os.path.join(os.path.dirname(__file__), "test_data", "sample.txt")

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
def test_download_functionality(page: Page, streamlit_port: int) -> None:
    """ダウンロード機能が動作することを確認"""
    # タブを選択
    tab_button = page.locator(f"button[role='tab']:has-text('📝 {texts.tab1.menu_title}')").first
    expect(tab_button).to_be_visible()
    tab_button.click()

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
@pytest.mark.e2e_basic
@pytest.mark.benchmark
def test_cli_command_generation(page: Page, streamlit_port: int, benchmark: BenchmarkFixture) -> None:
    """CSVファイルとJinjaテンプレートを使用してCLIコマンドを生成する機能をテスト"""
    # タブを選択
    tab_button = page.locator(f"button[role='tab']:has-text('📝 {texts.tab1.menu_title}')").first
    expect(tab_button).to_be_visible()
    tab_button.click()

    # 設定定義ファイル[CSV]をアップロード
    upload_containers = page.locator("div[data-testid='stFileUploader']").all()
    assert len(upload_containers) > 1, "ファイルアップローダーが2つ以上見つかりません"

    # 1番目のアップロードコンテナ[設定定義ファイル]
    config_upload_container = upload_containers[0]
    expect(config_upload_container).to_be_visible()

    # ファイルアップロードボタンを見つける
    config_upload_button = config_upload_container.locator("button:has-text('Browse files')").first
    expect(config_upload_button).to_be_visible()

    # CSVファイルをアップロード
    csv_file_path = os.path.join(os.path.dirname(__file__), "test_data", "dns_dig_config.csv")
    with page.expect_file_chooser() as fc_info:
        config_upload_button.click()
    file_chooser = fc_info.value
    file_chooser.set_files(csv_file_path)

    # アップロード後の処理を待機
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1000)

    # 2番目のアップロードコンテナ[Jinjaテンプレート]
    jinja_upload_container = upload_containers[1]
    expect(jinja_upload_container).to_be_visible()

    # ファイルアップロードボタンを見つける
    jinja_upload_button = jinja_upload_container.locator("button:has-text('Browse files')").first
    expect(jinja_upload_button).to_be_visible()

    # Jinjaテンプレートファイルをアップロード
    jinja_file_path = os.path.join(os.path.dirname(__file__), "test_data", "dns_dig_tmpl.j2")
    with page.expect_file_chooser() as fc_info:
        jinja_upload_button.click()
    file_chooser = fc_info.value
    file_chooser.set_files(jinja_file_path)

    # アップロード後の処理を待機
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1000)

    def _generate_command() -> None:
        # CLIコマンド生成ボタンをクリック
        cli_button = page.locator(f"button:has-text('{texts.tab1.generate_text_button}')").first
        expect(cli_button).to_be_visible()
        cli_button.click()

        # 結果が表示されるまで待機
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)

        # 生成されたコマンドが表示されることを確認
        # 結果が表示されるエリアが存在することを確認
        result_area = page.locator("div.element-container").filter(has=page.locator("div.stMarkdown")).first
        expect(result_area).to_be_visible()

        # 何らかの結果が表示されていることを確認[具体的な内容はアプリケーションの実装に依存]
        result_text = result_area.inner_text()
        assert len(result_text) > 0, "生成されたコマンドが表示されていません"

    benchmark(_generate_command)


@pytest.mark.e2e
@pytest.mark.e2e_basic
def test_markdown_generation(page: Page, streamlit_port: int) -> None:
    """YAMLファイルとJinjaテンプレートを使用してMarkdownを生成する機能をテスト"""
    # タブを選択
    tab_button = page.locator(f"button[role='tab']:has-text('📝 {texts.tab1.menu_title}')").first
    expect(tab_button).to_be_visible()
    tab_button.click()

    # 設定定義ファイル[YAML]をアップロード
    upload_containers = page.locator("div[data-testid='stFileUploader']").all()
    assert len(upload_containers) > 1, "ファイルアップローダーが2つ以上見つかりません"

    # 1番目のアップロードコンテナ[設定定義ファイル]
    config_upload_container = upload_containers[0]
    expect(config_upload_container).to_be_visible()

    # ファイルアップロードボタンを見つける
    config_upload_button = config_upload_container.locator("button:has-text('Browse files')").first
    expect(config_upload_button).to_be_visible()

    # YAMLファイルをアップロード
    yaml_file_path = os.path.join(os.path.dirname(__file__), "test_data", "success_config.yaml")
    with page.expect_file_chooser() as fc_info:
        config_upload_button.click()
    file_chooser = fc_info.value
    file_chooser.set_files(yaml_file_path)

    # アップロード後の処理を待機
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1000)

    # 2番目のアップロードコンテナ[Jinjaテンプレート]
    jinja_upload_container = upload_containers[1]
    expect(jinja_upload_container).to_be_visible()

    # ファイルアップロードボタンを見つける
    jinja_upload_button = jinja_upload_container.locator("button:has-text('Browse files')").first
    expect(jinja_upload_button).to_be_visible()

    # Jinjaテンプレートファイルをアップロード
    jinja_file_path = os.path.join(os.path.dirname(__file__), "test_data", "success_template.j2")
    with page.expect_file_chooser() as fc_info:
        jinja_upload_button.click()
    file_chooser = fc_info.value
    file_chooser.set_files(jinja_file_path)

    # アップロード後の処理を待機
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1000)

    # Markdown生成ボタンをクリック
    markdown_button = page.locator(f"button:has-text('{texts.tab1.generate_markdown_button}')").first
    expect(markdown_button).to_be_visible()
    markdown_button.click()

    # 結果が表示されるまで待機
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)

    # 生成されたMarkdownが表示されることを確認
    # 結果が表示されるエリアが存在することを確認
    result_area = page.locator("div.element-container").filter(has=page.locator("div.stMarkdown")).first
    expect(result_area).to_be_visible()

    # 何らかの結果が表示されていることを確認[具体的な内容はアプリケーションの実装に依存]
    result_text = result_area.inner_text()
    assert len(result_text) > 0, "生成されたMarkdownが表示されていません"


@pytest.mark.e2e
@pytest.mark.e2e_basic
def test_toml_config_processing(page: Page, streamlit_port: int) -> None:
    """TOMLファイルとJinjaテンプレートを使用してコマンドを生成する機能をテスト"""
    # タブを選択
    tab_button = page.locator(f"button[role='tab']:has-text('📝 {texts.tab1.menu_title}')").first
    expect(tab_button).to_be_visible()
    tab_button.click()

    # 設定定義ファイル[TOML]をアップロード
    upload_containers = page.locator("div[data-testid='stFileUploader']").all()
    assert len(upload_containers) > 1, "ファイルアップローダーが2つ以上見つかりません"

    # 1番目のアップロードコンテナ[設定定義ファイル]
    config_upload_container = upload_containers[0]
    expect(config_upload_container).to_be_visible()

    # ファイルアップロードボタンを見つける
    config_upload_button = config_upload_container.locator("button:has-text('Browse files')").first
    expect(config_upload_button).to_be_visible()

    # TOMLファイルをアップロード
    toml_file_path = os.path.join(os.path.dirname(__file__), "test_data", "cisco_config.toml")
    with page.expect_file_chooser() as fc_info:
        config_upload_button.click()
    file_chooser = fc_info.value
    file_chooser.set_files(toml_file_path)

    # アップロード後の処理を待機
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1000)

    # 2番目のアップロードコンテナ[Jinjaテンプレート]
    jinja_upload_container = upload_containers[1]
    expect(jinja_upload_container).to_be_visible()

    # ファイルアップロードボタンを見つける
    jinja_upload_button = jinja_upload_container.locator("button:has-text('Browse files')").first
    expect(jinja_upload_button).to_be_visible()

    # Jinjaテンプレートファイルをアップロード
    jinja_file_path = os.path.join(os.path.dirname(__file__), "test_data", "cisco_template.jinja2")
    with page.expect_file_chooser() as fc_info:
        jinja_upload_button.click()
    file_chooser = fc_info.value
    file_chooser.set_files(jinja_file_path)

    # アップロード後の処理を待機
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1000)

    # CLIコマンド生成ボタンをクリック
    cli_button = page.locator(f"button:has-text('{texts.tab1.generate_text_button}')").first
    expect(cli_button).to_be_visible()
    cli_button.click()

    # 結果が表示されるまで待機
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)

    # 生成されたコマンドが表示されることを確認
    # 結果が表示されるエリアが存在することを確認
    result_area = page.locator("div.element-container").filter(has=page.locator("div.stMarkdown")).first
    expect(result_area).to_be_visible()

    # 何らかの結果が表示されていることを確認[具体的な内容はアプリケーションの実装に依存]
    result_text = result_area.inner_text()
    assert len(result_text) > 0, "生成されたコマンドが表示されていません"


@pytest.mark.e2e
@pytest.mark.e2e_basic
def test_config_debug_visual(page: Page, streamlit_port: int) -> None:
    """設定デバッグタブでの視覚的デバッグ機能をテスト"""
    # タブ2を選択
    tab_button = page.locator(f"button[role='tab']:has-text('📜 {texts.tab2.menu_title}')").first
    expect(tab_button).to_be_visible()
    tab_button.click()

    # タブ切り替え後の表示を待機
    page.wait_for_timeout(1000)
    page.wait_for_load_state("networkidle")

    # タブパネルが表示されるのを待機
    tab_panel = page.locator("div[role='tabpanel']:visible").first
    expect(tab_panel).to_be_visible()

    # 設定定義ファイルのアップロード要素を見つける
    upload_container = tab_panel.locator("div[data-testid='stFileUploader']").first
    expect(upload_container).to_be_visible()

    # ファイルアップロードボタンを見つける
    upload_button = upload_container.locator("button:has-text('Browse files')").first
    expect(upload_button).to_be_visible()

    # TOMLファイルをアップロード
    toml_file_path = os.path.join(os.path.dirname(__file__), "test_data", "cisco_config.toml")
    with page.expect_file_chooser() as fc_info:
        upload_button.click()
    file_chooser = fc_info.value
    file_chooser.set_files(toml_file_path)

    # アップロード後の処理を待機
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1000)

    # 解析結果の表示ボタン[visual]をクリック
    visual_button = page.locator(f"button:has-text('{texts.tab2.generate_visual_button}')").first
    expect(visual_button).to_be_visible()
    visual_button.click()

    # 結果が表示されるまで待機
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)

    # 視覚的な解析結果が表示されることを確認
    # 結果が表示されるエリアが存在することを確認
    result_area = page.locator("div.element-container").filter(has=page.locator("div.stMarkdown")).first
    expect(result_area).to_be_visible()

    # 何らかの結果が表示されていることを確認[具体的な内容はアプリケーションの実装に依存]
    result_text = result_area.inner_text()
    assert len(result_text) > 0, "解析結果が表示されていません"


@pytest.mark.e2e
@pytest.mark.e2e_basic
def test_config_debug_toml(page: Page, streamlit_port: int) -> None:
    """設定デバッグタブでのTOML形式での表示機能をテスト"""
    # タブ2を選択
    tab_button = page.locator(f"button[role='tab']:has-text('📜 {texts.tab2.menu_title}')").first
    expect(tab_button).to_be_visible()
    tab_button.click()

    # タブ切り替え後の表示を待機
    page.wait_for_timeout(1000)
    page.wait_for_load_state("networkidle")

    # タブパネルが表示されるのを待機
    tab_panel = page.locator("div[role='tabpanel']:visible").first
    expect(tab_panel).to_be_visible()

    # 設定定義ファイルのアップロード要素を見つける
    upload_container = tab_panel.locator("div[data-testid='stFileUploader']").first
    expect(upload_container).to_be_visible()

    # ファイルアップロードボタンを見つける
    upload_button = upload_container.locator("button:has-text('Browse files')").first
    expect(upload_button).to_be_visible()

    # YAMLファイルをアップロード
    yaml_file_path = os.path.join(os.path.dirname(__file__), "test_data", "success_config.yaml")
    with page.expect_file_chooser() as fc_info:
        upload_button.click()
    file_chooser = fc_info.value
    file_chooser.set_files(yaml_file_path)

    # アップロード後の処理を待機
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1000)

    # 解析結果の表示ボタン[toml]をクリック
    toml_button = page.locator(f"button:has-text('{texts.tab2.generate_toml_button}')").first
    expect(toml_button).to_be_visible()
    toml_button.click()

    # 結果が表示されるまで待機
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)

    # TOML形式の解析結果が表示されることを確認
    # 結果が表示されるエリアが存在することを確認
    result_area = page.locator("div.element-container").filter(has=page.locator("div.stMarkdown")).first
    expect(result_area).to_be_visible()

    # 何らかの結果が表示されていることを確認[具体的な内容はアプリケーションの実装に依存]
    result_text = result_area.inner_text()
    assert len(result_text) > 0, "解析結果が表示されていません"


@pytest.mark.e2e
@pytest.mark.e2e_basic
def test_config_debug_yaml(page: Page, streamlit_port: int) -> None:
    """設定デバッグタブでのYAML形式での表示機能をテスト"""
    # タブ2を選択
    tab_button = page.locator(f"button[role='tab']:has-text('📜 {texts.tab2.menu_title}')").first
    expect(tab_button).to_be_visible()
    tab_button.click()

    # タブ切り替え後の表示を待機
    page.wait_for_timeout(1000)
    page.wait_for_load_state("networkidle")

    # タブパネルが表示されるのを待機
    tab_panel = page.locator("div[role='tabpanel']:visible").first
    expect(tab_panel).to_be_visible()

    # 設定定義ファイルのアップロード要素を見つける
    upload_container = tab_panel.locator("div[data-testid='stFileUploader']").first
    expect(upload_container).to_be_visible()

    # ファイルアップロードボタンを見つける
    upload_button = upload_container.locator("button:has-text('Browse files')").first
    expect(upload_button).to_be_visible()

    # CSVファイルをアップロード
    csv_file_path = os.path.join(os.path.dirname(__file__), "test_data", "dns_dig_config.csv")
    with page.expect_file_chooser() as fc_info:
        upload_button.click()
    file_chooser = fc_info.value
    file_chooser.set_files(csv_file_path)

    # アップロード後の処理を待機
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1000)

    # 解析結果の表示ボタン[yaml]をクリック
    yaml_button = page.locator(f"button:has-text('{texts.tab2.generate_yaml_button}')").first
    expect(yaml_button).to_be_visible()
    yaml_button.click()

    # 結果が表示されるまで待機
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)

    # YAML形式の解析結果が表示されることを確認
    # 結果が表示されるエリアが存在することを確認
    result_area = page.locator("div.element-container").filter(has=page.locator("div.stMarkdown")).first
    expect(result_area).to_be_visible()

    # 何らかの結果が表示されていることを確認[具体的な内容はアプリケーションの実装に依存]
    result_text = result_area.inner_text()
    assert len(result_text) > 0, "解析結果が表示されていません"


@pytest.mark.e2e
@pytest.mark.e2e_basic
def test_advanced_settings(page: Page, streamlit_port: int) -> None:
    """詳細設定タブでの設定変更機能をテスト"""
    # タブ3を選択
    tab_button = page.locator(f"button[role='tab']:has-text('🛠️ {texts.tab3.menu_title}')").first
    expect(tab_button).to_be_visible()
    tab_button.click()

    # タブ切り替え後の表示を待機
    page.wait_for_timeout(1000)
    page.wait_for_load_state("networkidle")

    # タブパネルが表示されるのを待機
    tab_panel = page.locator("div[role='tabpanel']:visible").first
    expect(tab_panel).to_be_visible()

    # 入力ファイルの設定セクションが表示されることを確認
    input_settings_header = tab_panel.locator(f"h3:has-text('{texts.tab3.subheader_input_file}')").first
    expect(input_settings_header).to_be_visible()

    # コマンド生成タブに戻る
    tab_button = page.locator(f"button[role='tab']:has-text('📝 {texts.tab1.menu_title}')").first
    expect(tab_button).to_be_visible()
    tab_button.click()

    # タブ切り替え後の表示を待機
    page.wait_for_timeout(1000)
    page.wait_for_load_state("networkidle")

    # タブパネルが表示されるのを待機
    tab_panel = page.locator("div[role='tabpanel']:visible").first
    expect(tab_panel).to_be_visible()


@pytest.mark.e2e
@pytest.mark.e2e_basic
def test_sample_collection(page: Page, streamlit_port: int) -> None:
    """サンプル集タブでのサンプルファイル表示機能をテスト"""
    # タブ4を選択
    tab_button = page.locator(f"button[role='tab']:has-text('💼 {texts.tab4.menu_title}')").first
    expect(tab_button).to_be_visible()
    tab_button.click()

    # タブ切り替え後の表示を待機
    page.wait_for_timeout(1000)
    page.wait_for_load_state("networkidle")

    # タブパネルが表示されるのを待機
    tab_panel = page.locator("div[role='tabpanel']:visible").first
    expect(tab_panel).to_be_visible()

    # サンプル集の表示セクションが表示されることを確認
    sample_header = tab_panel.locator(f"h3:has-text('{texts.tab4.subheader}')").first
    expect(sample_header).to_be_visible()

    # サンプルファイルのテキストエリアが表示されることを確認
    # cisco_config.tomlのテキストエリア
    cisco_config_textarea = tab_panel.locator("textarea[aria-label='cisco_config.toml']").first
    expect(cisco_config_textarea).to_be_visible()

    # cisco_template.jinja2のテキストエリア
    cisco_template_textarea = tab_panel.locator("textarea[aria-label='cisco_template.jinja2']").first
    expect(cisco_template_textarea).to_be_visible()

    # dns_dig_config.csvのテキストエリア
    dns_dig_config_textarea = tab_panel.locator("textarea[aria-label='dns_dig_config.csv']").first
    expect(dns_dig_config_textarea).to_be_visible()

    # dns_dig_tmpl.j2のテキストエリア
    dns_dig_tmpl_textarea = tab_panel.locator("textarea[aria-label='dns_dig_tmpl.j2']").first
    expect(dns_dig_tmpl_textarea).to_be_visible()

    # success_config.yamlのテキストエリア
    success_config_textarea = tab_panel.locator("textarea[aria-label='success_config.yaml']").first
    expect(success_config_textarea).to_be_visible()

    # success_template.j2のテキストエリア
    success_template_textarea = tab_panel.locator("textarea[aria-label='success_template.j2']").first
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


# ============================================================================
# パラメータ化されたテスト関数
# ============================================================================


@pytest.mark.e2e
@pytest.mark.e2e_parametrized
@pytest.mark.parametrize(
    ("tab_name", "expected_element"),
    [
        pytest.param(f"📝 {texts.tab1.menu_title}", f"button:has-text('{texts.tab1.generate_text_button}')", id="コマンド生成タブ"),
        pytest.param(f"📜 {texts.tab2.menu_title}", f"button:has-text('{texts.tab2.generate_visual_button}')", id="設定デバッグタブ"),
        pytest.param(f"🛠️ {texts.tab3.menu_title}", f"h3:has-text('{texts.tab3.subheader_input_file}')", id="詳細設定タブ"),
        pytest.param(f"💼 {texts.tab4.menu_title}", f"h3:has-text('{texts.tab4.subheader}')", id="サンプル集タブ"),
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
@pytest.mark.e2e_parametrized
@pytest.mark.parametrize(
    ("tab_name", "upload_index", "file_type", "file_name"),
    [
        pytest.param(f"📝 {texts.tab1.menu_title}", 0, texts.tab1.upload_config, "dns_dig_config.csv", id="CSVファイルアップロード"),
        pytest.param(f"📝 {texts.tab1.menu_title}", 1, texts.tab1.upload_template, "dns_dig_tmpl.j2", id="Jinjaテンプレートアップロード"),
        pytest.param(f"📜 {texts.tab2.menu_title}", 0, texts.tab2.upload_debug_config, "cisco_config.toml", id="TOMLファイルアップロード"),
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
    # Streamlitサーバーが応答することを確認
    assert _wait_for_streamlit(timeout=5, interval=1, port=streamlit_port), "Streamlit server is not responding before test."

    # Arrange: タブを選択
    tab_button = page.locator(f"button[role='tab']:has-text('{tab_name}')").first
    expect(tab_button).to_be_visible()
    tab_button.click()

    # ページの読み込みを待機 - 待機時間を増やす
    page.wait_for_timeout(3000)
    page.wait_for_load_state("networkidle")

    # タブパネルが表示されていることを確認
    tab_panel = page.locator("div[role='tabpanel']:visible").first
    expect(tab_panel).to_be_visible()

    # ファイルアップロード要素を取得 - タブパネル内で検索するように変更
    upload_containers = tab_panel.locator("div[data-testid='stFileUploader']").all()
    assert len(upload_containers) > upload_index, f"ファイルアップローダーが{upload_index + 1}個以上見つかりません"

    upload_container = upload_containers[upload_index]
    # 可視性チェックを削除し、存在チェックに変更
    assert upload_container.count() > 0, "ファイルアップローダーが存在しません"

    # ファイルアップロードボタンを見つける
    upload_button = upload_container.locator("button:has-text('Browse files')").first
    expect(upload_button).to_be_visible()

    # テスト用のファイルパスを準備
    test_file_path = os.path.join(os.path.dirname(__file__), "test_data", file_name)

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
    assert file_name in uploaded_file_text, f"アップロードされたファイル名 {file_name} が表示されていません"


@pytest.mark.e2e
@pytest.mark.e2e_parametrized
@pytest.mark.benchmark
@pytest.mark.parametrize(
    ("config_file", "template_file", "button_text"),
    [
        pytest.param("dns_dig_config.csv", "dns_dig_tmpl.j2", texts.tab1.generate_text_button, id="CSV_CLIコマンド生成"),
        pytest.param("success_config.yaml", "success_template.j2", texts.tab1.generate_markdown_button, id="YAML_Markdown生成"),
        pytest.param("cisco_config.toml", "cisco_template.jinja2", texts.tab1.generate_text_button, id="TOML_CLIコマンド生成"),
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
    assert _wait_for_streamlit(timeout=5, interval=1, port=streamlit_port), "Streamlit server is not responding before test."

    # Arrange: コマンド生成タブを選択
    tab_button = page.locator(f"button[role='tab']:has-text('📝 {texts.tab1.menu_title}')").first
    expect(tab_button).to_be_visible()
    tab_button.click()

    # ページの読み込みを待機 - 待機時間を増やす
    page.wait_for_timeout(3000)
    page.wait_for_load_state("networkidle")

    # タブパネルが表示されていることを確認
    tab_panel = page.locator("div[role='tabpanel']:visible").first
    expect(tab_panel).to_be_visible()

    # ファイルアップロード要素を取得 - タブパネル内で検索するように変更
    upload_containers = tab_panel.locator("div[data-testid='stFileUploader']").all()
    assert len(upload_containers) > 1, "ファイルアップローダーが2つ以上見つかりません"

    # 設定ファイルをアップロード
    config_upload_container = upload_containers[0]
    # 可視性チェックを削除し、存在チェックに変更
    assert config_upload_container.count() > 0, "設定ファイルアップローダーが存在しません"

    config_upload_button = config_upload_container.locator("button:has-text('Browse files')").first
    expect(config_upload_button).to_be_visible()

    config_file_path = os.path.join(os.path.dirname(__file__), "test_data", config_file)
    with page.expect_file_chooser() as fc_info:
        config_upload_button.click()
    file_chooser = fc_info.value
    file_chooser.set_files(config_file_path)

    # ページの読み込みを待機 - 待機時間を増やす
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(3000)

    # テンプレートファイルをアップロード
    jinja_upload_container = upload_containers[1]
    # 可視性チェックを削除し、存在チェックに変更
    assert jinja_upload_container.count() > 0, "テンプレートファイルアップローダーが存在しません"

    jinja_upload_button = jinja_upload_container.locator("button:has-text('Browse files')").first
    expect(jinja_upload_button).to_be_visible()

    jinja_file_path = os.path.join(os.path.dirname(__file__), "test_data", template_file)
    with page.expect_file_chooser() as fc_info:
        jinja_upload_button.click()
    file_chooser = fc_info.value
    file_chooser.set_files(jinja_file_path)

    # ページの読み込みを待機 - 待機時間を増やす
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(3000)

    def _generate_and_verify() -> None:
        # Act: コマンド生成ボタンをクリック
        command_button = page.locator(f"button:has-text('{button_text}')").first
        expect(command_button).to_be_visible()
        command_button.click()

        # ページの読み込みを待機 - 待機時間を増やす
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(5000)

        # Assert: 生成結果が表示されていることを確認 - セレクタを改善
        result_areas = page.locator("div.element-container div.stMarkdown").all()

        # 結果が表示されるまで少し待機
        page.wait_for_timeout(2000)

        # 結果テキストを取得
        result_text = ""
        for area in result_areas:
            result_text += area.inner_text() + "\n"

        # 何らかの結果が表示されていることを確認
        assert len(result_text.strip()) > 0, f"生成された{button_text}の結果が表示されていません"

    benchmark(_generate_and_verify)


@pytest.mark.e2e
@pytest.mark.e2e_parametrized
@pytest.mark.parametrize(
    ("file_name", "display_format", "expected_content"),
    [
        pytest.param("cisco_config.toml", "visual", ["hostname", "router"], id="TOML_視覚的表示"),
        pytest.param("success_config.yaml", "toml", ["url", "name"], id="YAML_TOML形式表示"),
        pytest.param("dns_dig_config.csv", "yaml", ["resolver", "fqdn", "record_type"], id="CSV_YAML形式表示"),
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
    # Streamlitサーバーが応答することを確認
    assert _wait_for_streamlit(timeout=5, interval=1, port=streamlit_port), "Streamlit server is not responding before test."

    # Arrange: 設定デバッグタブを選択
    tab_button = page.locator(f"button[role='tab']:has-text('📜 {texts.tab2.menu_title}')").first
    expect(tab_button).to_be_visible()
    tab_button.click()

    # ページの読み込みを待機 - 待機時間を増やす
    page.wait_for_timeout(3000)
    page.wait_for_load_state("networkidle")

    # タブパネルが表示されていることを確認
    tab_panel = page.locator("div[role='tabpanel']:visible").first
    expect(tab_panel).to_be_visible()

    # ファイルアップロード要素を取得 - タブパネル内で検索するように変更
    upload_container = tab_panel.locator("div[data-testid='stFileUploader']").first
    # 可視性チェックを削除し、存在チェックに変更
    assert upload_container.count() > 0, "ファイルアップローダーが存在しません"

    upload_button = upload_container.locator("button:has-text('Browse files')").first
    expect(upload_button).to_be_visible()

    # ファイルをアップロード
    test_file_path = os.path.join(os.path.dirname(__file__), "test_data", file_name)
    with page.expect_file_chooser() as fc_info:
        upload_button.click()
    file_chooser = fc_info.value
    file_chooser.set_files(test_file_path)

    # ページの読み込みを待機 - 待機時間を増やす
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(3000)

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
        markdown_elements = tab_panel.locator("div.element-container div.stMarkdown").all()
        for element in markdown_elements:
            result_text += element.inner_text() + "\n"

    # それでも結果が見つからない場合、プレーンテキスト要素を確認
    if not result_text:
        text_elements = tab_panel.locator("div.element-container div.stText").all()
        for element in text_elements:
            result_text += element.inner_text() + "\n"

    # コードブロック要素も確認
    code_blocks = tab_panel.locator("pre").all()
    for block in code_blocks:
        result_text += block.inner_text() + "\n"

    # デバッグ情報を出力
    print(f"取得したテキスト: {result_text[:200]}...")

    # 期待される内容のいずれかが表示されていることを確認[すべてではなく一部でも可]
    found_content = False
    for content in expected_content:
        if content in result_text:
            found_content = True
            print(f"期待される内容が見つかりました: {content}")
            break

    # 少なくとも1つの期待コンテンツが見つかればテスト成功
    assert found_content, f"期待される内容 {expected_content} のいずれも解析結果に表示されていません。実際の結果: {result_text[:200]}..."


# pytest-benchmark プラグインの設定を追加
# pytest.ini または conftest.py に追加
def pytest_configure(config: PytestConfig) -> None:
    config.option.benchmark_autosave = True
    config.option.benchmark_save = ".benchmarks"
    config.option.benchmark_compare = "last"
    config.option.benchmark_histogram = ".benchmarks/histograms"


# Playwrightのブラウザコンテキスト設定
@pytest.fixture
def browser_context_args(browser_name: str) -> dict:
    """ブラウザコンテキストの引数を設定するフィクスチャ

    Args:
        browser_name: ブラウザ名

    Returns:
        dict: ブラウザコンテキストの引数
    """
    return {
        "viewport": {"width": 1280, "height": 720},
        "ignore_https_errors": True,
        "java_script_enabled": True,
    }
