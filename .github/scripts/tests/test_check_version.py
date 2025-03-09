#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
check_version.pyのユニットテスト
"""

import logging
import sys
from pathlib import Path
from typing import List, Optional

import pytest
from pytest_mock import MockerFixture

# テスト対象モジュールのパスを追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from check_version import VersionChecker  # noqa: E402


@pytest.fixture
def checker() -> VersionChecker:
    """VersionCheckerのインスタンスを提供"""
    return VersionChecker()


@pytest.mark.parametrize(
    ("test_header", "test_message"),
    [
        ("::notice::", "テスト通知"),
        ("::warning::", "テスト警告"),
        ("::error::", "テストエラー"),
    ],
)
def test_github_logging(checker: VersionChecker, test_header: str, test_message: str, capsys: pytest.CaptureFixture) -> None:
    """GitHubのログメッセージのテスト"""

    if "通知" in test_message:
        checker.github_notice(test_message)
    elif "警告" in test_message:
        checker.github_warning(test_message)
    elif "エラー" in test_message:
        checker.github_error(test_message)

    captured = capsys.readouterr()
    assert captured.out == test_header + test_message + "\n"


@pytest.mark.parametrize(
    ("env_var_set", "expected_output", "expected_log"),
    [(True, "TEST_VAR=test_value\n", None), (False, None, "GITHUB_OUTPUT環境変数が設定されていません")],
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
        output_file = "./github/tmp/github_output.txt"
        Path("./github/tmp").mkdir(parents=True, exist_ok=True)  # ディレクトリを作成
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


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        # Normal cases (successful commands)
        (["git", "status"], True),
        (["npm", "version"], True),
        (["jq", "."], True),
        # Abnormal cases (failure commands)
        (["ls", "-l"], False),
        (["echo", "hello"], False),
        (["rm", "-rf", "/"], False),
        (["git", "push", "|", "grep"], False),
        (["npm", "install", "&", "rm"], False),
        (["invalid_command"], False),
        ([""], False),
        (["git", "&&", "status"], False),
        (["echo", "hello", "|", "grep", "hello"], False),
        ([";"], False),
        (["echo", "hello", ">", "output.txt"], False),
    ],
)
def test_validate_command_combined(checker: VersionChecker, command: List[str], expected: bool) -> None:
    """validate_commandメソッドのテスト（集約版）"""
    assert checker.validate_command(command) == expected


@pytest.mark.parametrize("return_code", [0, 1])
def test_run_cmd(checker: VersionChecker, return_code: int, mocker: MockerFixture) -> None:
    """run_cmdメソッドのテスト"""
    mock_run = mocker.patch("subprocess.run")  # Use mocker to patch subprocess.run
    mock_run.return_value.returncode = return_code  # Set the return code for the mock
    mocker.patch.object(VersionChecker, "validate_command", return_value=True)  # Mock validate_command to return True

    # Test with a valid command
    if return_code == 0:
        result = checker.run_cmd(["git", "status"])
        assert result is True
    else:
        result = checker.run_cmd(["git", "invalid_command"])
        assert result is False

    # Test with a command that raises an exception
    mock_run.side_effect = Exception("Command execution failed")
    result = checker.run_cmd(["git", "status"])
    assert result is False


@pytest.mark.parametrize(
    ("file_content", "expected_version", "expected_exception"),
    [
        ('{"version": "1.0.0"}', "1.0.0", False),  # 正常ケース
        ('{"version": "2.0.0"}', "2.0.0", False),  # 正常ケース
        ("", None, True),  # エラーケース: 空のファイル
        ('{"wrong_key": "value"}', None, True),  # エラーケース: バージョンキーなし
    ],
)
def test_get_file_version(
    checker: VersionChecker, file_content: str, expected_version: Optional[str], expected_exception: bool, mocker: MockerFixture
) -> None:
    """get_file_versionメソッドのテスト（成功とエラー）"""
    open_mock = mocker.patch("builtins.open", new_callable=mocker.mock_open, read_data=str(file_content))

    try:
        version = checker.get_file_version("package.json")
        assert version == expected_version
        assert open_mock.call_count == 1
        assert expected_exception is False
    except Exception:
        assert expected_exception is True


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        ("1.0.0", True),
        ("1.2.3", True),
        ("0.1.0", True),
        ("1.0.0-alpha", True),
        ("1.0.0-beta.1", True),
        ("1.0.0+build.1", True),
        ("v1.0.0", False),
        ("1.0", False),
        ("1", False),
        ("1.0.a", False),
        ("latest", False),
    ],
)
def test_is_semver(version: str, expected: bool, checker: VersionChecker) -> None:
    """is_semverメソッドのテスト"""
    assert checker.is_semver(version) == expected


@pytest.mark.parametrize(
    ("v1", "v2", "expected"),
    [
        ("1.0.1", "1.0.0", 1),
        ("1.1.0", "1.0.0", 1),
        ("2.0.0", "1.0.0", 1),
        ("1.0.0", "1.0.0", 0),
        ("1.0.0", "1.0.1", -1),
        ("1.0.0", "1.1.0", -1),
        ("1.0.0", "2.0.0", -1),
    ],
)
def test_compare_versions(v1: str, v2: str, expected: int, checker: VersionChecker) -> None:
    """compare_versionsメソッドのテスト"""
    assert checker.compare_versions(v1, v2) == expected


@pytest.mark.parametrize(
    ("init_return", "expected", "should_log_error"),
    [
        (True, True, False),  # Successful initialization
        (False, False, True),  # Failed initialization
    ],
)
def test_initialize_git_repo(
    checker: VersionChecker, init_return: bool, expected: bool, should_log_error: bool, mocker: MockerFixture
) -> None:
    """initialize_git_repoメソッドのテスト（成功と失敗の集約）"""
    if not init_return:
        mocker.patch("git.Repo", side_effect=Exception("Not a git repository"))  # Mock failure case

    mock_error = mocker.patch.object(VersionChecker, "github_error")  # Patch the github_error method

    result = checker.initialize_git_repo()
    assert result == expected  # Check if the result matches the expected value

    if should_log_error:
        mock_error.assert_called_once()  # Ensure an error was logged
    else:
        mock_error.assert_not_called()  # Ensure no error was logged


@pytest.mark.parametrize(
    ("exists", "expected"),
    [
        ([True, True], True),  # Both files exist
        ([False, True], False),  # First file missing
        ([True, False], False),  # Second file missing
        ([False, False], False),  # Both files missing
    ],
)
def test_validate_and_check_versions(checker: VersionChecker, exists: List[bool], expected: bool, mocker: MockerFixture) -> None:
    """validate_and_check_versionsメソッドのテスト"""
    mocker.patch("pathlib.Path.exists", side_effect=exists)  # Use mocker to patch the exists method
    mocker.patch.object(checker, "get_file_version", side_effect=["1.0.0", "1.0.0"])  # Mock version retrieval
    mock_error = mocker.patch.object(VersionChecker, "github_error")
    mock_fail = mocker.patch.object(VersionChecker, "set_fail_output")

    result, new_version, lock_version = checker.validate_and_check_versions()
    assert result == expected

    if not expected:
        if not exists[0]:
            mock_error.assert_called_once_with("package.json ファイルが見つかりません")
            mock_fail.assert_called_once_with("package_missing")
        elif not exists[1]:
            mock_error.assert_called_once_with("package-lock.json ファイルが見つかりません")
            mock_fail.assert_called_once_with("lockfile_missing")


@pytest.mark.parametrize(
    ("init_return", "expected"),
    [
        (True, 0),
        (False, 1),
    ],
)
def test_run(checker: VersionChecker, init_return: bool, expected: int, mocker: MockerFixture) -> None:
    """runメソッドのテスト"""
    mocker.patch.object(VersionChecker, "initialize_git_repo", return_value=init_return)
    result = checker.run()
    assert result == expected
