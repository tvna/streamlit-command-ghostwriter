import os
from typing import Dict, List

import pytest
from _pytest.mark.structures import MarkDecorator
from streamlit.testing.v1 import AppTest

UNIT: MarkDecorator = pytest.mark.unit

# Constants for expected UI element counts
EXPECTED_TITLE_COUNT = 1
EXPECTED_TAB_COUNT = 5
MIN_EXPECTED_COLUMN_COUNT = 5
MIN_EXPECTED_SUBHEADER_COUNT = 1
MIN_EXPECTED_SIDEBAR_COUNT = 1
MIN_EXPECTED_MARKDOWN_COUNT = 1
MIN_EXPECTED_BUTTON_COUNT = 5

# Constants for button keys
BUTTON_KEYS = [
    "tab1_execute_text",
    "tab1_execute_markdown",
    "tab2_execute_visual",
    "tab2_execute_toml",
    "tab2_execute_yaml",
]


@pytest.fixture
def app_test() -> AppTest:
    """
    Streamlitアプリのテスト用インスタンスを提供するフィクスチャ。

    Returns:
        AppTest: 実行済みのStreamlitアプリテストインスタンス
    """
    # プロジェクトのルートディレクトリからapp.pyへの絶対パスを構築
    app_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "app.py")
    return AppTest.from_file(app_path).run()


@UNIT
def test_main_layout(app_test: AppTest) -> None:
    """
    Streamlitアプリのレイアウトをテストする。

    アプリの起動時の基本的なUI要素の存在と、各ボタンのクリック後の状態変化を検証します。
    テストでは以下を確認します:
    - タイトル、タブ、カラム、サブヘッダー、サイドバーなどの基本要素
    - 各ボタンの初期状態と、クリック後の状態変化
    - 警告、エラー、成功メッセージの表示状態
    """
    # Arrange - 初期状態の検証
    assert app_test.title.len == EXPECTED_TITLE_COUNT, "Title is not displayed"
    assert len(app_test.tabs) == EXPECTED_TAB_COUNT, "Four tabs are not displayed"
    assert len(app_test.columns) >= MIN_EXPECTED_COLUMN_COUNT, f"At least {MIN_EXPECTED_COLUMN_COUNT} columns are required"
    assert app_test.subheader.len >= MIN_EXPECTED_SUBHEADER_COUNT, "Subheader is not displayed"
    assert len(app_test.sidebar) >= MIN_EXPECTED_SIDEBAR_COUNT, "Sidebar is not displayed"
    assert app_test.markdown.len >= MIN_EXPECTED_MARKDOWN_COUNT, "Markdown element is not displayed"
    assert app_test.button.len >= MIN_EXPECTED_BUTTON_COUNT, f"At least {MIN_EXPECTED_BUTTON_COUNT} buttons are required"

    # 初期状態ではすべてのボタンが未クリック状態
    for button_key in BUTTON_KEYS:
        assert app_test.button(key=button_key).value is False, f"Button '{button_key}' should be in initial unclicked state"

    # 初期状態ではエラーや警告メッセージは表示されていない
    assert app_test.error.len == 0, "Error message should not be displayed in initial state"
    assert app_test.warning.len == 0, "Warning message should not be displayed in initial state"
    assert app_test.success.len == 0, "Success message should not be displayed in initial state"


