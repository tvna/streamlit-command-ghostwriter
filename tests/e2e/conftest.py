#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
pytest の設定ファイル
CI環境でのテスト実行をサポートするための設定を含みます。
"""

import os

import pytest
from playwright.sync_api import Browser, Playwright


@pytest.fixture(scope="session")
def playwright_browser_type(playwright: Playwright) -> Browser:
    """Playwrightのブラウザタイプを設定するフィクスチャ

    CI環境では常にヘッドレスモードで実行します。

    Args:
        playwright: Playwrightインスタンス

    Returns:
        browser: 設定されたブラウザインスタンス
    """
    # CI環境かどうかを確認
    is_ci = os.environ.get("CI") == "true" or os.environ.get("GITHUB_ACTIONS") == "true"

    # ブラウザの起動オプション
    launch_options = {
        "headless": is_ci,  # CI環境ではヘッドレスモードで実行
        "args": ["--no-sandbox", "--disable-dev-shm-usage"],
    }

    # Chromiumブラウザを使用
    browser_type = playwright.chromium
    return browser_type.launch(**launch_options)


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args: dict) -> dict:
    """ブラウザコンテキストの引数を設定"""
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
    }


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args: dict) -> dict:
    """ブラウザ起動時の引数を設定"""
    return {
        **browser_type_launch_args,
        # ヘッドレスモードを有効化 [テスト実行時にブラウザを表示しない]
        "headless": True,
        # デバッグが必要な場合は以下の設定を有効にしてください
        # "headless": False,
        # "slow_mo": 100,
    }
