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
        self.repo = None
        self._version: Optional[str] = None  # 新しいプライベート変数を追加

    @property
    def version(self: "VersionChecker") -> Optional[str]:
        """バージョン情報を取得"""
        return self._version

    @version.setter
    def version(self: "VersionChecker", value: str) -> None:
        """バージョン情報を設定し、ファイル入力処理をスキップ"""
        self._version = value

    # GitHub Actions用ログコマンド
    def github_notice(self: "VersionChecker", message: str) -> None:
        """GitHub Actionsに通知メッセージを出力"""
        print(f"::notice::{message}")

    def github_warning(self: "VersionChecker", message: str) -> None:
        """GitHub Actionsに警告メッセージを出力"""
        print(f"::warning::{message}")

    def github_error(self: "VersionChecker", message: str) -> None:
        """GitHub Actionsにエラーメッセージを出力"""
        print(f"::error::{message}")

    def set_github_output(self: "VersionChecker", name: str, value: str) -> None:
        """GitHub Actionsの出力変数を設定"""
        github_output = os.environ.get("GITHUB_OUTPUT")
        if github_output:
            with open(github_output, "a") as f:
                f.write(f"{name}={value}\n")
        else:
            logger.warning("GITHUB_OUTPUT環境変数が設定されていません")

    def set_fail_output(self: "VersionChecker", reason: str, **kwargs: str) -> None:
        """失敗時の出力を設定"""
        self.set_github_output("status", "failure")
        self.set_github_output("message", reason)
        self.set_github_output("version_changed", "false")
        self.set_github_output("reason", reason)
        for key, value in kwargs.items():
            self.set_github_output(key, value)

    def set_success_output(self: "VersionChecker", new_version: str = "", old_version: str = "") -> None:
        """成功時の出力を設定"""
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

    def get_latest_commit_for_file(self: "VersionChecker", repo: git.Repo, file_path: str) -> Optional[git.Commit]:
        """ファイルを変更した最新のコミットを取得"""
        try:
            commits = list(repo.iter_commits(paths=file_path, max_count=1))
            return commits[0] if commits else None
        except Exception as e:
            self.github_warning(f"{file_path}の最新コミット取得に失敗しました: {e}")
            return None

    def get_commit_time(self: "VersionChecker", commit: git.Commit) -> int:
        """コミットのUNIXタイムスタンプを取得"""
        return commit.committed_date

    def get_previous_version(self: "VersionChecker", repo: git.Repo, commit: git.Commit, file_path: str) -> Optional[str]:
        """指定コミットの一つ前のバージョンを取得"""
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
        """リポジトリからセマンティックバージョニングに従ったタグを取得"""
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

    def compare_versions(self: "VersionChecker", v1: str, v2: str) -> int:
        """セマンティックバージョンの比較: v1 > v2 なら1、v1 == v2 なら0、v1 < v2 なら-1"""
        ver1 = version.parse(v1)
        ver2 = version.parse(v2)
        if ver1 > ver2:
            return 1
        elif ver1 < ver2:
            return -1
        else:
            return 0

    def initialize_repo(self: "VersionChecker") -> bool:
        """リポジトリを初期化"""
        try:
            self.repo = git.Repo(".")
            return True
        except Exception as e:
            self.github_error(f"リポジトリの初期化に失敗しました: {e}")
            return False

    def check_file_existence(self: "VersionChecker") -> bool:
        """ファイルの存在確認"""
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
        """package.jsonの変更確認"""

        if self.repo is None:
            self.github_error("リポジトリが初期化されていません")
            self.set_fail_output("repo_not_initialized")
            return False, None

        package_json_path = "package.json"
        pkg_commit = self.get_latest_commit_for_file(self.repo, package_json_path)
        if not pkg_commit:
            self.github_notice("package.json の変更が見つかりません")
            self.set_fail_output("no_package_change")
            return False, None

        return True, pkg_commit

    def check_next_gen_versions(self: "VersionChecker") -> Tuple[bool, Optional[str], Optional[str]]:
        """バージョンの取得と検証"""
        package_json_path = "package.json"
        package_lock_path = "package-lock.json"

        # setterが呼ばれた場合、ファイルからのバージョン取得をスキップ
        if self._version is not None:
            current_version = self._version
        else:
            # 現在のバージョン取得
            current_version = self.get_file_version(package_json_path)
            if not current_version:
                self.github_error("現在のバージョンの取得に失敗しました")
                self.set_fail_output("current_version_error")
                return False, None, None

        # package-lock.jsonのバージョン取得
        lock_version = self.get_file_version(package_lock_path)
        if not lock_version:
            self.github_error("package-lock.json のバージョン取得に失敗しました")
            self.set_fail_output("lock_version_error")
            return False, None, None

        # バージョン形式の検証
        if not self.is_semver(current_version):
            self.github_warning(f"バージョン形式が正しくありません: {current_version}")

        # バージョン整合性チェック
        if current_version != lock_version:
            self.github_error(f"package.json ({current_version}) は" f"package-lock.json ({lock_version}) のバージョンと一致していません")
            self.github_error("package-lock.json の更新が必要です。'npm install' または 'npm ci' を実行してください")
            self.set_fail_output("version_mismatch")
            return False, current_version, lock_version

        return True, current_version, lock_version

    def check_previous_version(self: "VersionChecker", pkg_commit: git.Commit) -> Tuple[bool, Optional[str]]:
        """前のバージョンを確認"""
        package_json_path = "package.json"
        current_version = self.get_file_version(package_json_path)

        if self.repo is None:
            self.github_error("リポジトリが初期化されていません")
            self.set_fail_output("repo_not_initialized")
            return False, None

        # 前のバージョン取得
        previous_version = self.get_previous_version(self.repo, pkg_commit, package_json_path)
        if not previous_version:
            self.github_notice("前のバージョンが見つかりません")
            self.set_fail_output("no_previous_version")
            return False, None

        if current_version is None:
            self.github_error("現在のバージョンの取得に失敗しました")
            self.set_fail_output("current_version_error")
            return False, None

        # バージョン変更があるか確認
        if current_version == previous_version:
            self.github_notice(f"バージョンに変更がありません: {current_version}")
            self.set_fail_output("no_version_change")
            return False, previous_version

        # バージョンが増加しているか確認
        if self.compare_versions(current_version, previous_version) <= 0:
            self.github_error(f"新しいバージョン ({current_version}) は前のバージョン ({previous_version}) 以下です")
            self.set_fail_output("version_not_incremented")
            return False, previous_version

        return True, previous_version

    def check_version_tags(self: "VersionChecker", current_version: str) -> bool:
        """バージョンタグの確認"""

        if self.repo is None:
            self.github_error("リポジトリが初期化されていません")
            self.set_fail_output("repo_not_initialized")
            return False

        # バージョンタグ取得
        tags = self.get_version_tags(self.repo)
        if tags:
            # 最新のバージョンタグと比較
            latest_tag = tags[-1]
            latest_version = latest_tag[1:] if latest_tag.startswith("v") else latest_tag

            if self.is_semver(latest_version) and self.compare_versions(current_version, latest_version) <= 0:
                self.github_error(f"新しいバージョン ({current_version}) は最新タグ ({latest_version}) 以下です")
                self.set_fail_output("version_not_incremented_from_tag")
                return False

        return True

    def run(self: "VersionChecker") -> int:
        """メイン処理を実行"""
        try:
            # リポジトリ初期化
            if not self.initialize_repo():
                return 1

            # ファイル存在確認
            if not self.check_file_existence():
                return 1

            # package.jsonの変更確認
            has_changes, pkg_commit = self.check_package_changes()
            if not has_changes:
                return 0

            # バージョン検証
            versions_ok, current_version, lock_version = self.check_next_gen_versions()
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

            if current_version is None:
                self.github_error("現在のバージョンの取得に失敗しました")
                self.set_fail_output("current_version_error")
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
            if not self.check_version_tags(current_version):
                return 1

            # すべてのチェックが成功したら
            self.github_notice(f"バージョンが {previous_version} から {current_version} に更新されました")
            self.set_success_output(current_version, previous_version)
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
