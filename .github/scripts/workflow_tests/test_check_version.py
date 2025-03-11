#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
check_version.pyのユニットテスト
"""

import logging
import sys
from pathlib import Path
from typing import Optional

import pytest
from pytest_mock import MockerFixture

# テスト対象モジュールのパスを追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from check_version import VersionChecker


@pytest.fixture
def checker() -> VersionChecker:
    """VersionCheckerのインスタンスを提供"""
    return VersionChecker()


@pytest.mark.workflow
@pytest.mark.parametrize(
    ("env_var_set", "expected_output", "expected_log"),
    [
        pytest.param(True, "TEST_VAR=test_value\n", None, id="True"),
        pytest.param(False, None, "GITHUB_OUTPUT環境変数が設定されていません", id="False"),
    ],
)
def test_set_github_output(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    checker: VersionChecker,
    env_var_set: bool,
    expected_output: Optional[str],
    expected_log: Optional[str],
) -> None:
    if env_var_set:
        # 一時ファイルを作成し、そのパスを環境変数に設定
        output_file = "./.github/tmp/github_output.txt"
        Path("./.github/tmp").mkdir(parents=True, exist_ok=True)  # ディレクトリを作成
        monkeypatch.setenv("GITHUB_OUTPUT", str(output_file))
    else:
        # 環境変数を設定しない
        monkeypatch.delenv("GITHUB_OUTPUT", raising=False)

    # caplog を使用してログをキャプチャ
    with caplog.at_level(logging.WARNING, logger="test_logger"):
        checker.set_github_output("TEST_VAR", "test_value")

    if env_var_set:
        # ファイルの内容を検証
        with open(output_file, "r") as f:
            lines: list[str] = f.readlines()
        assert expected_output in lines
    else:
        # 警告ログが出力されていることを確認
        assert expected_log is not None
        assert expected_log in caplog.text


@pytest.mark.workflow
@pytest.mark.parametrize(
    ("file_content", "expected_version", "expected_exception"),
    [
        pytest.param('{"version": "1.0.0"}', "1.0.0", False, id="1.0.0"),  # 正常ケース
        pytest.param('{"version": "2.0.0"}', "2.0.0", False, id="2.0.0"),  # 正常ケース
        pytest.param("", None, True, id="空のファイル"),  # エラーケース: 空のファイル
        pytest.param('{"wrong_key": "value"}', None, True, id="バージョンキーなし"),  # エラーケース: バージョンキーなし
    ],
)
def test_get_file_version(
    checker: VersionChecker, file_content: str, expected_version: Optional[str], expected_exception: bool, mocker: MockerFixture
) -> None:
    """get_file_versionメソッドのテスト(成功とエラー)"""
    open_mock = mocker.patch("builtins.open", new_callable=mocker.mock_open, read_data=str(file_content))

    try:
        version = checker.get_file_version("package.json")
        assert version == expected_version
        assert open_mock.call_count == 1
        assert expected_exception is False
    except Exception:
        assert expected_exception is True


@pytest.mark.workflow
@pytest.mark.parametrize(
    ("version", "expected"),
    [
        pytest.param("1.0.0", True, id="1.0.0"),
        pytest.param("1.2.3", True, id="1.2.3"),
        pytest.param("0.1.0", True, id="0.1.0"),
        pytest.param("1.0.0-alpha", True, id="1.0.0-alpha"),
        pytest.param("1.0.0-beta.1", True, id="1.0.0-beta.1"),
        pytest.param("1.0.0+build.1", True, id="1.0.0+build.1"),
        pytest.param("v1.0.0", False, id="v1.0.0"),
        pytest.param("1.0", False, id="1.0"),
        pytest.param("1", False, id="1"),
        pytest.param("1.0.a", False, id="1.0.a"),
        pytest.param("latest", False, id="latest"),
    ],
)
def test_is_semver(version: str, expected: bool, checker: VersionChecker) -> None:
    """is_semverメソッドのテスト"""
    assert checker.is_semver(version) == expected


@pytest.mark.workflow
@pytest.mark.parametrize(
    ("v1", "v2", "expected"),
    [
        pytest.param("1.0.1", "1.0.0", 1, id="1.0.1 > 1.0.0"),
        pytest.param("1.1.0", "1.0.0", 1, id="1.1.0 > 1.0.0"),
        pytest.param("2.0.0", "1.0.0", 1, id="2.0.0 > 1.0.0"),
        pytest.param("1.0.0", "1.0.0", 0, id="1.0.0 = 1.0.0"),
        pytest.param("1.0.0", "1.0.1", -1, id="1.0.0 < 1.0.1"),
        pytest.param("1.0.0", "1.1.0", -1, id="1.0.0 < 1.1.0"),
        pytest.param("1.0.0", "2.0.0", -1, id="1.0.0 < 2.0.0"),
    ],
)
def test_compare_versions(v1: str, v2: str, expected: int, checker: VersionChecker) -> None:
    """compare_versionsメソッドのテスト"""
    assert checker.compare_versions(v1, v2) == expected


@pytest.mark.workflow
@pytest.mark.parametrize(
    (
        "exists_package_json",
        "exists_package_lock",
        "new_version",
        "lock_version",
        "expected_result",
        "expected_new_version",
        "expected_lock_version",
        "expected_print_called",
    ),
    [
        pytest.param(True, True, "1.0.0", "1.0.0", True, "1.0.0", "1.0.0", True, id="Both files exist"),
        pytest.param(False, True, None, "1.0.0", False, None, None, False, id="First file missing"),
        pytest.param(True, False, "1.0.0", None, False, None, None, False, id="Second file missing"),
        pytest.param(True, False, "1.0", "1.0.0", False, None, None, False, id="First file broken"),
        pytest.param(True, False, "1.0.0", "1.0", False, None, None, False, id="Second file broken"),
        pytest.param(True, True, None, None, False, None, None, False, id="Both files broken"),
    ],
)
def test_read_npm_versions(
    checker: VersionChecker,
    exists_package_json: bool,
    exists_package_lock: bool,
    new_version: Optional[str],
    lock_version: Optional[str],
    expected_result: bool,
    expected_new_version: Optional[str],
    expected_lock_version: Optional[str],
    expected_print_called: bool,
    mocker: MockerFixture,
    capsys: pytest.CaptureFixture,
) -> None:
    """read_npm_versionsメソッドのテスト"""
    mocker.patch("pathlib.Path.exists", return_value=[exists_package_json, exists_package_lock])
    mocker.patch.object(checker, "get_file_version", side_effect=[new_version, lock_version])

    result, npm_new_version, npm_lock_version = checker.read_npm_versions()
    captured = capsys.readouterr()

    assert result == expected_result
    assert npm_new_version == expected_new_version
    assert npm_lock_version == expected_lock_version
    assert True if len(captured.out) == 0 else False is expected_print_called
