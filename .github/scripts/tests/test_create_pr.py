#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
create_pr.pyのユニットテスト
"""

import os
import sys
from pathlib import Path
from typing import Optional

import pytest
from pytest_mock import MockerFixture

# テスト対象モジュールのパスを追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from create_pr import PullRequestCreator  # noqa: E402


@pytest.fixture  # noqa: PT001
def creator() -> PullRequestCreator:
    """PullRequestCreatorのインスタンスを提供するフィクスチャ"""
    creator_instance = PullRequestCreator()
    return creator_instance


@pytest.mark.parametrize(
    ("method", "test_message", "expected_output"),
    [
        ("github_notice", "テスト通知", "::notice::テスト通知\n"),
        ("github_warning", "テスト警告", "::warning::テスト警告\n"),
        ("github_error", "テストエラー", "::error::テストエラー\n"),
    ],
)
def test_github_methods(
    creator: PullRequestCreator, method: str, test_message: str, expected_output: str, capsys: pytest.CaptureFixture
) -> None:
    """githubメソッドのテスト"""
    getattr(creator, method)(test_message)  # メソッドを動的に呼び出す

    captured = capsys.readouterr()
    assert captured.out == expected_output


@pytest.mark.skip(reason="GitHub Actions上でのみ失敗してしまうテスト")
@pytest.mark.parametrize(
    ("env_key", "env_value", "expected_path_call_count", "expected_output"),
    [
        pytest.param("GITHUB_OUTPUT", "github_output.txt", 1, ""),
        pytest.param("GITHUB_OUTPUT", None, 0, "GITHUB_OUTPUT環境変数が設定されていません\n"),
        pytest.param(None, None, 0, "GITHUB_OUTPUT環境変数が設定されていません\n"),
    ],
)
def test_set_github_output(
    env_key: Optional[str],
    env_value: Optional[str],
    expected_path_call_count: int,
    expected_output: str,
    creator: PullRequestCreator,
    capsys: pytest.CaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
) -> None:
    """set_github_outputメソッドのテスト"""

    if env_key is not None and env_value is not None:
        mocker.patch.dict(os.environ, {env_key: env_value})
    else:
        mocker.patch.dict(os.environ, {})

    if env_key is None:
        mock_path = mocker.patch.object(os.path, "isfile", return_value=False)
    else:
        mock_path = mocker.patch.object(os.path, "isfile", return_value=True)

    creator.set_github_output("test_name", "test_value")
    captured = capsys.readouterr()

    assert mock_path.call_count == expected_path_call_count
    assert captured.out == expected_output


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
        (["pr", "create"], "GH_TOKEN", 1, 0, 0, 0),  # 成功ケース
        (["pr", "create"], None, 0, 1, 0, 0),  # GH_TOKEN未設定
        (["rm", "-rf", "/"], "GH_TOKEN", 0, 1, 0, 0),  # 無効なコマンド
        (["pr", "create", "|", "grep"], "GH_TOKEN", 0, 1, 0, 0),  # 危険な文字を含む引数
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


@pytest.mark.parametrize(
    ("sensitive", "exception", "expected_result", "expected_notice_calls", "expected_warning_calls", "expected_error_calls"),
    [
        (False, False, "Test commit message", 0, 0, 0),  # 通常のメッセージ
        (True, False, "Add token ghp_***", 0, 1, 0),  # 機密情報を含むメッセージ
        (False, True, "Unable to fetch commit message", 0, 1, 0),  # 例外発生時
    ],
)
def test_get_latest_commit_message(
    creator: PullRequestCreator,
    mocker: MockerFixture,
    sensitive: bool,
    exception: bool,
    expected_result: str,
    expected_notice_calls: int,
    expected_warning_calls: int,
    expected_error_calls: int,
) -> None:
    """get_latest_commit_messageメソッドのテスト"""
    if exception:
        mock_repo = mocker.patch("git.Repo", side_effect=Exception("Not a git repository"))
    else:
        mock_repo = mocker.patch("git.Repo")

    mock_repo_instance = mock_repo.return_value
    mock_commit = mocker.MagicMock()
    mock_notice = mocker.patch.object(PullRequestCreator, "github_notice")
    mock_warning = mocker.patch.object(PullRequestCreator, "github_warning")
    mock_error = mocker.patch.object(PullRequestCreator, "github_error")

    if sensitive:
        mock_commit.message = "Add token ghp_abcdef123456"
    else:
        mock_commit.message = "Test commit message"

    mock_repo_instance.head.commit = mock_commit

    result = creator.get_latest_commit_message()

    assert result == expected_result

    mock_repo.assert_called_once_with(".")
    if exception:
        assert mock_notice.call_count == expected_notice_calls
        assert mock_warning.call_count == expected_warning_calls
        assert mock_error.call_count == expected_error_calls
        assert mock_repo_instance.call_count == 0
        assert mock_commit.call_count == 0
    else:
        assert mock_notice.call_count == expected_notice_calls
        assert mock_warning.call_count == expected_warning_calls
        assert mock_error.call_count == expected_error_calls
        assert mock_repo_instance.call_count == 0
        assert mock_commit.call_count == 0


@pytest.mark.parametrize(
    ("mock_commit_messages", "expected_result", "fetch_exception"),
    [
        (["First commit\nDetails here", "Second commit\nMore details"], ["- First commit", "- Second commit"], False),
        ([], ["Unable to fetch commit titles"], True),  # Fetch exception case
    ],
)
def test_get_commit_titles(
    creator: PullRequestCreator,
    mocker: MockerFixture,
    mock_commit_messages: list,
    expected_result: list,
    fetch_exception: bool,
) -> None:
    """get_commit_titlesメソッドのテスト"""
    mock_repo = mocker.patch("git.Repo")
    mock_repo_instance = mock_repo.return_value

    if fetch_exception:
        mock_repo_instance.git.fetch.side_effect = Exception("Fetch failed")
    else:
        mock_commit1 = mocker.MagicMock()
        mock_commit1.message = mock_commit_messages[0]
        mock_commit2 = mocker.MagicMock()
        mock_commit2.message = mock_commit_messages[1]
        mock_repo_instance.iter_commits.return_value = [mock_commit1, mock_commit2]

    result = creator.get_commit_titles()
    assert result == expected_result

    mock_repo.assert_called_once_with(".")
    if not fetch_exception:
        mock_repo_instance.git.fetch.assert_called_once_with("origin", "main:main")
        mock_repo_instance.iter_commits.assert_called_once_with("main..develop", max_count=10)
    else:
        mock_repo_instance.git.fetch.assert_called_once_with("origin", "main:main")


@pytest.mark.parametrize(
    ("labels", "expected_args"),
    [
        (
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
        ),
        (
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


@pytest.mark.parametrize(
    ("env_vars", "expected_result", "expected_calls"),
    [
        ({"NEW_VERSION": "1.0.0", "OLD_VERSION": "0.9.0"}, True, 0),  # 成功ケース
        ({"NEW_VERSION": "", "OLD_VERSION": "0.9.0"}, False, 1),  # 新バージョンがない場合
        ({"NEW_VERSION": "1.0.0", "OLD_VERSION": ""}, False, 1),  # 旧バージョンがない場合
    ],
)
def test_get_version_info(
    creator: PullRequestCreator, mocker: MockerFixture, env_vars: dict, expected_result: bool, expected_calls: int
) -> None:
    """get_version_infoメソッドのテスト"""
    mocker.patch.dict(os.environ, env_vars)
    mock_error = mocker.patch.object(PullRequestCreator, "github_error")

    result = creator.get_version_info()
    assert result == expected_result
    assert mock_error.call_count == expected_calls

    if expected_result:
        assert creator.new_version == "1.0.0"
        assert creator.old_version == "0.9.0"
    else:
        if env_vars["NEW_VERSION"] == "":
            assert creator.new_version == ""
            assert creator.old_version == "0.9.0"
        else:
            assert creator.new_version == "1.0.0"
            assert creator.old_version == ""


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
    ("new_version", "old_version", "expected_result", "expected_calls"),
    [
        ("1.0.0", "0.9.0", 0, ["PRの作成準備中...", "PRを作成中...", "PRが作成されました"]),
        ("", "", 1, ["PRの作成準備中..."]),
    ],
)
def test_run(
    creator: PullRequestCreator, mocker: MockerFixture, new_version: str, old_version: str, expected_result: int, expected_calls: list
) -> None:
    """runメソッドの成功およびバージョン情報エラー時のテスト"""
    mocker.patch.dict(os.environ, {"NEW_VERSION": new_version, "OLD_VERSION": old_version})

    if expected_result == 0:
        mocker.patch.object(PullRequestCreator, "github_notice")
        mocker.patch.object(PullRequestCreator, "get_version_info", return_value=True)
        mocker.patch.object(PullRequestCreator, "prepare_pr_content", return_value=("Test Title", "Test Body", ["test-label"]))
        mock_create_pr = mocker.patch.object(PullRequestCreator, "create_pr", return_value=True)

        result = creator.run()
        assert result == expected_result
        mock_create_pr.assert_called_once_with("Test Title", "Test Body", ["test-label"])
    else:
        mocker.patch.object(PullRequestCreator, "github_notice")
        mocker.patch.object(PullRequestCreator, "get_version_info", return_value=False)

        result = creator.run()
        assert result == expected_result
