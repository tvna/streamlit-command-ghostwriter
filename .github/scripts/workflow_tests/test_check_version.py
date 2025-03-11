#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
check_version.pyのユニットテスト
"""

import logging
import sys
from pathlib import Path
from typing import Callable, Optional

import pytest
from pytest_mock import MockerFixture

# テスト対象モジュールのパスを追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from check_version import InvalidGitRepositoryError, InvalidReadPackageError, VersionChecker
from git.exc import GitCommandNotFound


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
def test_set_fail_output(checker: VersionChecker, mocker: MockerFixture) -> None:
    """set_fail_outputメソッドのテスト"""
    # set_github_outputメソッドをモック化
    mock_set_github_output = mocker.patch.object(checker, "set_github_output")

    # メソッド実行
    checker.set_fail_output("test_reason", extra_key="extra_value")

    # 呼び出し確認
    assert mock_set_github_output.call_count == 5
    mock_set_github_output.assert_any_call("status", "failure")
    mock_set_github_output.assert_any_call("message", "test_reason")
    mock_set_github_output.assert_any_call("version_changed", "false")
    mock_set_github_output.assert_any_call("reason", "test_reason")
    mock_set_github_output.assert_any_call("extra_key", "extra_value")


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
    ("commits_exist", "expected_result", "expected_exception"),
    [
        pytest.param(True, "mock_commit", False, id="Commit exists"),
        pytest.param(False, None, False, id="No commits"),
        pytest.param(None, None, True, id="Exception raised"),
    ],
)
def test_get_package_json_from_latest_git_commit(
    checker: VersionChecker, commits_exist: Optional[bool], expected_result: Optional[str], expected_exception: bool, mocker: MockerFixture
) -> None:
    """get_package_json_from_latest_git_commitメソッドのテスト"""
    # モックの設定
    mock_repo = mocker.MagicMock()
    mock_commit = mocker.MagicMock()
    mocker.patch.object(checker, "_git_repo", mock_repo)

    if commits_exist is None:
        # 例外を発生させる
        mock_repo.iter_commits.side_effect = Exception("Test exception")
    else:
        # コミットの有無に応じて戻り値を設定
        mock_repo.iter_commits.return_value = [mock_commit] if commits_exist else []

    # テスト実行
    if expected_exception:
        with pytest.raises(InvalidReadPackageError):
            checker.get_package_json_from_latest_git_commit()
    else:
        result = checker.get_package_json_from_latest_git_commit()
        if expected_result:
            assert result == mock_commit
        else:
            assert result is None


@pytest.mark.workflow
@pytest.mark.parametrize(
    ("version_in_json", "exception_on_read", "expected_exception"),
    [
        pytest.param("1.0.0", False, False, id="Valid version"),
        pytest.param(None, False, True, id="No version in JSON"),
        pytest.param("1.0.0", True, True, id="Exception on read"),
    ],
)
def test_get_package_json_from_previous_git_commit(
    checker: VersionChecker, version_in_json: Optional[str], exception_on_read: bool, expected_exception: bool, mocker: MockerFixture
) -> None:
    """get_package_json_from_previous_git_commitメソッドのテスト"""
    # モックの設定
    mock_commit = mocker.MagicMock()
    mock_parent = mocker.MagicMock()
    mock_tree = mocker.MagicMock()
    mock_blob = mocker.MagicMock()
    mock_data_stream = mocker.MagicMock()

    mock_commit.parents = [mock_parent]
    mock_parent.tree = mock_tree
    mock_tree.__truediv__.return_value = mock_blob
    mock_blob.data_stream = mock_data_stream

    if exception_on_read:
        mock_data_stream.read.side_effect = Exception("Test exception")
    else:
        json_content = f'{{"version": "{version_in_json}"}}' if version_in_json else "{}"
        mock_data_stream.read.return_value = json_content.encode("utf-8")

    # テスト実行
    if expected_exception:
        with pytest.raises(InvalidReadPackageError):
            checker.get_package_json_from_previous_git_commit(mock_commit)
    else:
        result = checker.get_package_json_from_previous_git_commit(mock_commit)
        assert result == version_in_json


@pytest.mark.workflow
@pytest.mark.parametrize(
    (
        "exists_package_json",
        "exists_package_lock",
        "new_version",
        "lock_version",
        "is_semver_result",
        "expected_warning",
    ),
    [
        pytest.param(True, True, "1.0.0", "1.0.0", True, False, id="Valid semver"),
        pytest.param(True, True, "invalid", "invalid", False, True, id="Invalid semver"),
    ],
)
def test_read_npm_versions_semver_validation(
    checker: VersionChecker,
    exists_package_json: bool,
    exists_package_lock: bool,
    new_version: str,
    lock_version: str,
    is_semver_result: bool,
    expected_warning: bool,
    mocker: MockerFixture,
    capsys: pytest.CaptureFixture,
) -> None:
    """read_npm_versionsメソッドのセマンティックバージョン検証テスト"""
    # モックの設定
    mocker.patch("pathlib.Path.exists", return_value=True)
    mocker.patch.object(checker, "get_file_version", side_effect=[new_version, lock_version])
    mocker.patch.object(checker, "is_semver", return_value=is_semver_result)
    mocker.patch.object(checker, "set_fail_output")

    # テスト実行
    result, npm_new_version, npm_lock_version = checker.read_npm_versions()

    # 出力の検証
    captured = capsys.readouterr()
    if expected_warning:
        assert f"::warning::バージョン形式が正しくありません: {new_version}" in captured.out


@pytest.mark.workflow
@pytest.mark.parametrize(
    ("exception_factory", "expected_output", "expected_reason"),
    [
        pytest.param(
            lambda: GitCommandNotFound("git", "Command not found"),
            "::error::gitコマンドが見つかりません",
            "git_command_not_found",
            id="GitCommandNotFound",
        ),
    ],
)
def test_run_specific_exceptions(
    checker: VersionChecker,
    exception_factory: Callable[[], Exception],
    expected_output: str,
    expected_reason: str,
    mocker: MockerFixture,
    capsys: pytest.CaptureFixture,
) -> None:
    """runメソッドの特定の例外テスト"""
    # モックの設定
    exception = exception_factory()
    mocker.patch.object(checker, "read_npm_versions", side_effect=exception)
    mocker.patch.object(checker, "set_fail_output")

    # テスト実行
    result = checker.run()

    # 結果の検証
    assert result == 1

    # 出力の検証
    captured = capsys.readouterr()
    assert expected_output in captured.out
    checker.set_fail_output.assert_called_once_with(expected_reason)


@pytest.mark.workflow
@pytest.mark.parametrize(
    (
        "read_npm_versions_result",
        "read_npm_package_changes_result",
        "compare_npm_versions_result",
        "compare_git_tags_result",
        "expected_result",
        "expected_exception",
    ),
    [
        # 正常系
        pytest.param((True, "1.0.1", "1.0.1"), (True, "mock_commit"), True, True, 0, None, id="Success"),
        # 異常系: npmファイルの検証失敗
        pytest.param((False, None, None), None, None, None, 1, None, id="Invalid npm files"),
        # 異常系: package.jsonの変更なし
        pytest.param((True, "1.0.1", "1.0.1"), (False, None), None, None, 0, None, id="No package changes"),
        # 異常系: バージョン比較失敗
        pytest.param((True, "1.0.1", "1.0.1"), (True, "mock_commit"), False, None, 1, None, id="Version comparison failed"),
        # 異常系: タグ比較失敗
        pytest.param((True, "1.0.1", "1.0.1"), (True, "mock_commit"), True, False, 1, None, id="Tag comparison failed"),
        # 例外: InvalidReadPackageError
        pytest.param(
            None, None, None, None, 1, InvalidReadPackageError("Invalid read package error occurred"), id="InvalidReadPackageError"
        ),
        pytest.param(
            None, None, None, None, 1, InvalidGitRepositoryError("Invalid git repository error occurred"), id="InvalidGitRepositoryError"
        ),
        pytest.param(None, None, None, None, 1, Exception("An unexpected error occurred"), id="Other exception"),
    ],
)
def test_run(
    checker: VersionChecker,
    read_npm_versions_result: Optional[tuple],
    read_npm_package_changes_result: Optional[tuple],
    compare_npm_versions_result: Optional[bool],
    compare_git_tags_result: Optional[bool],
    expected_result: int,
    expected_exception: Optional[Exception],
    mocker: MockerFixture,
    capsys: pytest.CaptureFixture,
) -> None:
    """runメソッドのテスト"""
    # モックの設定
    if expected_exception:
        # 例外をシミュレート
        mocker.patch.object(checker, "read_npm_versions", side_effect=expected_exception)
    else:
        # 正常系のモック
        mocker.patch.object(checker, "read_npm_versions", return_value=read_npm_versions_result)
        if read_npm_package_changes_result is not None:
            mocker.patch.object(checker, "read_npm_package_changes", return_value=read_npm_package_changes_result)

        if read_npm_package_changes_result and read_npm_package_changes_result[0]:
            # コミットが存在する場合
            mocker.patch.object(checker, "get_package_json_from_previous_git_commit", return_value="1.0.0")

            if compare_npm_versions_result is not None:
                mocker.patch.object(checker, "compare_npm_versions", return_value=compare_npm_versions_result)

                if compare_npm_versions_result and compare_git_tags_result is not None:
                    mocker.patch.object(checker, "compare_git_tags", return_value=compare_git_tags_result)

    mocker.patch.object(checker, "set_github_output")
    mocker.patch.object(checker, "set_fail_output")

    # テスト実行
    result = checker.run()

    # 結果の検証
    assert result == expected_result

    # 成功時の出力検証
    if expected_result == 0 and read_npm_versions_result and read_npm_package_changes_result and read_npm_package_changes_result[0]:
        captured = capsys.readouterr()
        assert "::notice::npmのバージョンが" in captured.out
        checker.set_github_output.assert_any_call("status", "success")
        checker.set_github_output.assert_any_call("version_changed", "true")


@pytest.mark.workflow
def test_main(mocker: MockerFixture) -> None:
    """main関数のテスト"""
    # 先にインポートしておく
    from check_version import main

    # モックの設定
    mock_checker = mocker.MagicMock()
    mock_checker.run.return_value = 0
    mocker.patch("check_version.VersionChecker", return_value=mock_checker)

    # テスト実行
    main()

    # 検証
    mock_checker.run.assert_called_once()
