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
def checker(mocker: MockerFixture) -> VersionChecker:
    """VersionCheckerのインスタンスを提供"""
    # Git.Repoをモック化して、InvalidGitRepositoryErrorを回避
    mock_repo = mocker.MagicMock()
    mocker.patch("git.Repo", return_value=mock_repo)

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
    (
        "package_json_exists",
        "package_lock_exists",
        "package_json_version",
        "package_lock_version",
        "expected_result",
        "expected_new_version",
        "expected_lock_version",
        "expected_fail_reason",
    ),
    [
        # 正常系
        pytest.param(True, True, "1.0.0", "1.0.0", True, "1.0.0", "1.0.0", None, id="Both files exist with matching versions"),
        # 異常系: package.jsonが存在しない
        pytest.param(False, True, None, "1.0.0", False, None, None, "package_missing", id="package.json missing"),
        # 異常系: package-lock.jsonが存在しない
        pytest.param(True, False, "1.0.0", None, False, None, None, "lockfile_missing", id="package-lock.json missing"),
        # 異常系: package.jsonのバージョン取得失敗
        pytest.param(True, True, None, "1.0.0", False, None, None, "npm_new_version_error", id="package.json version error"),
        # 異常系: package-lock.jsonのバージョン取得失敗
        pytest.param(True, True, "1.0.0", None, False, None, None, "npm_lock_version_error", id="package-lock.json version error"),
        # 異常系: バージョン不一致
        pytest.param(True, True, "1.0.0", "1.0.1", False, None, None, "version_mismatch", id="Version mismatch"),
    ],
)
def test_read_npm_versions(
    package_json_exists: bool,
    package_lock_exists: bool,
    package_json_version: Optional[str],
    package_lock_version: Optional[str],
    expected_result: bool,
    expected_new_version: Optional[str],
    expected_lock_version: Optional[str],
    expected_fail_reason: Optional[str],
    mocker: MockerFixture,
    capsys: pytest.CaptureFixture,
) -> None:
    """read_npm_versionsメソッドの全分岐テスト"""
    # Git.Repoをモック化
    mock_repo = mocker.MagicMock()
    mocker.patch("git.Repo", return_value=mock_repo)

    # VersionCheckerのインスタンスを作成
    checker = VersionChecker()

    # 必要なメソッドをモック化
    # 1. Path.exists
    original_exists = Path.exists

    def mock_exists(self: Path) -> bool:
        path_str = str(self)
        if path_str == "package.json":
            return package_json_exists
        elif path_str == "package-lock.json":
            return package_lock_exists
        return original_exists(self)

    mocker.patch.object(Path, "exists", mock_exists)

    # 2. get_file_version
    def mock_get_file_version(file_path: str) -> Optional[str]:
        if file_path == "package.json":
            return package_json_version
        elif file_path == "package-lock.json":
            return package_lock_version
        return None

    mocker.patch.object(checker, "get_file_version", side_effect=mock_get_file_version)

    # 3. is_semver
    mocker.patch.object(checker, "is_semver", return_value=True)

    # 4. set_fail_output
    set_fail_output_mock = mocker.patch.object(checker, "set_fail_output")

    # テスト実行
    result, npm_new_version, npm_lock_version = checker.read_npm_versions()

    # 結果の検証
    assert result == expected_result
    assert npm_new_version == expected_new_version
    assert npm_lock_version == expected_lock_version

    # 出力の検証
    captured = capsys.readouterr()

    if not package_json_exists:
        assert "::error::package.json ファイルが見つかりません" in captured.out

    if package_json_exists and not package_lock_exists:
        assert "::error::package-lock.json ファイルが見つかりません" in captured.out

    if package_json_exists and package_lock_exists and package_json_version is None:
        assert "::error::新しいpackage.jsonのバージョンの取得に失敗しました" in captured.out

    if package_json_exists and package_lock_exists and package_json_version and package_lock_version is None:
        assert "::error::新しいpackage-lock.jsonのバージョン取得に失敗しました" in captured.out

    if (
        package_json_exists
        and package_lock_exists
        and package_json_version
        and package_lock_version
        and package_json_version != package_lock_version
    ):
        assert (
            f"::error::package.json ({package_json_version}) はpackage-lock.json ({package_lock_version}) のバージョンと一致していません"
            in captured.out
        )

    # 失敗理由の検証
    if expected_fail_reason:
        set_fail_output_mock.assert_called_once_with(expected_fail_reason)
    else:
        set_fail_output_mock.assert_not_called()


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
@pytest.mark.parametrize(
    ("tag_names", "fetch_exception", "expected_result"),
    [
        pytest.param(["v1.0.0", "v1.1.0", "v0.9.0"], False, ["v0.9.0", "v1.0.0", "v1.1.0"], id="Valid tags sorted"),
        pytest.param(["v1.0.0", "not-semver", "v0.9.0"], False, ["v0.9.0", "v1.0.0"], id="Mixed tags"),
        pytest.param([], False, [], id="No tags"),
        pytest.param(["not-semver1", "not-semver2"], False, [], id="No valid tags"),
        pytest.param(["v1.0.0", "v1.1.0"], True, ["v1.0.0", "v1.1.0"], id="Fetch exception"),
    ],
)
def test_get_version_tags(
    checker: VersionChecker,
    tag_names: list[str],
    fetch_exception: bool,
    expected_result: list[str],
    mocker: MockerFixture,
    capsys: pytest.CaptureFixture,
) -> None:
    """get_version_tagsメソッドのテスト"""
    # モックの設定
    mock_repo = mocker.MagicMock()
    mock_tags = []

    for tag_name in tag_names:
        mock_tag = mocker.MagicMock()
        mock_tag.name = tag_name
        mock_tags.append(mock_tag)

    mock_repo.tags = mock_tags

    # fetch呼び出しのモック
    if fetch_exception:
        mock_repo.git.fetch.side_effect = Exception("Test fetch exception")
    else:
        mocker.patch.object(mock_repo.git, "fetch")

    # is_semverメソッドの元の実装を使用
    mocker.patch.object(checker, "is_semver", side_effect=checker.is_semver)

    # テスト実行
    result = checker.get_version_tags(mock_repo)

    # 結果の検証
    assert result == expected_result

    # 例外発生時の出力検証
    if fetch_exception:
        captured = capsys.readouterr()
        assert "::warning::タグ取得に失敗しました" in captured.out


