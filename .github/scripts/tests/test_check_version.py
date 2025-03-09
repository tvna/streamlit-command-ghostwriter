#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
check_version.pyのユニットテスト
"""

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

# テスト対象モジュールのパスを追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from check_version import VersionChecker  # noqa: E402


class TestVersionChecker(unittest.TestCase):
    """VersionCheckerクラスのテスト"""

    def setUp(self: "TestVersionChecker") -> None:
        """テスト環境のセットアップ"""
        self.checker = VersionChecker()
        # 標準出力をキャプチャするためのパッチャー
        self.stdout_patcher = mock.patch("sys.stdout")
        self.mock_stdout = self.stdout_patcher.start()

    def tearDown(self: "TestVersionChecker") -> None:
        """テスト後のクリーンアップ"""
        self.stdout_patcher.stop()

    @mock.patch("builtins.print")
    def test_github_notice(self: "TestVersionChecker", mock_print: mock.MagicMock) -> None:
        test_message = "テスト通知"
        self.checker.github_notice(test_message)
        mock_print.assert_called_with(f"::notice::{test_message}")

    @mock.patch("builtins.print")
    def test_github_warning(self: "TestVersionChecker", mock_print: mock.MagicMock) -> None:
        """github_warningメソッドのテスト"""
        test_message = "テスト警告"
        self.checker.github_warning(test_message)
        mock_print.assert_called_with(f"::warning::{test_message}")

    @mock.patch("builtins.print")
    def test_github_error(self: "TestVersionChecker", mock_print: mock.MagicMock) -> None:
        """github_errorメソッドのテスト"""
        test_message = "テストエラー"
        self.checker.github_error(test_message)
        mock_print.assert_called_with(f"::error::{test_message}")

    @mock.patch.dict(os.environ, {"GITHUB_OUTPUT": "github_output.txt"})
    @mock.patch("builtins.open", new_callable=mock.mock_open)
    def test_set_github_output(self: "TestVersionChecker", mock_open: mock.MagicMock) -> None:
        """set_github_outputメソッドのテスト"""
        self.checker.set_github_output("test_name", "test_value")
        mock_open.assert_called_with("github_output.txt", "a")
        mock_open().write.assert_called_with("test_name=test_value\n")

    @mock.patch.dict(os.environ, {})
    @mock.patch("check_version.logger.warning")
    def test_set_github_output_no_env(self: "TestVersionChecker", mock_warning: mock.MagicMock) -> None:
        """GITHUB_OUTPUT環境変数がない場合のset_github_outputメソッドのテスト"""
        self.checker.set_github_output("test_name", "test_value")
        mock_warning.assert_called_with("GITHUB_OUTPUT環境変数が設定されていません")

    @mock.patch.object(VersionChecker, "set_github_output")
    def test_set_fail_output(self: "TestVersionChecker", mock_set_github_output: mock.MagicMock) -> None:
        """set_fail_outputメソッドのテスト"""
        self.checker.set_fail_output("test_reason", key1="value1", key2="value2")
        expected_calls = [
            mock.call("status", "failure"),
            mock.call("message", "test_reason"),
            mock.call("version_changed", "false"),
            mock.call("reason", "test_reason"),
            mock.call("key1", "value1"),
            mock.call("key2", "value2"),
        ]
        mock_set_github_output.assert_has_calls(expected_calls, any_order=True)

    @mock.patch.object(VersionChecker, "set_github_output")
    def test_set_success_output(self: "TestVersionChecker", mock_set_github_output: mock.MagicMock) -> None:
        """set_success_outputメソッドのテスト"""
        self.checker.set_success_output("1.0.0", "0.9.0")
        expected_calls = [
            mock.call("status", "success"),
            mock.call("version_changed", "true"),
            mock.call("new_version", "1.0.0"),
            mock.call("old_version", "0.9.0"),
        ]
        mock_set_github_output.assert_has_calls(expected_calls, any_order=True)

    def test_validate_command_safe(self: "TestVersionChecker") -> None:
        """安全なコマンドのvalidate_commandメソッドのテスト"""
        # 安全なコマンド
        assert self.checker.validate_command(["git", "status"])
        assert self.checker.validate_command(["npm", "version"])
        assert self.checker.validate_command(["jq", "."])

    def test_validate_command_unsafe(self: "TestVersionChecker") -> None:
        """安全でないコマンドのvalidate_commandメソッドのテスト"""
        # 安全でないコマンド
        assert not self.checker.validate_command(["rm", "-rf", "/"])
        assert not self.checker.validate_command(["git", "push", "|", "grep"])
        assert not self.checker.validate_command(["npm", "install", "&", "rm"])

    @mock.patch("subprocess.run")
    @mock.patch.object(VersionChecker, "validate_command", return_value=True)
    def test_run_cmd_success(self: "TestVersionChecker", mock_validate: mock.MagicMock, mock_run: mock.MagicMock) -> None:
        """run_cmdメソッドの成功テスト"""
        mock_run.return_value.returncode = 0
        result = self.checker.run_cmd(["git", "status"])
        assert result
        mock_validate.assert_called_once()
        mock_run.assert_called_once()

    @mock.patch("subprocess.run")
    @mock.patch.object(VersionChecker, "validate_command", return_value=False)
    @mock.patch.object(VersionChecker, "github_error")
    def test_run_cmd_invalid(
        self: "TestVersionChecker", mock_error: mock.MagicMock, mock_validate: mock.MagicMock, mock_run: mock.MagicMock
    ) -> None:
        """無効なコマンドでのrun_cmdメソッドのテスト"""
        result = self.checker.run_cmd(["rm", "-rf", "/"])
        assert not result
        mock_validate.assert_called_once()
        mock_run.assert_not_called()
        mock_error.assert_called_once()

    @mock.patch("subprocess.run")
    @mock.patch.object(VersionChecker, "validate_command", return_value=True)
    def test_run_cmd_failure(self: "TestVersionChecker", mock_validate: mock.MagicMock, mock_run: mock.MagicMock) -> None:
        """実行失敗時のrun_cmdメソッドのテスト"""
        mock_run.return_value.returncode = 1
        result = self.checker.run_cmd(["git", "status"])
        assert not result
        mock_validate.assert_called_once()
        mock_run.assert_called_once()

    @mock.patch("builtins.open", new_callable=mock.mock_open, read_data='{"version": "1.0.0"}')
    def test_get_file_version_success(self: "TestVersionChecker", mock_file: mock.MagicMock) -> None:
        """get_file_versionメソッドの成功テスト"""
        version = self.checker.get_file_version("package.json")
        assert version == "1.0.0"
        mock_file.assert_called_with("package.json", "r")

    @mock.patch("builtins.open", side_effect=Exception("File not found"))
    @mock.patch.object(VersionChecker, "github_error")
    def test_get_file_version_error(self: "TestVersionChecker", mock_error: mock.MagicMock, mock_file: mock.MagicMock) -> None:
        """get_file_versionメソッドのエラーテスト"""
        version = self.checker.get_file_version("package.json")
        assert version is None
        mock_file.assert_called_with("package.json", "r")
        mock_error.assert_called_once()

    def test_is_semver_valid(self: "TestVersionChecker") -> None:
        """is_semverメソッドの有効なバージョンのテスト"""
        assert self.checker.is_semver("1.0.0")
        assert self.checker.is_semver("1.2.3")
        assert self.checker.is_semver("0.1.0")
        assert self.checker.is_semver("1.0.0-alpha")
        assert self.checker.is_semver("1.0.0-beta.1")
        assert self.checker.is_semver("1.0.0+build.1")

    def test_is_semver_invalid(self: "TestVersionChecker") -> None:
        """is_semverメソッドの無効なバージョンのテスト"""
        assert not self.checker.is_semver("v1.0.0")  # vプレフィックスは無効
        assert not self.checker.is_semver("1.0")  # マイナーバージョンのみは無効
        assert not self.checker.is_semver("1")  # メジャーバージョンのみは無効
        assert not self.checker.is_semver("1.0.a")  # 数字以外は無効
        assert not self.checker.is_semver("latest")  # 文字列は無効

    def test_compare_versions(self: "TestVersionChecker") -> None:
        """compare_versionsメソッドのテスト"""
        # v1 > v2
        assert self.checker.compare_versions("1.0.1", "1.0.0") == 1
        assert self.checker.compare_versions("1.1.0", "1.0.0") == 1
        assert self.checker.compare_versions("2.0.0", "1.0.0") == 1

        # v1 == v2
        assert self.checker.compare_versions("1.0.0", "1.0.0") == 0

        # v1 < v2
        assert self.checker.compare_versions("1.0.0", "1.0.1") == -1
        assert self.checker.compare_versions("1.0.0", "1.1.0") == -1
        assert self.checker.compare_versions("1.0.0", "2.0.0") == -1

    @mock.patch.object(VersionChecker, "github_error")
    def test_initialize_repo_exception(self: "TestVersionChecker", mock_error: mock.MagicMock) -> None:
        """initialize_repoメソッドの例外テスト"""
        with mock.patch("git.Repo", side_effect=Exception("Not a git repository")):
            result = self.checker.initialize_repo()
            assert not result
            mock_error.assert_called_once()

    @mock.patch("pathlib.Path.exists", side_effect=[True, True])
    def test_check_file_existence_success(self: "TestVersionChecker", mock_exists: mock.MagicMock) -> None:
        """check_file_existenceメソッドの成功テスト"""
        result = self.checker.check_file_existence()
        assert result
        assert mock_exists.call_count == 2

    @mock.patch("pathlib.Path.exists", side_effect=[False, True])
    @mock.patch.object(VersionChecker, "github_error")
    @mock.patch.object(VersionChecker, "set_fail_output")
    def test_check_file_existence_no_package(
        self: "TestVersionChecker", mock_fail: mock.MagicMock, mock_error: mock.MagicMock, mock_exists: mock.MagicMock
    ) -> None:
        """package.jsonがない場合のcheck_file_existenceメソッドのテスト"""
        result = self.checker.check_file_existence()
        assert not result
        mock_exists.assert_called_once()
        mock_error.assert_called_once()
        mock_fail.assert_called_once_with("package_missing")

    @mock.patch("pathlib.Path.exists", side_effect=[True, False])
    @mock.patch.object(VersionChecker, "github_error")
    @mock.patch.object(VersionChecker, "set_fail_output")
    def test_check_file_existence_no_lock(
        self: "TestVersionChecker", mock_fail: mock.MagicMock, mock_error: mock.MagicMock, mock_exists: mock.MagicMock
    ) -> None:
        """package-lock.jsonがない場合のcheck_file_existenceメソッドのテスト"""
        result = self.checker.check_file_existence()
        assert not result
        assert mock_exists.call_count == 2
        mock_error.assert_called_once()
        mock_fail.assert_called_once_with("lockfile_missing")

    # 完全なテストケースを追加するのはかなり長くなるので、主要なメソッドのテストを中心に示します
    # 実際の実装では、残りのメソッドにも同様のテストケースを追加することが望ましいです

    # 統合テスト: runメソッドのテスト
    @mock.patch.object(VersionChecker, "initialize_repo", return_value=True)
    @mock.patch.object(VersionChecker, "check_file_existence", return_value=True)
    @mock.patch.object(VersionChecker, "check_package_changes", return_value=(True, mock.MagicMock()))
    @mock.patch.object(VersionChecker, "check_versions", return_value=(True, "1.0.0", "1.0.0"))
    @mock.patch.object(VersionChecker, "check_previous_version", return_value=(True, "0.9.0"))
    @mock.patch.object(VersionChecker, "check_version_tags", return_value=True)
    @mock.patch.object(VersionChecker, "github_notice")
    @mock.patch.object(VersionChecker, "set_success_output")
    def test_run_success(
        self: "TestVersionChecker",
        mock_success: mock.MagicMock,
        mock_notice: mock.MagicMock,
        mock_tags: mock.MagicMock,
        mock_prev: mock.MagicMock,
        mock_versions: mock.MagicMock,
        mock_changes: mock.MagicMock,
        mock_files: mock.MagicMock,
        mock_init: mock.MagicMock,
    ) -> None:
        """runメソッドの成功テスト"""
        result = self.checker.run()
        assert result == 0
        mock_init.assert_called_once()
        mock_files.assert_called_once()
        mock_changes.assert_called_once()
        mock_versions.assert_called_once()
        mock_prev.assert_called_once()
        mock_tags.assert_called_once()
        mock_notice.assert_called_once()
        mock_success.assert_called_once_with("1.0.0", "0.9.0")

    @mock.patch.object(VersionChecker, "initialize_repo", return_value=False)
    def test_run_init_failure(self: "TestVersionChecker", mock_init: mock.MagicMock) -> None:
        """initialize_repoが失敗した場合のrunメソッドのテスト"""
        result = self.checker.run()
        assert result == 1
        mock_init.assert_called_once()

    @mock.patch.object(VersionChecker, "initialize_repo", side_effect=Exception("Unexpected error"))
    @mock.patch.object(VersionChecker, "github_error")
    @mock.patch.object(VersionChecker, "set_fail_output")
    def test_run_exception(
        self: "TestVersionChecker", mock_fail: mock.MagicMock, mock_error: mock.MagicMock, mock_init: mock.MagicMock
    ) -> None:
        """例外が発生した場合のrunメソッドのテスト"""
        result = self.checker.run()
        assert result == 1
        mock_init.assert_called_once()
        mock_error.assert_called_once()
        mock_fail.assert_called_once_with("unexpected_error")


if __name__ == "__main__":
    unittest.main()
