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

from check_version import InvalidGitRepositoryError, VersionChecker
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
    """set_github_outputメソッドのテスト"""
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
    ("package_json_exists", "expected_result", "expected_fail_reason"),
    [
        pytest.param(True, True, None, id="package.json exists"),
        pytest.param(False, False, "package_missing", id="package.json missing"),
    ],
)
def test_check_package_json_exists(
    checker: VersionChecker,
    package_json_exists: bool,
    expected_result: bool,
    expected_fail_reason: Optional[str],
    mocker: MockerFixture,
    capsys: pytest.CaptureFixture,
) -> None:
    """check_package_json_existsメソッドのテスト"""
    # Path.existsをモック化
    mocker.patch("pathlib.Path.exists", return_value=package_json_exists)
    mocker.patch.object(checker, "set_fail_output")

    # テスト実行
    result = checker.check_package_json_exists()

    # 結果の検証
    assert result == expected_result

    # 出力の検証
    captured = capsys.readouterr()
    if not package_json_exists:
        assert "::error::package.json ファイルが見つかりません" in captured.out
        checker.set_fail_output.assert_called_once_with("package_missing")
    else:
        checker.set_fail_output.assert_not_called()


@pytest.mark.workflow
@pytest.mark.parametrize(
    ("branch_name", "file_path", "fetch_success", "commit_exists", "blob_exists", "version_in_json", "expected_result"),
    [
        pytest.param("main", "package.json", True, True, True, "1.0.0", "1.0.0", id="Success main package.json"),
        pytest.param("develop", "package.json", True, True, True, "1.1.0", "1.1.0", id="Success develop package.json"),
        pytest.param("develop", "package-lock.json", True, True, True, "1.1.0", "1.1.0", id="Success develop package-lock.json"),
        pytest.param("main", "package.json", False, True, True, "1.0.0", None, id="Fetch error"),
        pytest.param("main", "package.json", True, False, True, "1.0.0", None, id="Commit error"),
        pytest.param("main", "package.json", True, True, False, "1.0.0", None, id="Blob error"),
        pytest.param("main", "package.json", True, True, True, None, None, id="No version in JSON"),
    ],
)
def test_get_version_from_branch(
    checker: VersionChecker,
    branch_name: str,
    file_path: str,
    fetch_success: bool,
    commit_exists: bool,
    blob_exists: bool,
    version_in_json: Optional[str],
    expected_result: Optional[str],
    mocker: MockerFixture,
    capsys: pytest.CaptureFixture,
) -> None:
    """get_version_from_branchメソッドのテスト"""
    # モックの設定
    mock_repo = mocker.MagicMock()
    mock_commit = mocker.MagicMock()
    mock_tree = mocker.MagicMock()
    mock_blob = mocker.MagicMock()
    mock_data_stream = mocker.MagicMock()

    mocker.patch.object(checker, "_git_repo", mock_repo)

    # fetch呼び出しのモック
    if not fetch_success:
        mock_repo.git.fetch.side_effect = Exception("Test fetch exception")
    else:
        mock_repo.git.fetch.return_value = None

    # commitのモック
    if not commit_exists:
        mock_repo.commit.side_effect = Exception("Test commit exception")
    else:
        mock_repo.commit.return_value = mock_commit
        mock_commit.tree = mock_tree

        # blobのモック
        if not blob_exists:
            mock_tree.__truediv__.side_effect = KeyError("Test blob exception")
        else:
            mock_tree.__truediv__.return_value = mock_blob
            mock_blob.data_stream = mock_data_stream

            # JSONデータのモック
            json_content = f'{{"version": "{version_in_json}"}}' if version_in_json else "{}"
            mock_data_stream.read.return_value = json_content.encode("utf-8")

    # テスト実行
    result = checker.get_version_from_branch(branch_name, file_path)

    # 結果の検証
    assert result == expected_result

    # 出力の検証
    captured = capsys.readouterr()
    if not fetch_success or not commit_exists:
        assert f"::error::{branch_name}ブランチから{file_path}のバージョン取得に失敗しました" in captured.out
    elif not blob_exists:
        assert f"::error::{branch_name}ブランチに{file_path}が見つかりません" in captured.out
    elif version_in_json is None:
        assert f"::error::{branch_name}ブランチの{file_path}にバージョンが見つかりません" in captured.out


