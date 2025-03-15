#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
pytest の設定ファイル
"""

import pytest


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
