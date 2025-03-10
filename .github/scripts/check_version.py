#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
バージョンチェックスクリプト
package.jsonとpackage-lock.jsonのバージョン整合性チェックと、既存タグとの比較を行う
"""

import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple, cast

import git
from packaging import version

# ロギング設定
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)

# 安全なコマンドのリスト
SAFE_COMMANDS = ["git", "npm", "jq"]


class VersionChecker:
    """バージョンチェッカークラス"""

    def __init__(self: "VersionChecker") -> None:
        """初期化メソッド。

        Attributes:
            repo: Gitリポジトリのインスタンス。
            _npm_new_version: 新しいバージョンの情報。
        """
        self._git_repo: Optional[git.Repo] = None
        self._npm_new_version: Optional[str] = None
        self._npm_lock_version: Optional[str] = None
        self._git_old_version: Optional[str] = None

    @property
    def npm_new_version(self: "VersionChecker") -> Optional[str]:
        """新しいバージョンを取得するプロパティ。

        Returns:
            新しいバージョンの文字列。
        """
        return self._npm_new_version

    @npm_new_version.setter
    def npm_new_version(self: "VersionChecker", value: str) -> None:
        """新しいバージョンを設定するプロパティ。

        Args:
            value: 新しいバージョンの文字列。
        """
        self._npm_new_version = value

    @property
    def npm_lock_version(self: "VersionChecker") -> Optional[str]:
        """ロックファイルのバージョンを取得するプロパティ。

        Returns:
            npm_lock_version: ロックファイルのバージョンの文字列。
        """
        return self._npm_lock_version

    @npm_lock_version.setter
    def npm_lock_version(self: "VersionChecker", value: str) -> None:
        """ロックファイルのバージョンを設定するプロパティ。

        Args:
            value: ロックファイルのバージョンの文字列。
        """
        self._npm_lock_version = value

    @property
    def git_old_version(self: "VersionChecker") -> Optional[str]:
        """前のバージョンを取得するプロパティ。

        Returns:
            git_old_version: 前のバージョンの文字列。
        """
        return self._git_old_version

    @git_old_version.setter
    def git_old_version(self: "VersionChecker", value: str) -> None:
        """前のバージョンを設定するプロパティ。

        Args:
            value: 前のバージョンの文字列。
        """
        self._git_old_version = value

    # GitHub Actions用ログコマンド
    def github_notice(self: "VersionChecker", message: str) -> None:
        """GitHub Actionsに通知メッセージを出力。

        Args:
            message: 通知メッセージの文字列。
        """
        print(f"::notice::{message}")

    def github_warning(self: "VersionChecker", message: str) -> None:
        """GitHub Actionsに警告メッセージを出力。

        Args:
            message: 警告メッセージの文字列。
        """
        print(f"::warning::{message}")

    def github_error(self: "VersionChecker", message: str) -> None:
        """GitHub Actionsにエラーメッセージを出力。

        Args:
            message: エラーメッセージの文字列。
        """
        print(f"::error::{message}")

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

    def set_success_output(self: "VersionChecker", npm_new_version: str = "", old_version: str = "") -> None:
        """成功時の出力を設定。

        Args:
            npm_new_version: 新しいバージョンの文字列。
            old_version: 古いバージョンの文字列。
        """
        self.set_github_output("status", "success")
        self.set_github_output("version_changed", "true")
        if npm_new_version:
            self.set_github_output("npm_new_version", npm_new_version)
        if old_version:
            self.set_github_output("old_version", old_version)

    def validate_command(self: "VersionChecker", cmd: List[str]) -> bool:
        # コマンドの先頭部分（実行ファイル名）のみを検証
        executable = cmd[0]
        base_executable = os.path.basename(executable)

        # 許可リストに含まれるコマンドのみ実行を許可
        is_safe = any(base_executable == safe_cmd or base_executable.startswith(f"{safe_cmd}.") for safe_cmd in SAFE_COMMANDS)

        # コマンドの引数にも危険な文字がないか確認
        if is_safe and len(cmd) > 1:
            for arg in cmd[1:]:
                if not isinstance(arg, str):
                    return False
                # シェル特殊文字を含む引数は拒否
                if any(c in arg for c in ["|", "&", ";", "$", ">", "<", "`", "\\"]):
                    return False

        return is_safe

    def get_file_version(self: "VersionChecker", file_path: str) -> Optional[str]:
        """JSONファイルからバージョン情報を取得"""
        try:
            with open(file_path, "r") as f:
                data = json.load(f)
                return cast(Optional[str], data.get("version"))
        except Exception as e:
            self.github_error(f"{file_path}の解析に失敗しました: {e}")
            return None

    def is_semver(self: "VersionChecker", version_str: str) -> bool:
        """文字列がセマンティックバージョニングに従っているか検証"""
        # セマンティックバージョニングの正規表現パターン
        pattern = (
            r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
            r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
            r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
        )
        return bool(re.match(pattern, version_str))

    def get_latest_git_commit_for_file(self: "VersionChecker", repo: git.Repo, file_path: str) -> Optional[git.Commit]:
        """ファイルを変更した最新のコミットを取得。

        Args:
            repo: Gitリポジトリのインスタンス。
            file_path: 対象ファイルのパス。

        Returns:
            最新のコミットオブジェクト、またはコミットが存在しない場合はNone。
        """
        try:
            commits = list(repo.iter_commits(paths=file_path, max_count=1))
            return commits[0] if commits else None
        except Exception as e:
            self.github_warning(f"{file_path}の最新コミット取得に失敗しました: {e}")
            return None

    def get_commit_time(self: "VersionChecker", commit: git.Commit) -> int:
        """コミットのUNIXタイムスタンプを取得。

        Args:
            commit: コミットオブジェクト。

        Returns:
            コミットのUNIXタイムスタンプ。
        """
        return commit.committed_date

    def get_git_old_version(self: "VersionChecker", repo: git.Repo, commit: git.Commit, file_path: str) -> Optional[str]:
        """指定コミットの一つ前のバージョンを取得。

        Args:
            repo: Gitリポジトリのインスタンス。
            commit: 対象コミットオブジェクト。
            file_path: 対象ファイルのパス。

        Returns:
            前のバージョンの文字列、または取得に失敗した場合はNone。
        """
        try:
            parent = commit.parents[0]
            blob = parent.tree / file_path
            content = blob.data_stream.read().decode("utf-8")
            data = json.loads(content)
            return cast(Optional[str], data.get("version"))
        except Exception as e:
            self.github_warning(f"前バージョンの取得に失敗しました: {e}")
            return None

    def get_version_tags(self: "VersionChecker", repo: git.Repo) -> List[str]:
        """リポジトリからセマンティックバージョニングに従ったタグを取得。

        Args:
            repo: Gitリポジトリのインスタンス。

        Returns:
            セマンティックバージョニングに従ったタグのリスト。
        """
        # 最新のタグ情報を取得
        try:
            repo.git.fetch(all=True, tags=True)
        except Exception as e:
            self.github_warning(f"タグ取得に失敗しました: {e}")

        version_tags: List[str] = []
        for tag in repo.tags:
            tag_name = str(tag.name)
            # vプレフィックスを削除
            tag_version = tag_name[1:] if tag_name.startswith("v") else tag_name
            if self.is_semver(tag_version):
                version_tags.append(tag_name)

        # タグをバージョン順にソート
        return sorted(version_tags, key=lambda t: version.parse(t[1:] if t.startswith("v") else t))

    def compare_versions(self: "VersionChecker", npm_new_version: str, old_version: str) -> int:
        """セマンティックバージョンの比較。

        Args:
            npm_new_version: 新しいバージョンの文字列。
            old_version: 古いバージョンの文字列。

        Returns:
            npm_new_version > old_version なら1、npm_new_version == old_version なら0、npm_new_version < old_version なら-1。
        """
        ver_new = version.parse(npm_new_version)
        ver_old = version.parse(old_version)
        if ver_new > ver_old:
            return 1
        elif ver_new < ver_old:
            return -1
        else:
            return 0

    def initialize_git_repo(self: "VersionChecker") -> bool:
        """リポジトリを初期化。

        Returns:
            初期化が成功した場合はTrue、失敗した場合はFalse。
        """
        try:
            self._git_repo = git.Repo(".")
            return True
        except Exception as e:
            self.github_error(f"リポジトリの初期化に失敗しました: {e}")
            return False

    def read_npm_versions(self: "VersionChecker") -> bool:
        """npmファイルの存在確認とバージョンの取得と検証。

        Returns:
            npmファイルが存在し、バージョンが正常であればTrueと新しいバージョン、ロックファイルのバージョン。
            失敗した場合はFalseとNone。
        """
        package_json_path = "package.json"
        package_lock_path = "package-lock.json"

        # npmファイルの存在確認
        if not Path(package_json_path).exists():
            self.github_error(f"{package_json_path} ファイルが見つかりません")
            self.set_fail_output("package_missing")
            return False

        if not Path(package_lock_path).exists():
            self.github_error(f"{package_lock_path} ファイルが見つかりません")
            self.set_fail_output("lockfile_missing")
            return False

        # 現在のバージョン取得
        npm_new_version = self._npm_new_version = self.get_file_version(package_json_path)
        if not npm_new_version:
            self.github_error("現在のバージョンの取得に失敗しました")
            self.set_fail_output("npm_new_version_error")
            return False

        # package-lock.jsonのバージョン取得
        npm_lock_version = self._npm_lock_version = self.get_file_version(package_lock_path)
        if not npm_lock_version:
            self.github_error("package-lock.json のバージョン取得に失敗しました")
            self.set_fail_output("npm_lock_version_error")
            return False

        # バージョン形式の検証
        if not self.is_semver(npm_new_version):
            self.github_warning(f"バージョン形式が正しくありません: {npm_new_version}")

        # バージョン整合性チェック
        if npm_new_version != npm_lock_version:
            self.github_error(
                f"package.json ({npm_new_version}) は" f"package-lock.json ({npm_lock_version}) のバージョンと一致していません"
            )
            self.github_error("package-lock.json の更新が必要です。'npm install' または 'npm ci' を実行してください")
            self.set_fail_output("version_mismatch")
            return False

        return True

    def read_npm_package_changes(self: "VersionChecker") -> Tuple[bool, Optional[git.Commit]]:
        """package.jsonの変更確認。

        Returns:
            変更があった場合はTrueと最新のコミット、変更がなかった場合はFalseとNone。
        """
        if self._git_repo is None:
            self.github_error("リポジトリが初期化されていません")
            self.set_fail_output("repo_not_initialized")
            return False, None

        package_json_path = "package.json"
        pkg_commit = self.get_latest_git_commit_for_file(self._git_repo, package_json_path)
        if not pkg_commit:
            self.github_notice("package.json の変更が見つかりません")
            self.set_fail_output("no_package_change")
            return False, None

        return True, pkg_commit

    def compare_npm_and_git_version(self: "VersionChecker", pkg_commit: git.Commit) -> bool:
        """前のバージョンを確認。

        Args:
            pkg_commit: 対象のコミットオブジェクト。

        Returns:
            バージョンが正常であればTrueと前のバージョン、失敗した場合はFalseとNone。
        """
        package_json_path = "package.json"
        npm_new_version = self._npm_new_version

        if self._git_repo is None:
            self.github_error("リポジトリが初期化されていません")
            self.set_fail_output("repo_not_initialized")
            return False

        # 前のバージョン取得
        git_old_version = self._git_old_version = self.get_git_old_version(self._git_repo, pkg_commit, package_json_path)
        if not git_old_version:
            self.github_notice("前のバージョンが見つかりません")
            self.set_fail_output("no_git_old_version")
            return False

        if npm_new_version is None:
            self.github_error("現在のバージョンの取得に失敗しました")
            self.set_fail_output("npm_new_version_error")
            return False

        # バージョン変更があるか確認
        if npm_new_version == git_old_version:
            self.github_notice(f"バージョンに変更がありません: {npm_new_version}")
            self.set_fail_output("no_version_change")
            return False

        # バージョンが増加しているか確認
        if self.compare_versions(npm_new_version, git_old_version) <= 0:
            self.github_error(f"新しいバージョン ({npm_new_version}) は前のバージョン ({git_old_version}) 以下です")
            self.set_fail_output("version_not_incremented")
            return False

        return True

    def check_git_version_tags(self: "VersionChecker", repo: git.Repo, npm_new_version: str) -> bool:
        """バージョンタグの確認。

        Args:
            npm_new_version: 新しいバージョンの文字列。

        Returns:
            バージョンタグが正常であればTrue、そうでなければFalse。
        """

        # バージョンタグ取得
        tags = self.get_version_tags(repo)
        if tags:
            # 最新のバージョンタグと比較
            latest_tag = tags[-1]
            latest_version = latest_tag[1:] if latest_tag.startswith("v") else latest_tag

            if self.is_semver(latest_version) and self.compare_versions(npm_new_version, latest_version) <= 0:
                self.github_error(f"新しいバージョン ({npm_new_version}) は最新タグ ({latest_version}) 以下です")
                self.set_fail_output("version_not_incremented_from_tag")
                return False

        return True

    def run(self: "VersionChecker") -> int:
        """メイン処理を実行。

        Returns:
            処理が成功した場合は0、失敗した場合は1。
        """
        try:
            # リポジトリ初期化
            if not self.initialize_git_repo():
                return 1

            # npmファイルの存在確認とバージョン検証
            if not self.read_npm_versions():
                return 1

            # package.jsonの変更確認
            has_changes, pkg_commit = self.read_npm_package_changes()
            if not has_changes or pkg_commit is None:
                return 0

            # 前のバージョン確認
            if not self.compare_npm_and_git_version(pkg_commit):
                return 1

            if self._npm_new_version is None:
                self.github_error("現在のバージョンの取得に失敗しました")
                self.set_fail_output("npm_new_version_error")
                return 1

            if self._git_old_version is None:
                self.github_error("前のバージョンの取得に失敗しました")
                self.set_fail_output("git_old_version_error")
                return 1

            if self._npm_lock_version is None:
                self.github_error("package-lock.json のバージョン取得に失敗しました")
                self.set_fail_output("npm_lock_version_error")
                return 1

            # バージョンタグ確認
            if not self.check_git_version_tags(self._git_repo, self._npm_new_version):
                return 1

            # すべてのチェックが成功したら
            self.github_notice(f"バージョンが {self._git_old_version} から {self._npm_new_version} に更新されました")
            self.set_success_output(self._npm_new_version, self._git_old_version)
            return 0

        except Exception as e:
            self.github_error(f"予期せぬエラーが発生しました: {e}")
            self.set_fail_output("unexpected_error")
            return 1


def main() -> int:
    """メイン関数"""
    checker = VersionChecker()
    return checker.run()


if __name__ == "__main__":
    sys.exit(main())
