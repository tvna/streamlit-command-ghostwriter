#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
pytest の設定ファイル
CI環境でのテスト実行をサポートするための設定を含みます。
"""

import logging
import os
import shutil
import socket
import subprocess
import sys
import time
from typing import Any, Dict, Generator, List, Optional

import psutil
import pytest
import requests
from _pytest.config import Config as PytestConfig
from playwright.sync_api import Page

# アプリケーションのルートディレクトリをPythonパスに追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# ロガーの設定
logger = logging.getLogger(__name__)

# Playwrightのヘッドレスモード設定
_PLAYWRIGHT_HEADLESS_FLAG = "true"


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args: Dict[str, Any]) -> Dict[str, Any]:
    """ブラウザ起動時の引数を設定

    Args:
        browser_type_launch_args: 既存のブラウザ起動引数

    Returns:
        Dict[str, Any]: 更新されたブラウザ起動引数
    """
    # CI環境かどうかを確認
    is_ci = os.environ.get("CI") == "true" or os.environ.get("GITHUB_ACTIONS") == "true"

    return {
        **browser_type_launch_args,
        # CI環境ではヘッドレスモードで実行
        "headless": is_ci,
        "args": ["--no-sandbox", "--disable-dev-shm-usage"],
    }


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args: Dict[str, Any]) -> Dict[str, Any]:
    """ブラウザコンテキストの引数を設定

    Args:
        browser_context_args: 既存のブラウザコンテキスト引数

    Returns:
        Dict[str, Any]: 更新されたブラウザコンテキスト引数
    """
    return {
        **browser_context_args,
        # ブラウザの言語設定
        "locale": "ja-JP",
        # ブラウザのタイムゾーン設定
        "timezone_id": "Asia/Tokyo",
        # ブラウザの権限設定
        "permissions": ["geolocation"],
        # ブラウザの viewport 設定
        "viewport": {
            "width": 1280,
            "height": 720,
        },
        "ignore_https_errors": True,
        "java_script_enabled": True,
    }


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
        timeout: 最大待機時間（秒）
        interval: 試行間隔（秒）
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


# pytest-benchmark プラグインの設定を追加
def pytest_configure(config: PytestConfig) -> None:
    """pytestの設定を構成する

    Args:
        config: pytestの設定オブジェクト
    """
    config.option.benchmark_autosave = True
    config.option.benchmark_save = ".benchmarks"
    config.option.benchmark_compare = "last"
    config.option.benchmark_histogram = ".benchmarks/histograms"