@pytest.mark.workflow
@pytest.mark.parametrize(
    ("commit_exists", "expected_result", "expected_commit"),
    [
        pytest.param(True, True, "mock_commit", id="Commit exists"),
        pytest.param(False, False, None, id="No commit"),
    ],
)
def test_read_npm_package_changes(
    checker: VersionChecker,
    commit_exists: bool,
    expected_result: bool,
    expected_commit: Optional[str],
    mocker: MockerFixture,
    capsys: pytest.CaptureFixture,
) -> None:
    """read_npm_package_changesメソッドのテスト"""
    # モックの設定
    mock_commit = mocker.MagicMock() if commit_exists else None
    mocker.patch.object(checker, "get_package_json_from_latest_git_commit", return_value=mock_commit)
    mocker.patch.object(checker, "set_fail_output")

    # テスト実行
    result, commit = checker.read_npm_package_changes()

    # 結果の検証
    assert result == expected_result
    if expected_commit:
        assert commit == mock_commit
    else:
        assert commit is None

    # 出力の検証
    captured = capsys.readouterr()
    if not commit_exists:
        assert "::notice::package.json の変更が見つかりません" in captured.out
        checker.set_fail_output.assert_called_once_with("no_package_change")


@pytest.mark.workflow
@pytest.mark.parametrize(
    ("new_version", "old_version", "expected_result"),
    [
        pytest.param("1.0.1", "1.0.0", True, id="Incremented version"),
        pytest.param("1.0.0", "1.0.0", False, id="Same version"),
        pytest.param("1.0.0", "1.0.1", False, id="Decremented version"),
    ],
)
def test_compare_npm_versions(
    checker: VersionChecker,
    new_version: str,
    old_version: str,
    expected_result: bool,
    mocker: MockerFixture,
    capsys: pytest.CaptureFixture,
) -> None:
    """compare_npm_versionsメソッドのテスト"""
    # モックの設定
    mocker.patch.object(checker, "compare_versions", side_effect=checker.compare_versions)
    mocker.patch.object(checker, "set_fail_output")

    # テスト実行
    result = checker.compare_npm_versions(new_version, old_version)

    # 結果の検証
    assert result == expected_result

    # 出力の検証
    captured = capsys.readouterr()
    if new_version == old_version:
        assert f"::notice::package.jsonにて、バージョンに変更がありません: {new_version}" in captured.out
        checker.set_fail_output.assert_called_once_with("no_version_change")
    elif checker.compare_versions(new_version, old_version) <= 0:
        assert f"::error::package.jsonにて、新しいバージョン ({new_version}) が、過去のバージョン ({old_version}) 以下です" in captured.out
        checker.set_fail_output.assert_called_once_with("version_not_incremented")


@pytest.mark.workflow
@pytest.mark.parametrize(
    ("tags", "npm_version", "expected_result"),
    [
        pytest.param(["v0.9.0", "v1.0.0"], "1.0.1", True, id="Higher version"),
        pytest.param(["v0.9.0", "v1.0.0"], "1.0.0", False, id="Same version"),
        pytest.param(["v0.9.0", "v1.0.0"], "0.9.5", False, id="Lower version"),
        pytest.param([], "1.0.0", True, id="No tags"),
    ],
)
def test_compare_git_tags(
    checker: VersionChecker, tags: list[str], npm_version: str, expected_result: bool, mocker: MockerFixture, capsys: pytest.CaptureFixture
) -> None:
    """compare_git_tagsメソッドのテスト"""
    # モックの設定
    mock_repo = mocker.MagicMock()
    mocker.patch.object(checker, "_git_repo", mock_repo)
    mocker.patch.object(checker, "get_version_tags", return_value=tags)
    mocker.patch.object(checker, "is_semver", return_value=True)
    mocker.patch.object(checker, "compare_versions", side_effect=checker.compare_versions)
    mocker.patch.object(checker, "set_fail_output")

    # テスト実行
    result = checker.compare_git_tags(npm_version)

    # 結果の検証
    assert result == expected_result

    # 出力の検証
    captured = capsys.readouterr()
    if tags and not expected_result:
        latest_tag = tags[-1]
        latest_version = latest_tag[1:] if latest_tag.startswith("v") else latest_tag
        assert f"::error::package.jsonにて、新しいバージョン ({npm_version}) が、最新タグ ({latest_version}) 以下です" in captured.out
        checker.set_fail_output.assert_called_once_with("version_not_incremented_from_tag")


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
    result = main()

    # 検証
    mock_checker.run.assert_called_once()
    assert result == 0

    # 異常系のテスト
    mock_checker.run.return_value = 1
    result = main()
    assert result == 1
