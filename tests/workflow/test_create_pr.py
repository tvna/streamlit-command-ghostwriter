#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""create_pr.pyのユニットテストモジュール。

このモジュールは、scripts/create_pr.py内のPullRequestCreatorクラスの
機能をテストするためのテストケースを提供します。

テストの主な対象:
- GitHub Actions関連のメソッド (github_notice, github_warning, github_error)
- 環境変数の処理 (set_github_output)
- コマンド検証と実行 (validate_command, run_gh_cmd)
- Git操作 (get_latest_commit_message, get_commit_titles)
- PRの作成と管理 (create_pr, prepare_pr_content, run)

これらのテストは、モックを使用して外部依存性を分離し、
様々な条件下での動作を検証します。
"""

import os
from typing import List, Optional, Union
from unittest.mock import MagicMock, Mock

import pytest
from pytest_mock import MockerFixture

from scripts.create_pr import PullRequestCreator


@pytest.fixture
def creator() -> PullRequestCreator:
    """PullRequestCreatorのインスタンスを提供するフィクスチャ。

    各テストで使用するPullRequestCreatorの新しいインスタンスを作成します。
    これにより、テスト間の状態の分離が保証されます。

    Returns:
        初期化されたPullRequestCreatorインスタンス
    """
    creator_instance = PullRequestCreator()
    return creator_instance


@pytest.mark.workflow
@pytest.mark.parametrize(
    ("method", "test_message", "expected_output"),
    [
        pytest.param("github_notice", "テスト通知", "::notice::テスト通知\n", id="github_notice"),
        pytest.param("github_warning", "テスト警告", "::warning::テスト警告\n", id="github_warning"),
        pytest.param("github_error", "テストエラー", "::error::テストエラー\n", id="github_error"),
    ],
)
def test_github_methods(
    creator: PullRequestCreator, method: str, test_message: str, expected_output: str, capsys: pytest.CaptureFixture
) -> None:
    """GitHub Actions向けの通知メソッドをテストする。

    github_notice、github_warning、github_errorの各メソッドが
    正しい形式で標準出力にメッセージを出力することを検証します。

    Args:
        creator: テスト対象のPullRequestCreatorインスタンス
        method: テスト対象のメソッド名
        test_message: テストで使用するメッセージ
        expected_output: 期待される出力文字列
        capsys: 標準出力をキャプチャするフィクスチャ
    """
    getattr(creator, method)(test_message)  # メソッドを動的に呼び出す

    captured = capsys.readouterr()
    assert captured.out == expected_output


@pytest.mark.workflow
@pytest.mark.parametrize(
    ("env_key", "env_value", "isfile_return", "expected_path_call_count", "expected_output"),
    [
        pytest.param("GITHUB_OUTPUT", "github_output.txt", True, 1, "", id="環境変数あり・ファイルあり"),
        pytest.param("GITHUB_OUTPUT", None, False, 0, "GITHUB_OUTPUT環境変数が設定されていません\n", id="環境変数なし"),
        pytest.param(None, None, False, 0, "GITHUB_OUTPUT環境変数が設定されていません\n", id="環境変数キーなし"),
    ],
)
def test_set_github_output_improved(
    env_key: Optional[str],
    env_value: Optional[str],
    isfile_return: bool,
    expected_path_call_count: int,
    expected_output: str,
    creator: PullRequestCreator,
    capsys: pytest.CaptureFixture,
    mocker: MockerFixture,
) -> None:
    """set_github_outputメソッドの改良版テスト - GitHub Actions環境でも動作する。

    GitHub Actions環境で実行される場合[GITHUB_OUTPUT環境変数が既に設定されている場合]は、
    エラーチェックをスキップして正常系のテストのみを実行します。

    Args:
        env_key: テストする環境変数のキー
        env_value: テストする環境変数の値
        isfile_return: os.path.isfileの戻り値
        expected_path_call_count: os.path.isfileの呼び出し回数の期待値
        expected_output: 期待される標準出力
        creator: テスト対象のPullRequestCreatorインスタンス
        capsys: 標準出力をキャプチャするフィクスチャ
        mocker: モックを作成するためのフィクスチャ
    """
    # GitHub Actions環境で実行されている場合はスキップ
    if "GITHUB_OUTPUT" in os.environ and env_key != "GITHUB_OUTPUT":
        pytest.skip("GitHub Actions環境では実行しません")

    # 現在の環境変数を保存
    original_env = os.environ.copy()

    try:
        # 環境変数の設定 [テスト用]
        if env_key is not None:
            if env_value is not None:
                os.environ[env_key] = env_value
            elif env_key in os.environ:
                del os.environ[env_key]

        # ファイル存在チェックのモック
        mock_path = mocker.patch.object(os.path, "isfile", return_value=isfile_return)

        # ファイル書き込みのモック
        mock_open = mocker.patch("builtins.open", new_callable=mocker.mock_open)

        # テスト実行
        creator.set_github_output("test_name", "test_value")
        captured = capsys.readouterr()

        # 検証
        assert mock_path.call_count == expected_path_call_count
        assert captured.out == expected_output

        # ファイルが存在する場合は書き込みが行われることを確認
        if isfile_return and env_value:
            mock_open.assert_called_once_with(env_value, "a")
            mock_open().write.assert_called_once_with("test_name=test_value\n")
        else:
            mock_open.assert_not_called()

    finally:
        # 環境変数を元に戻す
        os.environ.clear()
        os.environ.update(original_env)


@pytest.mark.workflow
@pytest.mark.parametrize(
    ("command", "expected_result"),
    [
        pytest.param([""], False, id="空のリストが無効なコマンドの場合"),
        pytest.param(["echo", "hello"], False, id="echo helloが無効なコマンドの場合"),
        pytest.param(["echo", "hello", ">", "output.txt"], False, id="echo hello > output.txtが無効なコマンドの場合"),
        pytest.param(["gh", "auth", "status"], True, id="gh auth statusが有効なコマンドの場合"),
        pytest.param(["gh", "pr", "create"], True, id="gh pr createが有効なコマンドの場合"),
        pytest.param(["gh", "pr", "create", "|", "grep"], False, id="gh pr create | grepが無効なコマンドの場合"),
        pytest.param(["git", "push", "|", "grep"], False, id="git push | grepが無効なコマンドの場合"),
        pytest.param(["git", "push", "|", "grep", "hello"], False, id="git push | grep helloが無効なコマンドの場合"),
        pytest.param(["git", "status"], False, id="git statusが無効なコマンドの場合"),
        pytest.param(["git", "&&", "status"], False, id="git && statusが無効なコマンドの場合"),
        pytest.param(["invalid_command"], False, id="invalid_commandが無効なコマンドの場合"),
        pytest.param(["npm", "install", "&", "rm"], False, id="npm install & rmが無効なコマンドの場合"),
        pytest.param(["npm", "version"], False, id="npm versionが無効なコマンドの場合"),
        pytest.param(["rm", "-rf", "/"], False, id="rm -rf /が無効なコマンドの場合"),
        pytest.param([";"], False, id=";が無効なコマンドの場合"),
        pytest.param(["jq", "."], False, id="jq .が無効なコマンドの場合"),
        pytest.param(["ls", "-l"], False, id="ls -lが無効なコマンドの場合"),
    ],
)
def test_validate_command(command: list, expected_result: bool, creator: PullRequestCreator) -> None:
    """コマンドのvalidate_commandメソッドのテスト"""
    result = creator.validate_command(command)
    assert result == expected_result


@pytest.mark.parametrize(
    (
        "command",
        "env_var",
        "expected_run_calls",
        "expected_error_calls",
        "expected_warning_calls",
        "expected_notice_calls",
    ),
    [
        pytest.param(["pr", "create"], "GH_TOKEN", 1, 0, 0, 0, id="成功ケース"),
        pytest.param(["pr", "create"], None, 0, 1, 0, 0, id="GH_TOKEN未設定"),
        pytest.param(["rm", "-rf", "/"], "GH_TOKEN", 0, 1, 0, 0, id="無効なコマンド"),
        pytest.param(["pr", "create", "|", "grep"], "GH_TOKEN", 0, 1, 0, 0, id="危険な文字を含む引数"),
    ],
)
def test_run_gh_cmd(
    command: list,
    env_var: Optional[str],
    expected_run_calls: int,
    expected_error_calls: int,
    expected_warning_calls: int,
    expected_notice_calls: int,
    creator: PullRequestCreator,
    mocker: MockerFixture,
) -> None:
    """run_gh_cmdメソッドのテストをまとめたもの"""
    if env_var:
        mock_env = mocker.patch.dict(os.environ, {env_var: "dummy_token"})
    else:
        mock_env = mocker.patch.dict(os.environ, {})

    mock_error = mocker.patch.object(PullRequestCreator, "github_error")
    mock_warning = mocker.patch.object(PullRequestCreator, "github_warning")
    mock_notice = mocker.patch.object(PullRequestCreator, "github_notice")
    mocker.patch.object(PullRequestCreator, "validate_command", return_value=(command != ["rm", "-rf", "/"]))

    mock_run = mocker.patch("subprocess.run")
    result = creator.run_gh_cmd(command)

    assert result is False
    assert mock_env is os.environ
    assert mock_run.call_count == expected_run_calls
    assert mock_error.call_count == expected_error_calls
    assert mock_warning.call_count == expected_warning_calls
    assert mock_notice.call_count == expected_notice_calls


@pytest.mark.workflow
@pytest.mark.parametrize(
    ("repo_side_effect", "commit_message", "expected_result", "expected_notice_calls", "expected_warning_calls", "expected_error_calls"),
    [
        pytest.param(None, "Test commit message", "Test commit message", 0, 0, 0, id="通常のメッセージ"),
        pytest.param(None, "Add token ghp_abcdef123456", "Add token ghp_***", 0, 1, 0, id="機密情報を含むメッセージ"),
        pytest.param(Exception("Not a git repository"), None, "Unable to fetch commit message", 0, 1, 0, id="例外発生時"),
    ],
)
def test_get_latest_commit_message(
    creator: PullRequestCreator,
    mocker: MockerFixture,
    repo_side_effect: Optional[Exception],
    commit_message: Optional[str],
    expected_result: str,
    expected_notice_calls: int,
    expected_warning_calls: int,
    expected_error_calls: int,
) -> None:
    """get_latest_commit_messageメソッドのテスト"""
    # Repoのモック設定
    if repo_side_effect:
        mock_repo = mocker.patch("git.Repo", side_effect=repo_side_effect)
    else:
        mock_repo = mocker.patch("git.Repo")
        mock_repo_instance = mock_repo.return_value
        mock_commit = mocker.MagicMock()
        mock_commit.message = commit_message
        mock_repo_instance.head.commit = mock_commit

    # 通知メソッドのモック
    mock_notice = mocker.patch.object(PullRequestCreator, "github_notice")
    mock_warning = mocker.patch.object(PullRequestCreator, "github_warning")
    mock_error = mocker.patch.object(PullRequestCreator, "github_error")

    # テスト実行
    result = creator.get_latest_commit_message()

    # 検証
    assert result == expected_result
    mock_repo.assert_called_once_with(".")
    assert mock_notice.call_count == expected_notice_calls
    assert mock_warning.call_count == expected_warning_calls
    assert mock_error.call_count == expected_error_calls


@pytest.mark.workflow
@pytest.mark.parametrize(
    ("fetch_side_effect", "commit_messages", "expected_result"),
    [
        pytest.param(
            None, ["First commit\nDetails here", "Second commit\nMore details"], ["- First commit", "- Second commit"], id="正常ケース"
        ),
        pytest.param(Exception("Fetch failed"), None, ["Unable to fetch commit titles"], id="Fetch例外ケース"),
    ],
)
def test_get_commit_titles(
    creator: PullRequestCreator,
    mocker: MockerFixture,
    fetch_side_effect: Optional[Exception],
    commit_messages: Optional[List[str]],
    expected_result: List[str],
) -> None:
    """get_commit_titlesメソッドのテスト"""
    # Repoのモック設定
    mock_repo = mocker.patch("git.Repo")
    mock_repo_instance = mock_repo.return_value

    # fetch側の設定
    if fetch_side_effect:
        mock_repo_instance.git.fetch.side_effect = fetch_side_effect
    else:
        # コミットのモック設定
        commits = []
        if commit_messages:
            for message in commit_messages:
                mock_commit = mocker.MagicMock()
                mock_commit.message = message
                commits.append(mock_commit)
        mock_repo_instance.iter_commits.return_value = commits

    # テスト実行
    result = creator.get_commit_titles()

    # 検証
    assert result == expected_result
    mock_repo.assert_called_once_with(".")
    mock_repo_instance.git.fetch.assert_called_once_with("origin", "main:main")

    # 正常ケースの場合のみiter_commitsの呼び出しを検証
    if not fetch_side_effect:
        mock_repo_instance.iter_commits.assert_called_once_with("main..develop", max_count=10)


@pytest.mark.workflow
@pytest.mark.parametrize(
    ("labels", "expected_args"),
    [
        pytest.param(
            ["bug", "enhancement"],
            [
                "pr",
                "create",
                "--base",
                "main",
                "--head",
                "develop",
                "--title",
                "Test PR",
                "--body",
                "PR body",
                "--label",
                "bug,enhancement",
            ],
            id="ラベルあり",
        ),
        pytest.param(
            [],
            [
                "pr",
                "create",
                "--base",
                "main",
                "--head",
                "develop",
                "--title",
                "Test PR",
                "--body",
                "PR body",
            ],
            id="ラベルなし",
        ),
    ],
)
def test_create_pr(creator: PullRequestCreator, mocker: MockerFixture, labels: list, expected_args: list) -> None:
    """create_prメソッドのテスト"""
    mock_env = mocker.patch.dict(os.environ, {"GH_TOKEN": "dummy_token"})
    mock_run_gh_cmd = mocker.patch.object(PullRequestCreator, "run_gh_cmd", return_value=True)

    result = creator.create_pr("Test PR", "PR body", labels)
    assert result
    assert mock_env is os.environ
    mock_run_gh_cmd.assert_called_once_with(expected_args)


@pytest.mark.workflow
@pytest.mark.parametrize(
    ("env_vars", "expected_result", "expected_new_version", "expected_old_version", "expected_error_calls"),
    [
        pytest.param({"NEW_VERSION": "1.0.0", "OLD_VERSION": "0.9.0"}, True, "1.0.0", "0.9.0", 0, id="成功ケース"),
        pytest.param({"NEW_VERSION": "", "OLD_VERSION": "0.9.0"}, False, "", "0.9.0", 1, id="新バージョンがない場合"),
        pytest.param({"NEW_VERSION": "1.0.0", "OLD_VERSION": ""}, False, "1.0.0", "", 1, id="旧バージョンがない場合"),
        pytest.param({}, False, None, None, 1, id="両方のバージョンがない場合"),
    ],
)
def test_get_version_info(
    creator: PullRequestCreator,
    mocker: MockerFixture,
    env_vars: dict,
    expected_result: bool,
    expected_new_version: Optional[str],
    expected_old_version: Optional[str],
    expected_error_calls: int,
) -> None:
    """get_version_infoメソッドのテスト"""
    # 環境変数のモック
    mocker.patch.dict(os.environ, env_vars)
    mock_error = mocker.patch.object(PullRequestCreator, "github_error")

    # テスト実行
    result = creator.get_version_info()

    # 検証
    assert result == expected_result
    assert mock_error.call_count == expected_error_calls
    assert creator.new_version == expected_new_version
    assert creator.old_version == expected_old_version


@pytest.mark.workflow
def test_prepare_pr_content(creator: PullRequestCreator, mocker: MockerFixture) -> None:
    """prepare_pr_contentメソッドのテスト"""
    creator.new_version = "1.0.0"
    creator.old_version = "0.9.0"

    mocker.patch.object(PullRequestCreator, "get_latest_commit_message", return_value="Test commit")
    mocker.patch.object(PullRequestCreator, "get_commit_titles", return_value=["- Commit 1", "- Commit 2"])

    title, body, labels = creator.prepare_pr_content()

    assert title == "Release v1.0.0"
    assert "develop から main へのバージョン 1.0.0 の自動 PR" in body
    assert "v0.9.0 から v1.0.0 に更新された" in body
    assert "Test commit" in body
    assert "- Commit 1" in body
    assert "- Commit 2" in body
    assert labels == ["automated-pr", "release"]


@pytest.mark.parametrize(
    ("new_version", "old_version", "get_version_info_return", "expected_result", "expected_notice_calls", "expected_create_pr_calls"),
    [
        # 成功ケース
        pytest.param(
            "1.0.0",
            "0.9.0",
            True,
            0,
            3,  # PRの作成準備中..., PRを作成中..., PRが作成されました
            1,
            id="成功ケース",
        ),
        # バージョン情報エラー時
        pytest.param(
            "",
            "",
            False,
            1,
            1,  # PRの作成準備中...
            0,
            id="バージョン情報エラー時",
        ),
    ],
)
def test_run(
    creator: PullRequestCreator,
    mocker: MockerFixture,
    new_version: str,
    old_version: str,
    get_version_info_return: bool,
    expected_result: int,
    expected_notice_calls: int,
    expected_create_pr_calls: int,
) -> None:
    """runメソッドのテスト"""
    # 環境変数のモック
    mocker.patch.dict(os.environ, {"NEW_VERSION": new_version, "OLD_VERSION": old_version})

    # 通知メソッドのモック
    mock_notice = mocker.patch.object(PullRequestCreator, "github_notice")

    # get_version_infoのモック
    mocker.patch.object(PullRequestCreator, "get_version_info", return_value=get_version_info_return)

    # 成功ケースの場合のみ追加のモックが必要
    mocker.patch.object(PullRequestCreator, "prepare_pr_content", return_value=("Test Title", "Test Body", ["test-label"]))
    mock_create_pr = mocker.patch.object(PullRequestCreator, "create_pr", return_value=True)

    # テスト実行
    result = creator.run()

    # 検証
    assert result == expected_result
    assert mock_notice.call_count == expected_notice_calls
    assert mock_create_pr.call_count == expected_create_pr_calls

    # create_prが呼ばれた場合のみ引数を検証
    if expected_create_pr_calls > 0:
        mock_create_pr.assert_called_once_with("Test Title", "Test Body", ["test-label"])


@pytest.mark.workflow
@pytest.mark.parametrize(
    ("title", "body", "labels", "expected_result", "expected_error_calls"),
    [
        pytest.param("Test PR", "Test Body", ["test-label"], True, 0, id="正常ケース"),
        pytest.param(123, "Test Body", ["test-label"], False, 1, id="タイトルが文字列でない"),
        pytest.param("Test PR", None, ["test-label"], False, 1, id="本文がNone"),
        pytest.param("Test PR", "Test Body", "not-a-list", False, 1, id="ラベルがリストでない"),
    ],
)
def test_create_pr_input_validation(
    creator: PullRequestCreator,
    mocker: MockerFixture,
    title: Union[str, int],
    body: Union[str, None],
    labels: Union[List[str], str],
    expected_result: bool,
    expected_error_calls: int,
) -> None:
    """create_prメソッドの入力検証テスト"""
    mocker.patch.dict(os.environ, {"GH_TOKEN": "dummy_token"})
    mock_error = mocker.patch.object(PullRequestCreator, "github_error")
    mock_run_gh_cmd = mocker.patch.object(PullRequestCreator, "run_gh_cmd", return_value=True)

    # 型チェックを無視して引数を渡す
    result = creator.create_pr(title, body, labels)  # type: ignore

    assert result == expected_result
    assert mock_error.call_count == expected_error_calls

    if expected_result:
        mock_run_gh_cmd.assert_called_once()
    else:
        mock_run_gh_cmd.assert_not_called()


@pytest.mark.workflow
@pytest.mark.parametrize(
    (
        "max_commits",
        "is_valid_input",
        "mock_commits",
        "expected_result",
        "expected_error_calls",
        "expected_repo_calls",
        "expected_fetch_calls",
        "expected_iter_commits_calls",
        "expected_repo_call_args",
        "expected_fetch_call_args",
        "expected_iter_commits_call_args",
    ),
    [
        # 正常ケース
        (
            10,
            True,
            [{"message": "Commit 1\nDetails here"}, {"message": "Commit 2\nMore details"}],
            ["- Commit 1", "- Commit 2"],
            0,
            1,
            1,
            1,
            [(".",)],
            [("origin", "main:main")],
            [("main..develop",), {"max_count": 10}],
        ),
        # 負の値
        (-1, False, [], [], 1, 0, 0, 0, [], [], []),
        # 整数でない値
        ("not-an-int", False, [], [], 1, 0, 0, 0, [], [], []),
    ],
)
def test_get_commit_titles_input_validation(
    creator: PullRequestCreator,
    mocker: MockerFixture,
    max_commits: Union[int, str],
    is_valid_input: bool,
    mock_commits: List[dict],
    expected_result: list,
    expected_error_calls: int,
    expected_repo_calls: int,
    expected_fetch_calls: int,
    expected_iter_commits_calls: int,
    expected_repo_call_args: List[tuple],
    expected_fetch_call_args: List[tuple],
    expected_iter_commits_call_args: List[Union[tuple, dict]],
) -> None:
    """get_commit_titlesメソッドの入力検証テスト"""
    # Repoのモック設定
    mock_repo = mocker.patch("git.Repo")
    mock_repo_instance = mock_repo.return_value
    mock_error = mocker.patch.object(PullRequestCreator, "github_error")

    # コミットのモック設定
    commits = []
    for commit_data in mock_commits:
        mock_commit = mocker.MagicMock()
        mock_commit.message = commit_data["message"]
        commits.append(mock_commit)

    mock_repo_instance.iter_commits.return_value = commits

    # テスト実行
    result = creator.get_commit_titles(max_commits)  # type: ignore

    # 検証
    assert mock_error.call_count == expected_error_calls
    assert result == expected_result

    # Repoの呼び出し検証
    assert mock_repo.call_count == expected_repo_calls

    # 呼び出し引数の検証
    _verify_call_args(mock_repo, expected_repo_call_args)
    _verify_call_args(mock_repo_instance.git.fetch, expected_fetch_call_args)

    # iter_commitsの呼び出し検証
    assert mock_repo_instance.iter_commits.call_count == expected_iter_commits_calls

    # iter_commitsの呼び出し引数検証(位置引数とキーワード引数の両方を処理)
    if expected_iter_commits_calls > 0:
        args, kwargs = expected_iter_commits_call_args
        mock_repo_instance.iter_commits.assert_called_with(*args, **kwargs)


def _verify_call_args(mock_obj: Union[Mock, MagicMock], expected_call_args: List[tuple]) -> None:
    """モックオブジェクトの呼び出し引数を検証するヘルパー関数"""
    if not expected_call_args:
        return

    # 実際の呼び出し回数と期待する引数リストの長さが一致することを確認
    assert mock_obj.call_count == len(expected_call_args)

    # 各呼び出しの引数を検証
    for i, args in enumerate(expected_call_args):
        call_args = mock_obj.call_args_list[i][0]
        assert call_args == args


@pytest.mark.workflow
@pytest.mark.parametrize(
    ("file_exists", "expected_output"),
    [
        pytest.param(True, "", id="ファイルが存在する場合"),
        pytest.param(False, "指定されたファイルが見つかりません: github_output.txt\n", id="ファイルが存在しない場合"),
    ],
)
def test_set_github_output_file_not_found(
    creator: PullRequestCreator,
    mocker: MockerFixture,
    capsys: pytest.CaptureFixture,
    file_exists: bool,
    expected_output: str,
) -> None:
    """set_github_outputメソッドのファイル存在チェックテスト"""
    mocker.patch.dict(os.environ, {"GITHUB_OUTPUT": "github_output.txt"})
    mock_isfile = mocker.patch.object(os.path, "isfile", return_value=file_exists)
    mock_open = mocker.patch("builtins.open", new_callable=mocker.mock_open)

    creator.set_github_output("test_name", "test_value")
    captured = capsys.readouterr()

    assert captured.out == expected_output
    mock_isfile.assert_called_once_with("github_output.txt")

    if file_exists:
        mock_open.assert_called_once_with("github_output.txt", "a")
        mock_open().write.assert_called_once_with("test_name=test_value\n")
    else:
        mock_open.assert_not_called()


@pytest.mark.workflow
@pytest.mark.parametrize(
    ("create_pr_result", "expected_result", "expected_error_calls", "expected_notice_calls"),
    [
        pytest.param(True, 0, 0, 3, id="PRの作成成功"),
        pytest.param(False, 1, 1, 2, id="PRの作成失敗"),
    ],
)
def test_run_pr_creation(
    creator: PullRequestCreator,
    mocker: MockerFixture,
    create_pr_result: bool,
    expected_result: int,
    expected_error_calls: int,
    expected_notice_calls: int,
) -> None:
    """runメソッドのPR作成結果テスト"""
    mocker.patch.dict(os.environ, {"NEW_VERSION": "1.0.0", "OLD_VERSION": "0.9.0"})
    mocker.patch.object(PullRequestCreator, "get_version_info", return_value=True)
    mocker.patch.object(PullRequestCreator, "prepare_pr_content", return_value=("Test Title", "Test Body", ["test-label"]))
    mock_create_pr = mocker.patch.object(PullRequestCreator, "create_pr", return_value=create_pr_result)
    mock_error = mocker.patch.object(PullRequestCreator, "github_error")
    mock_notice = mocker.patch.object(PullRequestCreator, "github_notice")

    result = creator.run()

    assert result == expected_result
    assert mock_error.call_count == expected_error_calls
    assert mock_notice.call_count == expected_notice_calls
    mock_create_pr.assert_called_once_with("Test Title", "Test Body", ["test-label"])


@pytest.mark.workflow
def test_run_exception(creator: PullRequestCreator, mocker: MockerFixture) -> None:
    """runメソッドの例外処理テスト"""
    mocker.patch.object(PullRequestCreator, "get_version_info", side_effect=Exception("Test exception"))
    mock_error = mocker.patch.object(PullRequestCreator, "github_error")

    result = creator.run()

    assert result == 1
    mock_error.assert_called_once()
    assert "予期せぬエラーが発生しました" in mock_error.call_args[0][0]


@pytest.mark.workflow
def test_main_function(mocker: MockerFixture) -> None:
    """main関数のテスト"""
    # 先にインポートしておく
    from scripts.create_pr import main

    # モックの設定
    mock_creator = mocker.MagicMock()
    mock_creator.run.return_value = 0
    mocker.patch("scripts.create_pr.PullRequestCreator", return_value=mock_creator)

    # テスト実行
    result = main()

    # 検証
    mock_creator.run.assert_called_once()
    assert result == 0

    # 異常系のテスト
    mock_creator.run.return_value = 1
    result = main()
    assert result == 1
