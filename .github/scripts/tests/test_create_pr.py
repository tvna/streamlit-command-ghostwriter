#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
create_pr.pyのユニットテスト
"""

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

# テスト対象モジュールのパスを追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from create_pr import PullRequestCreator  # noqa: E402


class TestPullRequestCreator(unittest.TestCase):
    """PullRequestCreatorクラスのテスト"""

    def setUp(self: "TestPullRequestCreator") -> None:
        """テスト環境のセットアップ"""
        self.creator = PullRequestCreator()
        # 標準出力をキャプチャするためのパッチャー
        self.stdout_patcher = mock.patch("sys.stdout")
        self.mock_stdout = self.stdout_patcher.start()

    def tearDown(self: "TestPullRequestCreator") -> None:
        """テスト後のクリーンアップ"""
        self.stdout_patcher.stop()

    @mock.patch("builtins.print")
    def test_github_notice(self: "TestPullRequestCreator", mock_print: mock.MagicMock) -> None:
        """github_noticeメソッドのテスト"""
        test_message = "テスト通知"
        self.creator.github_notice(test_message)
        mock_print.assert_called_with(f"::notice::{test_message}")

    @mock.patch("builtins.print")
    def test_github_warning(self: "TestPullRequestCreator", mock_print: mock.MagicMock) -> None:
        """github_warningメソッドのテスト"""
        test_message = "テスト警告"
        self.creator.github_warning(test_message)
        mock_print.assert_called_with(f"::warning::{test_message}")

    @mock.patch("builtins.print")
    def test_github_error(self: "TestPullRequestCreator", mock_print: mock.MagicMock) -> None:
        """github_errorメソッドのテスト"""
        test_message = "テストエラー"
        self.creator.github_error(test_message)
        mock_print.assert_called_with(f"::error::{test_message}")

    @mock.patch.dict(os.environ, {"GITHUB_OUTPUT": "github_output.txt"})
    @mock.patch("builtins.open", new_callable=mock.mock_open)
    def test_set_github_output(self: "TestPullRequestCreator", mock_open: mock.MagicMock) -> None:
        """set_github_outputメソッドのテスト"""
        self.creator.set_github_output("test_name", "test_value")
        mock_open.assert_called_with("github_output.txt", "a")
        mock_open().write.assert_called_with("test_name=test_value\n")

    @mock.patch.dict(os.environ, {})
    @mock.patch("logging.Logger.warning")
    def test_set_github_output_no_env(self: "TestPullRequestCreator", mock_warning: mock.MagicMock) -> None:
        """GITHUB_OUTPUT環境変数がない場合のset_github_outputメソッドのテスト"""
        self.creator.set_github_output("test_name", "test_value")
        mock_warning.assert_called_with("GITHUB_OUTPUT環境変数が設定されていません")

    def test_validate_command_safe(self: "TestPullRequestCreator") -> None:
        """安全なコマンドのvalidate_commandメソッドのテスト"""
        # 安全なコマンド
        assert self.creator.validate_command(["gh", "pr", "create"])
        assert self.creator.validate_command(["gh", "auth", "status"])

    def test_validate_command_unsafe(self: "TestPullRequestCreator") -> None:
        """安全でないコマンドのvalidate_commandメソッドのテスト"""
        # 安全でないコマンド
        assert not self.creator.validate_command(["rm", "-rf", "/"])
        assert not self.creator.validate_command(["gh", "pr", "create", "|", "grep"])
        assert not self.creator.validate_command(["gh", "auth", "status", "&", "rm"])

    @mock.patch.dict(os.environ, {"GH_TOKEN": "dummy_token"})
    @mock.patch("subprocess.run")
    @mock.patch.object(PullRequestCreator, "validate_command", return_value=True)
    def test_run_gh_cmd_success(self: "TestPullRequestCreator", mock_validate: mock.MagicMock, mock_run: mock.MagicMock) -> None:
        """run_gh_cmdメソッドの成功テスト"""
        mock_run.return_value.returncode = 0
        result = self.creator.run_gh_cmd(["pr", "create"])
        assert result
        mock_validate.assert_called_once()
        mock_run.assert_called_once()

    @mock.patch.dict(os.environ, {})
    @mock.patch.object(PullRequestCreator, "github_error")
    def test_run_gh_cmd_no_token(self: "TestPullRequestCreator", mock_error: mock.MagicMock) -> None:
        """GH_TOKENがない場合のrun_gh_cmdメソッドのテスト"""
        result = self.creator.run_gh_cmd(["pr", "create"])
        assert not result
        mock_error.assert_called_once_with("GH_TOKEN環境変数が設定されていません")

    @mock.patch.dict(os.environ, {"GH_TOKEN": "dummy_token"})
    @mock.patch.object(PullRequestCreator, "validate_command", return_value=False)
    @mock.patch.object(PullRequestCreator, "github_error")
    def test_run_gh_cmd_invalid(self: "TestPullRequestCreator", mock_error: mock.MagicMock, mock_validate: mock.MagicMock) -> None:
        """無効なコマンドでのrun_gh_cmdメソッドのテスト"""
        result = self.creator.run_gh_cmd(["rm", "-rf", "/"])
        assert not result
        mock_validate.assert_called_once()
        mock_error.assert_called_once()

    @mock.patch.dict(os.environ, {"GH_TOKEN": "dummy_token"})
    @mock.patch("subprocess.run")
    @mock.patch.object(PullRequestCreator, "validate_command", return_value=True)
    def test_run_gh_cmd_failure(self: "TestPullRequestCreator", mock_validate: mock.MagicMock, mock_run: mock.MagicMock) -> None:
        """実行失敗時のrun_gh_cmdメソッドのテスト"""
        mock_run.return_value.returncode = 1
        result = self.creator.run_gh_cmd(["pr", "create"])
        assert not result
        mock_validate.assert_called_once()
        mock_run.assert_called_once()

    @mock.patch("git.Repo")
    def test_get_latest_commit_message_success(self: "TestPullRequestCreator", mock_repo: mock.MagicMock) -> None:
        """get_latest_commit_messageメソッドの成功テスト"""
        # モックの設定
        mock_repo_instance = mock_repo.return_value
        mock_commit = mock.MagicMock()
        mock_commit.message = "Test commit message"
        mock_repo_instance.head.commit = mock_commit

        result = self.creator.get_latest_commit_message()
        assert result == "Test commit message"
        mock_repo.assert_called_once_with(".")

    @mock.patch("git.Repo")
    @mock.patch.object(PullRequestCreator, "github_warning")
    def test_get_latest_commit_message_sensitive(
        self: "TestPullRequestCreator", mock_warning: mock.MagicMock, mock_repo: mock.MagicMock
    ) -> None:
        """機密情報を含むget_latest_commit_messageメソッドのテスト"""
        # モックの設定
        mock_repo_instance = mock_repo.return_value
        mock_commit = mock.MagicMock()
        mock_commit.message = "Add token ghp_abcdef123456"
        mock_repo_instance.head.commit = mock_commit

        result = self.creator.get_latest_commit_message()
        assert result == "Add token ghp_***"
        mock_repo.assert_called_once_with(".")
        mock_warning.assert_called_once()

    @mock.patch("git.Repo", side_effect=Exception("Not a git repository"))
    @mock.patch.object(PullRequestCreator, "github_warning")
    def test_get_latest_commit_message_exception(
        self: "TestPullRequestCreator", mock_warning: mock.MagicMock, mock_repo: mock.MagicMock
    ) -> None:
        """例外発生時のget_latest_commit_messageメソッドのテスト"""
        result = self.creator.get_latest_commit_message()
        assert result == "Unable to fetch commit message"
        mock_repo.assert_called_once_with(".")
        mock_warning.assert_called_once()

    @mock.patch("git.Repo")
    def test_get_commit_titles_success(self: "TestPullRequestCreator", mock_repo: mock.MagicMock) -> None:
        """get_commit_titlesメソッドの成功テスト"""
        # モックの設定
        mock_repo_instance = mock_repo.return_value
        mock_commit1 = mock.MagicMock()
        mock_commit1.message = "First commit\nDetails here"
        mock_commit2 = mock.MagicMock()
        mock_commit2.message = "Second commit\nMore details"
        mock_repo_instance.iter_commits.return_value = [mock_commit1, mock_commit2]

        result = self.creator.get_commit_titles()
        assert result == ["- First commit", "- Second commit"]
        mock_repo.assert_called_once_with(".")
        mock_repo_instance.git.fetch.assert_called_once_with("origin", "main:main")
        mock_repo_instance.iter_commits.assert_called_once_with("main..develop", max_count=10)

    @mock.patch("git.Repo")
    @mock.patch.object(PullRequestCreator, "github_warning")
    def test_get_commit_titles_fetch_exception(
        self: "TestPullRequestCreator", mock_warning: mock.MagicMock, mock_repo: mock.MagicMock
    ) -> None:
        """フェッチ例外時のget_commit_titlesメソッドのテスト"""
        # モックの設定
        mock_repo_instance = mock_repo.return_value
        mock_repo_instance.git.fetch.side_effect = Exception("Fetch failed")

        result = self.creator.get_commit_titles()
        assert result == ["Unable to fetch commit titles"]
        mock_repo.assert_called_once_with(".")
        mock_repo_instance.git.fetch.assert_called_once_with("origin", "main:main")
        mock_warning.assert_called_once()

    @mock.patch("git.Repo", side_effect=Exception("Git error"))
    @mock.patch.object(PullRequestCreator, "github_warning")
    def test_get_commit_titles_git_exception(
        self: "TestPullRequestCreator", mock_warning: mock.MagicMock, mock_repo: mock.MagicMock
    ) -> None:
        """Git例外時のget_commit_titlesメソッドのテスト"""
        result = self.creator.get_commit_titles()
        assert result == ["Unable to fetch commit titles"]
        mock_repo.assert_called_once_with(".")
        mock_warning.assert_called_once()

    @mock.patch.dict(os.environ, {"GH_TOKEN": "dummy_token"})
    @mock.patch.object(PullRequestCreator, "run_gh_cmd", return_value=True)
    def test_create_pr_success(self: "TestPullRequestCreator", mock_run_gh_cmd: mock.MagicMock) -> None:
        """create_prメソッドの成功テスト"""
        result = self.creator.create_pr("Test PR", "PR body", ["bug", "enhancement"])
        assert result
        expected_args = [
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
        ]
        mock_run_gh_cmd.assert_called_once_with(expected_args)

    @mock.patch.dict(os.environ, {"GH_TOKEN": "dummy_token"})
    @mock.patch.object(PullRequestCreator, "run_gh_cmd", return_value=True)
    def test_create_pr_no_labels(self: "TestPullRequestCreator", mock_run_gh_cmd: mock.MagicMock) -> None:
        """ラベルなしのcreate_prメソッドのテスト"""
        result = self.creator.create_pr("Test PR", "PR body", [])
        assert result
        expected_args = ["pr", "create", "--base", "main", "--head", "develop", "--title", "Test PR", "--body", "PR body"]
        mock_run_gh_cmd.assert_called_once_with(expected_args)

    @mock.patch.dict(os.environ, {"NEW_VERSION": "1.0.0", "OLD_VERSION": "0.9.0"})
    def test_get_version_info_success(self: "TestPullRequestCreator") -> None:
        """get_version_infoメソッドの成功テスト"""
        result = self.creator.get_version_info()
        assert result
        assert self.creator.new_version == "1.0.0"
        assert self.creator.old_version == "0.9.0"

    @mock.patch.dict(os.environ, {"NEW_VERSION": "", "OLD_VERSION": "0.9.0"})
    @mock.patch.object(PullRequestCreator, "github_error")
    def test_get_version_info_missing_new(self: "TestPullRequestCreator", mock_error: mock.MagicMock) -> None:
        """新バージョンがない場合のget_version_infoメソッドのテスト"""
        result = self.creator.get_version_info()
        assert not result
        mock_error.assert_called_once()

    @mock.patch.dict(os.environ, {"NEW_VERSION": "1.0.0", "OLD_VERSION": ""})
    @mock.patch.object(PullRequestCreator, "github_error")
    def test_get_version_info_missing_old(self: "TestPullRequestCreator", mock_error: mock.MagicMock) -> None:
        """旧バージョンがない場合のget_version_infoメソッドのテスト"""
        result = self.creator.get_version_info()
        assert not result
        mock_error.assert_called_once()

    @mock.patch.object(PullRequestCreator, "get_latest_commit_message", return_value="Test commit")
    @mock.patch.object(PullRequestCreator, "get_commit_titles", return_value=["- Commit 1", "- Commit 2"])
    def test_prepare_pr_content(self: "TestPullRequestCreator", mock_titles: mock.MagicMock, mock_message: mock.MagicMock) -> None:
        """prepare_pr_contentメソッドのテスト"""
        self.creator.new_version = "1.0.0"
        self.creator.old_version = "0.9.0"

        title, body, labels = self.creator.prepare_pr_content()

        assert title == "Release v1.0.0"
        assert "develop から main へのバージョン 1.0.0 の自動 PR" in body
        assert "v0.9.0 から v1.0.0 に更新された" in body
        assert "Test commit" in body
        assert "- Commit 1" in body
        assert "- Commit 2" in body
        assert labels == ["automated-pr", "release"]
        mock_message.assert_called_once()
        mock_titles.assert_called_once_with(50)

    @mock.patch.dict(os.environ, {"NEW_VERSION": "1.0.0", "OLD_VERSION": "0.9.0"})
    @mock.patch.object(PullRequestCreator, "github_notice")
    @mock.patch.object(PullRequestCreator, "get_version_info", return_value=True)
    @mock.patch.object(PullRequestCreator, "prepare_pr_content", return_value=("Test Title", "Test Body", ["test-label"]))
    @mock.patch.object(PullRequestCreator, "create_pr", return_value=True)
    def test_run_success(
        self: "TestPullRequestCreator",
        mock_create_pr: mock.MagicMock,
        mock_prepare: mock.MagicMock,
        mock_get_version: mock.MagicMock,
        mock_notice: mock.MagicMock,
    ) -> None:
        """runメソッドの成功テスト"""
        result = self.creator.run()
        assert result == 0
        mock_notice.assert_any_call("PRの作成準備中...")
        mock_get_version.assert_called_once()
        mock_prepare.assert_called_once()
        mock_create_pr.assert_called_once_with("Test Title", "Test Body", ["test-label"])
        mock_notice.assert_any_call("PRを作成中...")
        mock_notice.assert_any_call("PRが作成されました")

    @mock.patch.dict(os.environ, {"NEW_VERSION": "", "OLD_VERSION": ""})
    @mock.patch.object(PullRequestCreator, "github_notice")
    @mock.patch.object(PullRequestCreator, "get_version_info", return_value=False)
    def test_run_version_error(self: "TestPullRequestCreator", mock_get_version: mock.MagicMock, mock_notice: mock.MagicMock) -> None:
        """バージョン情報エラー時のrunメソッドのテスト"""
        result = self.creator.run()
        assert result == 1
        mock_notice.assert_called_once_with("PRの作成準備中...")
        mock_get_version.assert_called_once()

    @mock.patch.dict(os.environ, {"NEW_VERSION": "1.0.0", "OLD_VERSION": "0.9.0"})
    @mock.patch.object(PullRequestCreator, "github_notice")
    @mock.patch.object(PullRequestCreator, "get_version_info", return_value=True)
    @mock.patch.object(PullRequestCreator, "prepare_pr_content", return_value=("Test Title", "Test Body", ["test-label"]))
    @mock.patch.object(PullRequestCreator, "create_pr", return_value=False)
    @mock.patch.object(PullRequestCreator, "github_error")
    def test_run_pr_creation_error(
        self: "TestPullRequestCreator",
        mock_error: mock.MagicMock,
        mock_create_pr: mock.MagicMock,
        mock_prepare: mock.MagicMock,
        mock_get_version: mock.MagicMock,
        mock_notice: mock.MagicMock,
    ) -> None:
        """PR作成エラー時のrunメソッドのテスト"""
        result = self.creator.run()
        assert result == 1
        mock_create_pr.assert_called_once_with("Test Title", "Test Body", ["test-label"])
        mock_error.assert_called_once_with("PRの作成に失敗しました")

    @mock.patch.dict(os.environ, {"NEW_VERSION": "1.0.0", "OLD_VERSION": "0.9.0"})
    @mock.patch.object(PullRequestCreator, "github_notice", side_effect=Exception("Unexpected error"))
    @mock.patch.object(PullRequestCreator, "github_error")
    def test_run_exception(self: "TestPullRequestCreator", mock_error: mock.MagicMock, mock_notice: mock.MagicMock) -> None:
        """例外発生時のrunメソッドのテスト"""
        result = self.creator.run()
        assert result == 1
        mock_notice.assert_called_once_with("PRの作成準備中...")
        mock_error.assert_called_once()


if __name__ == "__main__":
    unittest.main()
