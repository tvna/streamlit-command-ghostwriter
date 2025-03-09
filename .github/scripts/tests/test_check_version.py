#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
check_version.pyのユニットテスト
"""

import os
import sys
from pathlib import Path
from typing import List
from unittest import mock

import pytest

# テスト対象モジュールのパスを追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from check_version import VersionChecker  # noqa: E402


@pytest.fixture()
def checker() -> VersionChecker:
    """VersionCheckerのインスタンスを提供"""
    return VersionChecker()


@pytest.fixture(autouse=True)
def capsys() -> pytest.CaptureFixture:
    """標準出力をキャプチャするためのフィクスチャ"""
    with mock.patch("sys.stdout") as mock_stdout:
        yield mock_stdout


@pytest.mark.parametrize(
    "test_message",
    [
        ("テスト通知",),
        ("テスト警告",),
        ("テストエラー",),
    ],
)
def test_github_logging(checker: VersionChecker, test_message: str, capsys: pytest.CaptureFixture) -> None:
    """GitHubのログメッセージのテスト"""
    if "通知" in test_message:
        checker.github_notice(test_message)
    elif "警告" in test_message:
        checker.github_warning(test_message)
    elif "エラー" in test_message:
        checker.github_error(test_message)

    captured = capsys.getvalue()
    assert f"::{test_message}::" in captured


@pytest.mark.parametrize(
    ("output_name", "output_value"),
    [
        ("test_name", "test_value"),
    ],
)
def test_set_github_output(checker: VersionChecker, output_name: str, output_value: str) -> None:
    """set_github_outputメソッドのテスト"""
    with (
        mock.patch.dict(os.environ, {"GITHUB_OUTPUT": "github_output.txt"}),
        mock.patch("builtins.open", new_callable=mock.mock_open) as mock_open,
    ):
        checker.set_github_output(output_name, output_value)
        mock_open.assert_called_with("github_output.txt", "a")
        mock_open().write.assert_called_with(f"{output_name}={output_value}\n")


def test_set_github_output_no_env(checker: VersionChecker) -> None:
    """GITHUB_OUTPUT環境変数がない場合のset_github_outputメソッドのテスト"""
    with mock.patch("check_version.logger.warning") as mock_warning:
        checker.set_github_output("test_name", "test_value")
        mock_warning.assert_called_with("GITHUB_OUTPUT環境変数が設定されていません")


def test_set_fail_output(checker: VersionChecker) -> None:
    """set_fail_outputメソッドのテスト"""
    with mock.patch.object(VersionChecker, "set_github_output") as mock_set_github_output:
        checker.set_fail_output("test_reason", key1="value1", key2="value2")
        expected_calls = [
            mock.call("status", "failure"),
            mock.call("message", "test_reason"),
            mock.call("version_changed", "false"),
            mock.call("reason", "test_reason"),
            mock.call("key1", "value1"),
            mock.call("key2", "value2"),
        ]
        mock_set_github_output.assert_has_calls(expected_calls, any_order=True)


def test_set_success_output(checker: VersionChecker) -> None:
    """set_success_outputメソッドのテスト"""
    with mock.patch.object(VersionChecker, "set_github_output") as mock_set_github_output:
        checker.set_success_output("1.0.0", "0.9.0")
        expected_calls = [
            mock.call("status", "success"),
            mock.call("version_changed", "true"),
            mock.call("new_version", "1.0.0"),
            mock.call("old_version", "0.9.0"),
        ]
        mock_set_github_output.assert_has_calls(expected_calls, any_order=True)


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        (["git", "status"], True),
        (["npm", "version"], True),
        (["jq", "."], True),
        (["rm", "-rf", "/"], False),
        (["git", "push", "|", "grep"], False),
        (["npm", "install", "&", "rm"], False),
    ],
)
def test_validate_command(checker: VersionChecker, command: List[str], expected: bool) -> None:
    """validate_commandメソッドのテスト"""
    assert checker.validate_command(command) == expected


@pytest.mark.parametrize("return_code", [0, 1])
def test_run_cmd(checker: VersionChecker, return_code: int) -> None:
    """run_cmdメソッドのテスト"""
    with mock.patch("subprocess.run") as mock_run, mock.patch.object(VersionChecker, "validate_command", return_value=True):
        mock_run.return_value.returncode = return_code
        result = checker.run_cmd(["git", "status"])
        assert result if return_code == 0 else not result


@pytest.mark.parametrize(
    ("file_content", "expected_version"),
    [
        ('{"version": "1.0.0"}', "1.0.0"),
        ('{"version": "2.0.0"}', "2.0.0"),
    ],
)
def test_get_file_version_success(checker: VersionChecker, file_content: str, expected_version: str) -> None:
    """get_file_versionメソッドの成功テスト"""
    with mock.patch("builtins.open", new_callable=mock.mock_open, read_data=file_content):
        version = checker.get_file_version("package.json")
        assert version == expected_version


def test_get_file_version_error(checker: VersionChecker) -> None:
    """get_file_versionメソッドのエラーテスト"""
    with (
        mock.patch("builtins.open", side_effect=Exception("File not found")),
        mock.patch.object(VersionChecker, "github_error") as mock_error,
    ):
        version = checker.get_file_version("package.json")
        assert version is None
        mock_error.assert_called_once()


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


def test_initialize_repo_exception(checker: VersionChecker) -> None:
    """initialize_repoメソッドの例外テスト"""
    with (
        mock.patch("git.Repo", side_effect=Exception("Not a git repository")),
        mock.patch.object(VersionChecker, "github_error") as mock_error,
    ):
        result = checker.initialize_repo()
        assert not result
        mock_error.assert_called_once()


@pytest.mark.parametrize(
    ("exists", "expected"),
    [
        ([True, True], True),
        ([False, True], False),
        ([True, False], False),
    ],
)
def test_check_file_existence(checker: VersionChecker, exists: List[bool], expected: bool) -> None:
    """check_file_existenceメソッドのテスト"""
    with mock.patch("pathlib.Path.exists", side_effect=exists):
        result = checker.check_file_existence()
        assert result == expected


@pytest.mark.parametrize(
    ("exists", "expected_fail"),
    [
        ([False, True], "package_missing"),
        ([True, False], "lockfile_missing"),
    ],
)
def test_check_file_existence_no_files(checker: VersionChecker, exists: List[bool], expected_fail: str) -> None:
    """ファイルがない場合のcheck_file_existenceメソッドのテスト"""
    with (
        mock.patch("pathlib.Path.exists", side_effect=exists),
        mock.patch.object(VersionChecker, "github_error") as mock_error,
        mock.patch.object(VersionChecker, "set_fail_output") as mock_fail,
    ):
        result = checker.check_file_existence()
        assert not result
        mock_error.assert_called_once()
        mock_fail.assert_called_once_with(expected_fail)


@pytest.mark.parametrize(
    ("init_return", "expected"),
    [
        (True, 0),
        (False, 1),
    ],
)
def test_run(checker: VersionChecker, init_return: bool, expected: int) -> None:
    """runメソッドのテスト"""
    with mock.patch.object(VersionChecker, "initialize_repo", return_value=init_return):
        result = checker.run()
        assert result == expected


if __name__ == "__main__":
    pytest.main()