@pytest.mark.workflow
@pytest.mark.parametrize(
    (
        "package_json_version",
        "package_lock_version",
        "is_semver_result",
        "expected_result",
        "expected_package_version",
        "expected_lock_version",
        "expected_fail_reason",
    ),
    [
        # 正常系: バージョンが一致
        pytest.param("1.0.0", "1.0.0", True, True, "1.0.0", "1.0.0", None, id="Matching versions"),
        # 異常系: package.jsonのバージョン取得失敗
        pytest.param(None, "1.0.0", True, False, None, None, "develop_package_json_version_error", id="package.json version error"),
        # 異常系: package-lock.jsonのバージョン取得失敗
        pytest.param("1.0.0", None, True, False, None, None, "develop_package_lock_version_error", id="package-lock.json version error"),
        # 異常系: バージョン不一致
        pytest.param("1.0.0", "1.0.1", True, False, "1.0.0", "1.0.1", "develop_version_mismatch", id="Version mismatch"),
        # 警告: セマンティックバージョニングに従っていない
        pytest.param("invalid", "invalid", False, True, "invalid", "invalid", None, id="Invalid semver"),
    ],
)
def test_check_develop_package_versions_match(
    checker: VersionChecker,
    package_json_version: Optional[str],
    package_lock_version: Optional[str],
    is_semver_result: bool,
    expected_result: bool,
    expected_package_version: Optional[str],
    expected_lock_version: Optional[str],
    expected_fail_reason: Optional[str],
    mocker: MockerFixture,
    capsys: pytest.CaptureFixture,
) -> None:
    """check_develop_package_versions_matchメソッドのテスト"""
    # モックの設定
    mocker.patch.object(
        checker,
        "get_version_from_branch",
        side_effect=lambda branch, file_path: package_json_version if file_path == "package.json" else package_lock_version,
    )
    mocker.patch.object(checker, "is_semver", return_value=is_semver_result)
    mocker.patch.object(checker, "set_fail_output")

    # テスト実行
    result, actual_package_version, actual_lock_version = checker.check_develop_package_versions_match()

    # 結果の検証
    assert result == expected_result
    assert actual_package_version == expected_package_version
    assert actual_lock_version == expected_lock_version

    # 出力の検証
    captured = capsys.readouterr()
    if package_json_version and not is_semver_result:
        assert f"::warning::developブランチのpackage.jsonのバージョン形式が正しくありません: {package_json_version}" in captured.out

    if package_json_version and package_lock_version and package_json_version != package_lock_version:
        assert (
            f"::error::developブランチのpackage.json「{package_json_version}」はpackage-lock.json「{package_lock_version}」のバージョンと一致していません"
            in captured.out
        )
        assert "::error::package-lock.json の更新が必要です。'npm install' または 'npm ci' を実行してください" in captured.out

    # 失敗理由の検証
    if expected_fail_reason:
        checker.set_fail_output.assert_called_once_with(expected_fail_reason)
    else:
        checker.set_fail_output.assert_not_called()


