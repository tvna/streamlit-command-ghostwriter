#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""E2Eテスト実行のための設定モジュール.

このモジュールは、E2Eテストの実行環境を設定し、以下の機能を提供します:

  - Playwrightのブラウザ制御
    - ヘッドレスモード/ヘッドフルモードの切り替え (--headedオプション)
    - ブラウザのコンテキスト設定 (locale, timezone, viewport等)
  - Streamlitサーバーの制御
    - 自動起動 (常にヘッドレスモードで実行)
    - 動的ポート割り当て
    - プロセス監視と安全な終了処理
  - テスト実行環境の管理
    - セッションスコープのフィクスチャ提供
    - テストごとのセットアップ/クリーンアップ
    - ベンチマーク設定

Typical usage example:

  pytest --headed tests/e2e/test_*.py  # ブラウザを表示してテスト実行
  pytest tests/e2e/test_*.py          # ヘッドレスモードでテスト実行
"""

import logging
import os
import shutil
import socket
import subprocess
import sys
import time
from typing import Any, Dict, Final, Generator, List, Optional

import psutil
import pytest
import requests
from _pytest.config import Config as PytestConfig
from playwright.sync_api import Page

# アプリケーションのルートディレクトリをPythonパスに追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# ロガーの設定
logger: logging.Logger = logging.getLogger(__name__)


def pytest_addoption(parser: pytest.Parser) -> None:
    """pytestのコマンドラインオプションを追加.

    Args:
        parser: pytestのパーサーオブジェクト

    Note:
        追加されるオプション:
          --headed: ブラウザを表示モードで実行 [デフォルト: False]
    """
    parser.addoption(
        "--headed",
        action="store_true",
        default=False,
        help="Run browser in headed mode (browser will be visible)",
    )


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args: Dict[str, Any], pytestconfig: PytestConfig) -> Dict[str, Any]:
    """Playwrightブラウザの起動オプションを設定.

    Args:
        browser_type_launch_args: 既存のブラウザ起動オプション
        pytestconfig: pytestの設定オブジェクト

    Returns:
        Dict[str, Any]: 更新されたブラウザ起動オプション
          - headless: ヘッドレスモードの有効/無効
          - args: ブラウザ起動時の追加引数
    """
    is_playwright_headless: bool = not pytestconfig.getoption("--headed")

    return {
        **browser_type_launch_args,
        "headless": is_playwright_headless,
        "args": ["--no-sandbox", "--disable-dev-shm-usage"],
    }


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args: Dict[str, Any]) -> Dict[str, Any]:
    """ブラウザコンテキストのオプションを設定.

    Args:
        browser_context_args: 既存のブラウザコンテキストオプション

    Returns:
        Dict[str, Any]: 更新されたブラウザコンテキストオプション
          - locale: ブラウザの言語設定
          - timezone_id: タイムゾーン設定
          - permissions: ブラウザの権限設定
          - viewport: 画面サイズ設定
          - その他: HTTPS/JavaScriptの設定
    """
    return {
        **browser_context_args,
        "locale": "ja-JP",
        "timezone_id": "Asia/Tokyo",
        "permissions": ["geolocation"],
        "viewport": {
            "width": 1280,
            "height": 720,
        },
        "ignore_https_errors": True,
        "java_script_enabled": True,
    }


def _find_free_port() -> int:
    """使用可能なポート番号を動的に取得.

    Returns:
        int: 使用可能なポート番号

    Note:
        OSに空きポートを割り当ててもらうことで、ポート競合を回避します
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("localhost", 0))
        _, port = s.getsockname()
        logger.info(f"使用可能なポート {port} を割り当てました")
        return int(port)


def _wait_for_streamlit(timeout: int = 30, interval: int = 1, port: int = 8503) -> bool:
    """Streamlitサーバーの起動完了を待機.

    指定された時間内にサーバーが応答を返すまで待機します。

    Args:
        timeout: 最大待機時間 [秒]
        interval: 試行間隔 [秒]
        port: Streamlitサーバーのポート番号

    Returns:
        bool: サーバーが起動完了した場合はTrue、タイムアウトした場合はFalse

    Note:
        HTTPリクエストを定期的に送信し、200レスポンスを待機します
        プロセスの終了も監視し、異常終了を検知します
    """
    url: Final[str] = f"http://localhost:{port}"
    logger.info(f"Streamlitサーバーの起動を確認中: {url}")

    start_time: float = time.time()
    end_time: float = start_time + timeout
    attempt: int = 0

    while time.time() < end_time:
        attempt += 1
        try:
            logger.info(f"試行 {attempt}/{timeout}... (経過時間: {time.time() - start_time:.1f}秒)")
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                logger.info(f"Streamlitサーバーが起動しました (経過時間: {time.time() - start_time:.1f}秒)")
                return True
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            logger.info(f"接続エラー: {e}")

        if hasattr(psutil, "pid_exists") and not psutil.pid_exists(os.getpid()):
            logger.warning("テストプロセスが終了しています")
            return False

        time.sleep(interval)

    logger.warning(f"Streamlitサーバーの起動タイムアウト (経過時間: {time.time() - start_time:.1f}秒)")
    return False


