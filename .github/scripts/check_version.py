#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
バージョンチェックスクリプト
mainブランチとdevelopブランチのpackage.jsonのバージョンを比較し、
developブランチのバージョンが上がっていた場合のみ、正常とする
また、developブランチのpackage.jsonとpackage-lock.jsonのバージョンが一致しているかも確認する
"""

import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Optional, Tuple, cast

import git
from git.exc import GitCommandNotFound, InvalidGitRepositoryError
from packaging import version

# ロギング設定
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)

# 安全なコマンドのリスト
SAFE_COMMANDS = ["git", "npm", "jq"]


class InvalidReadPackageError(Exception):
    """package.jsonの読み込みに失敗しました"""

    pass


class VersionChecker:
    """バージョンチェッカークラス"""

    def __init__(self: "VersionChecker") -> None:
        """初期化メソッド。

        Attributes:
            repo: Gitリポジトリのインスタンス。
        """
        self._git_repo: git.Repo = git.Repo(".")

    def set_github_output(self: "VersionChecker", name: str, value: str) -> None:
        """GitHub Actionsの出力変数を設定。

        Args:
            name: 出力変数の名前。
            value: 出力変数の値。
        """
        github_output = os.environ.get("GITHUB_OUTPUT")
        if github_output:
            with open(github_output, "a") as f:
                f.write(f"{name}={value}\n")
        else:
            logger.warning("GITHUB_OUTPUT環境変数が設定されていません")

    def set_fail_output(self: "VersionChecker", reason: str, **kwargs: str) -> None:
        """失敗時の出力を設定。

        Args:
            reason: 失敗の理由。
            **kwargs: その他の出力変数。
        """
        self.set_github_output("status", "failure")
        self.set_github_output("message", reason)
        self.set_github_output("version_changed", "false")
        self.set_github_output("reason", reason)
        for key, value in kwargs.items():
            self.set_github_output(key, value)

    def is_semver(self: "VersionChecker", version_str: str) -> bool:
        """文字列がセマンティックバージョニングに従っているか検証"""
        # セマンティックバージョニングの正規表現パターン
        pattern = (
            r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
            r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
            r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
        )
        return bool(re.match(pattern, version_str))

    def get_version_from_branch(self: "VersionChecker", branch_name: str, file_path: str = "package.json") -> Optional[str]:
        """指定ブランチの指定ファイルからバージョンを取得。

        Args:
            branch_name: ブランチ名。
            file_path: ファイルパス(デフォルトはpackage.json)。

        Returns:
            バージョン文字列、または取得に失敗した場合はNone。
        """
        try:
            repo = self._git_repo
            # リモートブランチの最新情報を取得
            repo.git.fetch("origin", branch_name)
            # ブランチの最新コミットを取得
            commit = repo.commit(f"origin/{branch_name}")
            # 指定ファイルの内容を取得
            try:
                blob = commit.tree / file_path
                content = blob.data_stream.read().decode("utf-8")
                version_str = cast(Optional[str], json.loads(content).get("version"))

                if version_str is None:
                    print(f"::error::{branch_name}ブランチの{file_path}にバージョンが見つかりません")
                    return None

                return version_str
            except KeyError:
                print(f"::error::{branch_name}ブランチに{file_path}が見つかりません")
                return None

        except Exception as e:
            print(f"::error::{branch_name}ブランチから{file_path}のバージョン取得に失敗しました: {e}")
            return None

    def compare_versions(self: "VersionChecker", new_version: str, old_version: str) -> int:
        """セマンティックバージョンの比較。

        Args:
            new_version: 新しいバージョンの文字列。
            old_version: 古いバージョンの文字列。

        Returns:
            new_version > old_version なら1、new_version == old_version なら0、new_version < old_version なら-1。
        """
        ver_new = version.parse(new_version)
        ver_old = version.parse(old_version)
        if ver_new > ver_old:
            return 1
        elif ver_new < ver_old:
            return -1
        else:
            return 0

    def check_package_json_exists(self: "VersionChecker") -> bool:
        """カレントディレクトリにpackage.jsonが存在するか確認。

        Returns:
            package.jsonが存在すればTrue、そうでなければFalse。
        """
        package_json_path = "package.json"
        if not Path(package_json_path).exists():
            print(f"::error::{package_json_path} ファイルが見つかりません")
            self.set_fail_output("package_missing")
            return False
        return True

    def check_develop_package_versions_match(self: "VersionChecker") -> Tuple[bool, Optional[str], Optional[str]]:
        """developブランチのpackage.jsonとpackage-lock.jsonのバージョンが一致しているか確認。

        Returns:
            一致していればTrue、バージョン、バージョン、一致していなければFalse、バージョン、バージョン。
            エラーの場合はFalse、None、None。
        """
        # package.jsonのバージョン取得
        package_json_version = self.get_version_from_branch("develop", "package.json")
        if package_json_version is None:
            self.set_fail_output("develop_package_json_version_error")
            return False, None, None

        # package-lock.jsonのバージョン取得
        package_lock_version = self.get_version_from_branch("develop", "package-lock.json")
        if package_lock_version is None:
            self.set_fail_output("develop_package_lock_version_error")
            return False, None, None

        # バージョン形式の検証
        if not self.is_semver(package_json_version):
            print(f"::warning::developブランチのpackage.jsonのバージョン形式が正しくありません: {package_json_version}")

        # バージョン整合性チェック
        if package_json_version != package_lock_version:
            print(
                f"::error::developブランチのpackage.json「{package_json_version}」はpackage-lock.json「{package_lock_version}」のバージョンと一致していません"
            )
            print("::error::package-lock.json の更新が必要です。'npm install' または 'npm ci' を実行してください")
            self.set_fail_output("develop_version_mismatch")
            return False, package_json_version, package_lock_version

        return True, package_json_version, package_lock_version

    def run(self: "VersionChecker") -> int:
        """メイン処理を実行。

        Returns:
            処理が成功した場合は0、失敗した場合は1。
        """
        try:
            # package.jsonの存在確認
            if not self.check_package_json_exists():
                return 1

            # developブランチのpackage.jsonとpackage-lock.jsonのバージョン整合性チェック
            is_valid, develop_package_version, develop_lock_version = self.check_develop_package_versions_match()
            if not is_valid or develop_package_version is None:
                return 0

            # mainブランチのバージョン取得
            main_version = self.get_version_from_branch("main")
            if main_version is None:
                self.set_fail_output("main_version_error")
                return 0

            # バージョン形式の検証
            if not self.is_semver(main_version):
                print(f"::warning::mainブランチのバージョン形式が正しくありません: {main_version}")

            # バージョン比較
            if self.compare_versions(develop_package_version, main_version) <= 0:
                print(
                    f"::error::developブランチのバージョン「{develop_package_version}」がmainブランチのバージョン「{main_version}」以下です"
                )
                self.set_fail_output("version_not_incremented")
                return 0

            # すべてのチェックが成功したら
            print(
                f"::notice::developブランチのバージョン「{develop_package_version}」が"
                + f"mainブランチのバージョン「{main_version}」より大きいことを確認しました"
            )
            self.set_github_output("status", "success")
            self.set_github_output("version_changed", "true")
            self.set_github_output("develop_version", develop_package_version)
            self.set_github_output("main_version", main_version)
            return 0

        except GitCommandNotFound:
            print("::error::gitコマンドが見つかりません")
            self.set_fail_output("git_command_not_found")
        except InvalidGitRepositoryError:
            print("::error::gitリポジトリが不正です")
            self.set_fail_output("repo_not_initialized")
        except Exception as e:
            print(f"::error::予期せぬエラーが発生しました: {e}")
            self.set_fail_output("unexpected_error")
        return 1


def main() -> int:
    """メイン関数"""
    checker = VersionChecker()
    return checker.run()


if __name__ == "__main__":
    sys.exit(main())