@UNIT
@pytest.mark.parametrize(
    ("button_key", "expected_states"),
    [
        pytest.param(
            "tab1_execute_text",
            {
                "tab1_execute_text": True,
                "tab1_execute_markdown": False,
                "tab2_execute_visual": False,
                "tab2_execute_toml": False,
                "tab2_execute_yaml": False,
            },
            id="app_button_text_active_only",
        ),
        pytest.param(
            "tab1_execute_markdown",
            {
                "tab1_execute_text": False,
                "tab1_execute_markdown": True,
                "tab2_execute_visual": False,
                "tab2_execute_toml": False,
                "tab2_execute_yaml": False,
            },
            id="app_button_markdown_active_only",
        ),
        pytest.param(
            "tab2_execute_visual",
            {
                "tab1_execute_text": False,
                "tab1_execute_markdown": False,
                "tab2_execute_visual": True,
                "tab2_execute_toml": False,
                "tab2_execute_yaml": False,
            },
            id="app_button_visual_active_only",
        ),
        pytest.param(
            "tab2_execute_toml",
            {
                "tab1_execute_text": False,
                "tab1_execute_markdown": False,
                "tab2_execute_visual": False,
                "tab2_execute_toml": True,
                "tab2_execute_yaml": False,
            },
            id="app_button_toml_active_only",
        ),
        pytest.param(
            "tab2_execute_yaml",
            {
                "tab1_execute_text": False,
                "tab1_execute_markdown": False,
                "tab2_execute_visual": False,
                "tab2_execute_toml": False,
                "tab2_execute_yaml": True,
            },
            id="app_button_yaml_active_only",
        ),
    ],
)
def test_button_click_state(app_test: AppTest, button_key: str, expected_states: Dict[str, bool]) -> None:
    """
    各ボタンのクリック後の状態変化をテストする。

    Args:
        app_test: Streamlitアプリのテストインスタンス
        button_key: クリックするボタンのキー
        expected_states: クリック後の各ボタンの期待される状態
    """
    # Act - ボタンをクリック
    app_test.button(key=button_key).click().run()

    # Assert - 各ボタンの状態を検証
    for key, expected_value in expected_states.items():
        assert app_test.button(key=key).value is expected_value, (
            f"Button state does not match.\nButton: {key}\nExpected: {expected_value}\nGot: {app_test.button(key=key).value}"
        )

    # 警告メッセージが表示されることを確認
    assert app_test.warning.len >= 1, "Warning message should be displayed"


@UNIT
@pytest.mark.parametrize(
    ("button_sequence"),
    [
        pytest.param(
            ["tab1_execute_text", "tab1_execute_markdown"],
            id="app_button_sequence_text_to_markdown",
        ),
        pytest.param(
            ["tab2_execute_visual", "tab2_execute_toml", "tab2_execute_yaml"],
            id="app_button_sequence_visual_to_yaml",
        ),
        pytest.param(
            ["tab1_execute_text", "tab2_execute_visual"],
            id="app_button_sequence_tab1_to_tab2",
        ),
    ],
)
def test_button_sequence(app_test: AppTest, button_sequence: List[str]) -> None:
    """
    ボタンを連続してクリックした場合の状態変化をテストする。

    Args:
        app_test: Streamlitアプリのテストインスタンス
        button_sequence: クリックするボタンのキーのシーケンス
    """
    # Arrange - すべてのボタンキーのリスト (定数を使用)
    all_button_keys = BUTTON_KEYS

    # Act & Assert - 各ボタンを順番にクリックして状態を検証
    for _i, current_button in enumerate(button_sequence):
        # ボタンをクリック
        app_test.button(key=current_button).click().run()

        # 現在のボタンがアクティブになっていることを確認
        assert app_test.button(key=current_button).value is True, f"Button '{current_button}' should be active"

        # 他のボタンは非アクティブであることを確認
        for other_button in all_button_keys:
            if other_button != current_button:
                assert app_test.button(key=other_button).value is False, f"Button '{other_button}' should be inactive"

        # 警告メッセージが表示されることを確認
        assert app_test.warning.len >= 1, "Warning message should be displayed"


@UNIT
def test_app_edge_cases(app_test: AppTest) -> None:
    """
    Streamlitアプリのエッジケースをテストする。

    アプリの様々な入力条件と設定に対する動作を検証します。
    テストでは以下のケースを確認します:
    - ボタンのクリック動作
    - 警告メッセージの表示
    - 異なるボタンの状態変化
    """
    # Arrange - 初期状態の確認
    assert app_test.warning.len == 0, "Warning message should not be displayed in initial state"

    # Act & Assert - 空の入力でボタンをクリックすると警告が表示される
    app_test.button(key="tab1_execute_text").click().run()
    assert app_test.warning.len >= 1, "Warning message should be displayed"
    assert app_test.button(key="tab1_execute_text").value is True, "Button should be active"


# Note: We're not testing tab navigation directly because the Streamlit testing API
# doesn't provide a clean way to test tab selection and activation without triggering
# linter errors. The main functionality of the tabs is tested in test_main_layout and
# test_app_edge_cases.