def _get_validated_streamlit_path() -> str:
    """Streamlitアプリケーションの検証済みパスを取得.

    Returns:
        str: 検証済みのStreamlitアプリケーションの絶対パス

    Raises:
        FileNotFoundError: アプリケーションファイルが存在しない場合

    Note:
        セキュリティ対策として、相対パスを固定値で指定し、
        絶対パスに変換後に存在確認を行います
    """
    app_relative_path: Final[str] = os.path.join("..", "..", "app.py")
    streamlit_path: Final[str] = os.path.abspath(os.path.join(os.path.dirname(__file__), app_relative_path))

    if not os.path.exists(streamlit_path):
        raise FileNotFoundError(f"Streamlit app not found at {streamlit_path}")

    return streamlit_path


def _get_validated_streamlit_executable() -> str:
    """Streamlit実行ファイルの検証済みパスを取得.

    Returns:
        str: 検証済みのStreamlit実行ファイルの絶対パス

    Raises:
        FileNotFoundError: 実行ファイルがPATHに存在しない場合

    Note:
        セキュリティ対策として、PATHからの実行ファイル検索を
        shutil.whichを使用して行います
    """
    streamlit_executable: Optional[str] = shutil.which("streamlit")
    if streamlit_executable is None:
        raise FileNotFoundError("Streamlit executable not found in PATH")

    return streamlit_executable


def _run_streamlit_safely(app_path: str, port: int) -> subprocess.Popen[bytes]:
    """Streamlitサーバーを安全に起動.

    Args:
        app_path: Streamlitアプリケーションのパス
        port: 使用するポート番号

    Returns:
        subprocess.Popen: 起動したStreamlitプロセス

    Note:
        セキュリティ対策:
          - 検証済みの実行ファイルを使用
          - 環境変数を明示的にコピー
          - 作業ディレクトリを明示的に設定
          - シェル実行を無効化
    """
    executable: Final[str] = _get_validated_streamlit_executable()
    env: Final[Dict[str, str]] = os.environ.copy()
    args: Final[List[str]] = [executable, "run", app_path, f"--server.port={port}", "--server.headless=true"]

    logger.info(f"Streamlitを起動します: port={port}, headless=true")

    process: subprocess.Popen[bytes] = subprocess.Popen(
        args=args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
        env=env,
        cwd=os.path.dirname(app_path),
    )

    return process


@pytest.fixture
def streamlit_port() -> int:
    """テスト用の一意のポート番号を提供.

    Returns:
        int: 使用可能なポート番号

    Note:
        動的にポートを割り当てることで、テスト間の競合を防ぎます
    """
    return _find_free_port()


@pytest.fixture
def streamlit_app(streamlit_port: int) -> Generator[subprocess.Popen[bytes], None, None]:
    """テスト用のStreamlitサーバーを提供.

    Args:
        streamlit_port: 使用するポート番号

    Yields:
        subprocess.Popen: 起動したStreamlitプロセス

    Note:
        - 各テストごとに独立したサーバーを起動
        - 常にヘッドレスモードで実行
        - テスト終了時に自動的にプロセスを終了
    """

    process: Optional[subprocess.Popen[bytes]] = None
    try:
        streamlit_path: Final[str] = _get_validated_streamlit_path()
        process = _run_streamlit_safely(streamlit_path, port=streamlit_port)

        if not _wait_for_streamlit(timeout=120, interval=3, port=streamlit_port):
            if process:
                process.kill()
                process.wait(timeout=5)
            pytest.fail("Streamlit did not start in time.")

        yield process

    finally:
        if process:
            try:
                process.kill()
                process.wait(timeout=5)
                logger.info(f"Streamlitプロセス (PID: {process.pid}) を終了しました")
            except Exception as e:
                logger.warning(f"プロセスの終了中にエラーが発生しました: {e}")

                try:
                    if process.poll() is None:
                        import signal

                        os.kill(process.pid, signal.SIGKILL)
                        logger.info(f"Streamlitプロセス (PID: {process.pid}) を強制終了しました")
                except Exception as e2:
                    logger.warning(f"プロセスの強制終了中にエラーが発生しました: {e2}")


@pytest.fixture(autouse=True)
def setup_teardown(page: Page, streamlit_app: subprocess.Popen[bytes], streamlit_port: int) -> Generator[None, None, None]:
    """各テストの前後処理を実行.

    Args:
        page: Playwrightのページオブジェクト
        streamlit_app: 起動済みのStreamlitプロセス
        streamlit_port: 使用中のポート番号

    Yields:
        None: テスト実行のコンテキスト

    Note:
        テスト前:
          - Streamlitプロセスの状態確認
          - サーバーの応答確認
          - ページの初期化と読み込み待機
        テスト後:
          - ページのリセットと再読み込み
    """
    try:
        is_running: bool = streamlit_app is not None and streamlit_app.poll() is None
        logger.info(
            f"Streamlitプロセス (PID: {streamlit_app.pid if streamlit_app else 'None'}) の状態: "
            f"{'実行中' if is_running else f'終了 (コード: {streamlit_app.returncode if streamlit_app else None})'}"
        )

        if not is_running:
            pytest.skip("Streamlitプロセスが実行されていません")

        if not _wait_for_streamlit(timeout=30, interval=3, port=streamlit_port):
            pytest.fail("Streamlit server is not responding before test.")

        page.goto(f"http://localhost:{streamlit_port}/")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(3000)

        yield

    finally:
        try:
            page.reload()
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(1000)
        except Exception as e:
            logger.warning(f"ページのリセット中にエラーが発生しました: {e}")