@pytest.mark.workflow
@pytest.mark.parametrize(
    (
        "package_json_exists",
        "develop_versions_match",
        "develop_package_version",
        "develop_lock_version",
        "main_version",
        "main_semver_valid",
        "version_comparison",
        "expected_result",
        "expected_output",
    ),
    [
        # 正常系
        pytest.param(
            True,
            True,
            "1.1.0",
            "1.1.0",
            "1.0.0",
            True,
            1,
            0,
            "::notice::developブランチのバージョン「1.1.0」がmainブランチのバージョン「1.0.0」より大きいことを確認しました",
            id="Success",
        ),
        # package.jsonが存在しない
        pytest.param(False, True, "1.1.0", "1.1.0", "1.0.0", True, 1, 1, None, id="package.json missing"),
        # developブランチのpackage.jsonとpackage-lock.jsonのバージョンが一致しない
        pytest.param(True, False, "1.1.0", "1.0.0", "1.0.0", True, 1, 0, None, id="develop versions mismatch"),
        # developブランチのpackage.jsonのバージョン取得失敗
        pytest.param(True, False, None, "1.1.0", "1.0.0", True, 1, 0, None, id="develop package.json version error"),
        # mainブランチのバージョン取得失敗
        pytest.param(True, True, "1.1.0", "1.1.0", None, True, 1, 0, None, id="main version error"),
        # バージョン形式警告(main)
        pytest.param(
            True,
            True,
            "1.1.0",
            "1.1.0",
            "1.0.0",
            False,
            1,
            0,
            "::warning::mainブランチのバージョン形式が正しくありません: 1.0.0",
            id="Invalid main version format - バージョン形式警告(main)",
        ),
        # バージョン比較失敗(同じ)
        pytest.param(
            True,
            True,
            "1.0.0",
            "1.0.0",
            "1.0.0",
            True,
            0,
            0,
            "::error::developブランチのバージョン「1.0.0」がmainブランチのバージョン「1.0.0」以下です",
            id="Same version - バージョン比較失敗(同じ)",
        ),
        # バージョン比較失敗(低い)
        pytest.param(
            True,
            True,
            "1.0.0",
            "1.0.0",
            "1.1.0",
            True,
            -1,
            0,
            "::error::developブランチのバージョン「1.0.0」がmainブランチのバージョン「1.1.0」以下です",
            id="Lower version - バージョン比較失敗(低い)",
        ),
    ],
)
def test_run(
    checker: VersionChecker,
    package_json_exists: bool,
    develop_versions_match: bool,
    develop_package_version: Optional[str],
    develop_lock_version: Optional[str],
    main_version: Optional[str],
    main_semver_valid: bool,
    version_comparison: int,
    expected_result: int,
    expected_output: Optional[str],
    mocker: MockerFixture,
    capsys: pytest.CaptureFixture,
) -> None:
    """runメソッドのテスト"""
    # モックの設定
    mocker.patch.object(checker, "check_package_json_exists", return_value=package_json_exists)
    mocker.patch.object(
        checker,
        "check_develop_package_versions_match",
        return_value=(develop_versions_match, develop_package_version, develop_lock_version),
    )

    # get_version_from_branchのモック
    mocker.patch.object(checker, "get_version_from_branch", return_value=main_version)

    # is_semverのモック
    def mock_is_semver(version_str: str) -> bool:
        if version_str == main_version:
            return main_semver_valid
        return True

    mocker.patch.object(checker, "is_semver", side_effect=mock_is_semver)

    # compare_versionsのモック
    mocker.patch.object(checker, "compare_versions", return_value=version_comparison)

    # set_github_outputとset_fail_outputのモック
    mocker.patch.object(checker, "set_github_output")
    mocker.patch.object(checker, "set_fail_output")

    # テスト実行
    result = checker.run()

    # 結果の検証
    assert result == expected_result

    # 出力の検証
    captured = capsys.readouterr()
    if expected_output:
        assert expected_output in captured.out

    # 成功時の出力検証
    if (
        expected_result == 0
        and develop_versions_match
        and develop_package_version is not None
        and main_version is not None
        and version_comparison > 0
    ):
        checker.set_github_output.assert_any_call("status", "success")
        checker.set_github_output.assert_any_call("version_changed", "true")
        checker.set_github_output.assert_any_call("develop_version", develop_package_version)
        checker.set_github_output.assert_any_call("main_version", main_version)


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
        pytest.param(
            lambda: InvalidGitRepositoryError("Invalid git repository"),
            "::error::gitリポジトリが不正です",
            "repo_not_initialized",
            id="InvalidGitRepositoryError",
        ),
        pytest.param(
            lambda: Exception("An unexpected error"),
            "::error::予期せぬエラーが発生しました: An unexpected error",
            "unexpected_error",
            id="Other exception",
        ),
    ],
)
def test_run_exceptions(
    checker: VersionChecker,
    exception_factory: Callable[[], Exception],
    expected_output: str,
    expected_reason: str,
    mocker: MockerFixture,
    capsys: pytest.CaptureFixture,
) -> None:
    """runメソッドの例外テスト"""
    # モックの設定
    exception = exception_factory()
    mocker.patch.object(checker, "check_package_json_exists", side_effect=exception)
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
