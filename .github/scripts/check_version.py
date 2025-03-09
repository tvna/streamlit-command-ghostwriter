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
import subprocess  # noqa: S404 - セキュリティチェック済みの安全な使用法
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
            _new_version: 新しいバージョンの情報。
        """
        self._git_repo = None
        self._new_version: Optional[str] = None

    @property
    def new_version(self: "VersionChecker") -> Optional[str]:
        """新しいバージョンを取得するプロパティ。

        Returns:
            新しいバージョンの文字列。
        """
        return self._new_version

    @new_version.setter
    def new_version(self: "VersionChecker", value: str) -> None:
        """新しいバージョンを設定するプロパティ。

        Args:
            value: 新しいバージョンの文字列。
        """
        self._new_version = value

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

    def set_success_output(self: "VersionChecker", new_version: str = "", old_version: str = "") -> None:
        """成功時の出力を設定。

        Args:
            new_version: 新しいバージョンの文字列。
            old_version: 古いバージョンの文字列。
        """
        self.set_github_output("status", "success")
        self.set_github_output("version_changed", "true")
        if new_version:
            self.set_github_output("new_version", new_version)
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

    def run_cmd(self: "VersionChecker", cmd: List[str], cwd: Optional[str] = None) -> bool:
        """コマンドを実行して結果を返す"""
        # コマンドの検証
        if not self.validate_command(cmd):
            self.github_error(f"安全でないコマンドが指定されました: {cmd[0]}")
            return False

        try:
            # subprocess.runを使用してより安全に実行
            # S603を無視: 事前にvalidate_commandでコマンドの安全性を確認済み
            result = subprocess.run(  # noqa: S603
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=cwd,
                shell=False,  # シェルインジェクション防止
                check=False,  # エラー時に例外を発生させない
            )
            return result.returncode == 0
        except Exception as e:
            self.github_error(f"コマンド実行中にエラーが発生しました: {e}")
            return False

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

    def get_previous_version(self: "VersionChecker", repo: git.Repo, commit: git.Commit, file_path: str) -> Optional[str]:
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

    def validate_npm_file(self: "VersionChecker") -> bool:
        """npmプロジェクトのファイル存在確認。

        Returns:
            npmプロジェクトに必要なファイル（package.jsonとpackage-lock.json）が存在する場合はTrue、存在しない場合はFalse。
        """
        package_json_path = "package.json"
        package_lock_path = "package-lock.json"

        if not Path(package_json_path).exists():
            self.github_error(f"{package_json_path} ファイルが見つかりません")
            self.set_fail_output("package_missing")
            return False

        if not Path(package_lock_path).exists():
            self.github_error(f"{package_lock_path} ファイルが見つかりません")
            self.set_fail_output("lockfile_missing")
            return False

        return True

    def check_package_changes(self: "VersionChecker") -> Tuple[bool, Optional[git.Commit]]:
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

    def check_next_gen_versions(self: "VersionChecker") -> Tuple[bool, Optional[str], Optional[str]]:
        """バージョンの取得と検証。

        Returns:
            バージョンが正常であればTrueと新しいバージョン、ロックファイルのバージョン。
            失敗した場合はFalseとNone。
        """
        package_json_path = "package.json"
        package_lock_path = "package-lock.json"

        # setterが呼ばれた場合、ファイルからのバージョン取得をスキップ
        if self._new_version is not None:
            new_version = self._new_version
        else:
            # 現在のバージョン取得
            new_version = self.get_file_version(package_json_path)
            if not new_version:
                self.github_error("現在のバージョンの取得に失敗しました")
                self.set_fail_output("new_version_error")
                return False, None, None

        # package-lock.jsonのバージョン取得
        lock_version = self.get_file_version(package_lock_path)
        if not lock_version:
            self.github_error("package-lock.json のバージョン取得に失敗しました")
            self.set_fail_output("lock_version_error")
            return False, None, None

        # バージョン形式の検証
        if not self.is_semver(new_version):
            self.github_warning(f"バージョン形式が正しくありません: {new_version}")

        # バージョン整合性チェック
        if new_version != lock_version:
            self.github_error(f"package.json ({new_version}) は" f"package-lock.json ({lock_version}) のバージョンと一致していません")
            self.github_error("package-lock.json の更新が必要です。'npm install' または 'npm ci' を実行してください")
            self.set_fail_output("version_mismatch")
            return False, new_version, lock_version

        return True, new_version, lock_version

    def check_previous_version(self: "VersionChecker", pkg_commit: git.Commit) -> Tuple[bool, Optional[str]]:
        """前のバージョンを確認。

        Args:
            pkg_commit: 対象のコミットオブジェクト。

        Returns:
            バージョンが正常であればTrueと前のバージョン、失敗した場合はFalseとNone。
        """
        package_json_path = "package.json"
        new_version = self.get_file_version(package_json_path)

        if self._git_repo is None:
            self.github_error("リポジトリが初期化されていません")
            self.set_fail_output("repo_not_initialized")
            return False, None

        # 前のバージョン取得
        previous_version = self.get_previous_version(self._git_repo, pkg_commit, package_json_path)
        if not previous_version:
            self.github_notice("前のバージョンが見つかりません")
            self.set_fail_output("no_previous_version")
            return False, None

        if new_version is None:
            self.github_error("現在のバージョンの取得に失敗しました")
            self.set_fail_output("new_version_error")
            return False, None

        # バージョン変更があるか確認
        if new_version == previous_version:
            self.github_notice(f"バージョンに変更がありません: {new_version}")
            self.set_fail_output("no_version_change")
            return False, previous_version

        # バージョンが増加しているか確認
        if self.compare_versions(new_version, previous_version) <= 0:
            self.github_error(f"新しいバージョン ({new_version}) は前のバージョン ({previous_version}) 以下です")
            self.set_fail_output("version_not_incremented")
            return False, previous_version

        return True, previous_version

    def check_git_version_tags(self: "VersionChecker", new_version: str) -> bool:
        """バージョンタグの確認。

        Args:
            new_version: 新しいバージョンの文字列。

        Returns:
            バージョンタグが正常であればTrue、そうでなければFalse。
        """
        if self._git_repo is None:
            self.github_error("リポジトリが初期化されていません")
            self.set_fail_output("repo_not_initialized")
            return False

        # バージョンタグ取得
        tags = self.get_version_tags(self._git_repo)
        if tags:
            # 最新のバージョンタグと比較
            latest_tag = tags[-1]
            latest_version = latest_tag[1:] if latest_tag.startswith("v") else latest_tag

            if self.is_semver(latest_version) and self.compare_versions(new_version, latest_version) <= 0:
                self.github_error(f"新しいバージョン ({new_version}) は最新タグ ({latest_version}) 以下です")
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

            # ファイル存在確認
            if not self.validate_npm_file():
                return 1

            # package.jsonの変更確認
            has_changes, pkg_commit = self.check_package_changes()
            if not has_changes:
                return 0

            # バージョン検証
            versions_ok, new_version, lock_version = self.check_next_gen_versions()
            if not versions_ok:
                return 1

            if pkg_commit is None:
                self.github_error("package.jsonの変更が見つかりません")
                self.set_fail_output("no_package_change")
                return 1

            # 前のバージョン確認
            prev_version_ok, previous_version = self.check_previous_version(pkg_commit)
            if not prev_version_ok:
                return 1

            if new_version is None:
                self.github_error("現在のバージョンの取得に失敗しました")
                self.set_fail_output("new_version_error")
                return 1

            if previous_version is None:
                self.github_error("前のバージョンの取得に失敗しました")
                self.set_fail_output("previous_version_error")
                return 1

            if lock_version is None:
                self.github_error("package-lock.json のバージョン取得に失敗しました")
                self.set_fail_output("lock_version_error")
                return 1

            # バージョンタグ確認
            if not self.check_git_version_tags(new_version):
                return 1

            # すべてのチェックが成功したら
            self.github_notice(f"バージョンが {previous_version} から {new_version} に更新されました")
            self.set_success_output(new_version, previous_version)
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
