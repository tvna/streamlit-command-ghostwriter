#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PR作成スクリプト
developブランチからmainブランチへのPRを作成する
"""

import logging
import os
import re
import subprocess  # noqa: S404 - セキュリティチェック済みの安全な使用法
import sys
from typing import List, Tuple

import git

# ロギング設定
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)

# 安全なコマンドのリスト
SAFE_COMMANDS = ["gh"]


class PullRequestCreator:
    """PRを作成するクラス"""

    def __init__(self: "PullRequestCreator") -> None:
        """初期化メソッド。

        Attributes:
            new_version: 新しいバージョンの情報。
            old_version: 古いバージョンの情報。
        """
        self.new_version = None
        self.old_version = None

    def github_notice(self: "PullRequestCreator", message: str) -> None:
        """GitHub Actionsに通知メッセージを出力。

        Args:
            message: 通知メッセージの文字列。
        """
        print(f"::notice::{message}")

    def github_warning(self: "PullRequestCreator", message: str) -> None:
        """GitHub Actionsに警告メッセージを出力。

        Args:
            message: 警告メッセージの文字列。
        """
        print(f"::warning::{message}")

    def github_error(self: "PullRequestCreator", message: str) -> None:
        """GitHub Actionsにエラーメッセージを出力。

        Args:
            message: エラーメッセージの文字列。
        """
        print(f"::error::{message}")

    def set_github_output(self: "PullRequestCreator", name: str, value: str) -> None:
        """GitHub Actionsの出力変数を設定。

        Args:
            name: 出力変数の名前。
            value: 出力変数の値。
        """
        github_output = os.environ.get("GITHUB_OUTPUT")

        if not github_output:
            print("GITHUB_OUTPUT環境変数が設定されていません")
            logger.warning("GITHUB_OUTPUT環境変数が設定されていません")
            return

        if not os.path.isfile(github_output):
            print(f"指定されたファイルが見つかりません: {github_output}")
            logger.error(f"指定されたファイルが見つかりません: {github_output}")
            return

        with open(github_output, "a") as f:
            f.write(f"{name}={value}\n")

    def validate_command(self: "PullRequestCreator", cmd: List[str]) -> bool:
        """コマンドが安全なものであるか確認。

        Args:
            cmd: コマンドの引数リスト。

        Returns:
            コマンドが安全であればTrue、そうでなければFalse。
        """
        # コマンドの先頭部分（実行ファイル名）のみを検証
        executable = cmd[0]
        base_executable = os.path.basename(executable)

        # 許可リストに含まれるコマンドのみ実行を許可
        is_safe = any(base_executable == safe_cmd or base_executable.startswith(f"{safe_cmd}.") for safe_cmd in SAFE_COMMANDS)

        # コマンドの引数にも危険な文字がないか確認
        if is_safe and len(cmd) > 1:
            for arg in cmd[1:]:
                if not isinstance(arg, str):
                    logger.error(f"無効な引数が含まれています: {arg}")
                    return False
                # シェル特殊文字を含む引数は拒否
                if any(c in arg for c in ["|", "&", ";", "$", ">", "<", "`", "\\"]):
                    logger.error(f"危険な文字を含む引数が指定されました: {arg}")
                    return False

        return is_safe

    def run_gh_cmd(self: "PullRequestCreator", args: List[str]) -> bool:
        """GitHub CLIコマンドを実行。

        Args:
            args: コマンドの引数リスト。

        Returns:
            コマンドが成功した場合はTrue、失敗した場合はFalse。
        """
        cmd = ["gh"] + args

        # コマンドの引数に危険な文字が含まれているか確認
        for arg in args:
            if any(c in arg for c in ["|", "&", ";", "$", ">", "<", "`", "\\"]):
                self.github_error(f"危険な文字を含む引数が指定されました: {arg}")
                return False

        # GH_TOKENが環境変数に設定されているか確認
        if "GH_TOKEN" not in os.environ:
            self.github_error("GH_TOKEN環境変数が設定されていません")
            return False

        # コマンドの検証
        if not self.validate_command(cmd):
            self.github_error(f"安全でないコマンドが指定されました: {cmd[0]}")
            return False

        try:
            result = subprocess.run(  # noqa: S603
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=os.environ,
                shell=False,
                check=False,
            )
            return result.returncode == 0
        except Exception as e:
            self.github_error(f"コマンド実行中にエラーが発生しました: {e}")
            return False

    def get_latest_commit_message(self: "PullRequestCreator") -> str:
        """developブランチから最新のコミットメッセージを取得。

        Returns:
            最新のコミットメッセージの文字列。
        """
        try:
            repo = git.Repo(".")
            commit = repo.head.commit
            message = str(commit.message)

            # 機密情報が含まれていないか確認（簡易的）
            sensitive_patterns = r"(password|secret|token|key|認証|パスワード|ghp_)"
            if re.search(sensitive_patterns, message, re.IGNORECASE):
                self.github_warning("コミットメッセージに機密情報が含まれている可能性があります")
                # 機密情報をマスク処理
                masked_message = re.sub(r"ghp_\w+", "ghp_***", message)
                return masked_message

            return message
        except Exception as e:
            self.github_warning(f"コミットメッセージの取得に失敗しました: {e}")
            return "Unable to fetch commit message"

    def get_commit_titles(self: "PullRequestCreator", max_commits: int = 10) -> List[str]:
        """main..developの範囲のコミット件名リストを取得。

        Args:
            max_commits: 取得するコミットの最大数。

        Returns:
            コミット件名のリスト。
        """
        if not isinstance(max_commits, int) or max_commits < 0:
            self.github_error("max_commitsは0以上の整数である必要があります")
            return []

        try:
            repo = git.Repo(".")

            # mainブランチの最新情報を取得
            try:
                repo.git.fetch("origin", "main:main")
            except Exception as e:
                self.github_warning(f"mainブランチのフェッチに失敗しました: {e}")
                return ["Unable to fetch commit titles"]

            # コミット一覧を取得
            commits = list(repo.iter_commits("main..develop", max_count=max_commits))

            # コミット件名のリストを作成
            titles = []
            for commit in commits:
                # 1行目だけを取得
                title = str(commit.message).split("\n")[0]
                titles.append(f"- {title}")

            return titles
        except Exception as e:
            self.github_warning(f"コミット一覧の取得に失敗しました: {e}")
            return ["Unable to fetch commit titles"]

    def create_pr(self: "PullRequestCreator", title: str, body: str, labels: List[str]) -> bool:
        """PRを作成して成功・失敗を返す。

        Args:
            title: PRのタイトル。
            body: PRの本文。
            labels: PRに付けるラベルのリスト。

        Returns:
            PRの作成が成功した場合はTrue、失敗した場合はFalse。
        """
        if not isinstance(title, str) or not isinstance(body, str) or not isinstance(labels, list):
            self.github_error("引数は正しい型である必要があります: titleとbodyは文字列、labelsはリスト")
            return False

        args = ["pr", "create", "--base", "main", "--head", "develop", "--title", title, "--body", body]

        if labels:
            args.extend(["--label", ",".join(labels)])

        return self.run_gh_cmd(args)

    def get_version_info(self: "PullRequestCreator") -> bool:
        """バージョン情報の取得。

        Returns:
            バージョン情報が正常に取得できた場合はTrue、そうでなければFalse。
        """
        self.new_version = os.environ.get("NEW_VERSION")
        self.old_version = os.environ.get("OLD_VERSION")

        if not self.new_version or not self.old_version:
            self.github_error("バージョン情報が環境変数に設定されていません")
            return False

        return True

    def prepare_pr_content(self: "PullRequestCreator") -> Tuple[str, str, List[str]]:
        """PR内容の準備。

        Returns:
            PRのタイトル、本文、ラベルのタプル。
        """
        # コミットメッセージの取得
        commit_msg = self.get_latest_commit_message()

        # PRタイトルの作成
        pr_title = f"Release v{self.new_version}"

        # コミット一覧の取得
        commit_titles = self.get_commit_titles(50)

        # PR本文の作成
        pr_body = (
            f"develop から main へのバージョン {self.new_version} の自動 PR\n\n"
            f"このPRは以下の理由で自動的に作成されました:\n"
            f"1. develop ブランチ上ですべてのテストが合格\n"
            f"2. パッケージバージョンが v{self.old_version} から v{self.new_version} に更新された\n"
            f"3. package-lock.json も適切に更新されています\n"
            f"4. v{self.new_version} は既存のすべてのタグより新しいバージョンです\n\n"
            f"コミットメッセージ:\n"
            f"```\n{commit_msg}\n```\n\n"
            f"## 変更概要\n"
            f"このPRには、以下のコミットが含まれています:\n\n"
            f"{chr(10).join(commit_titles)}\n\n"
            f"## チェック項目\n"
            f"- [x] すべてのテストが合格\n"
            f"- [x] コード品質チェックが合格\n"
            f"- [x] バージョンが v{self.new_version} に更新されました\n"
            f"- [x] package-lock.json も更新されています\n"
            f"- [x] バージョンは既存のリリースより新しいです"
        )

        # ラベル設定
        labels = ["automated-pr", "release"]

        return pr_title, pr_body, labels

    def run(self: "PullRequestCreator") -> int:
        """メイン処理を実行。

        Returns:
            処理が成功した場合は0、失敗した場合は1。
        """
        try:
            self.github_notice("PRの作成準備中...")

            # バージョン情報の取得
            if not self.get_version_info():
                return 1

            # PR内容の準備
            pr_title, pr_body, labels = self.prepare_pr_content()

            # PRの作成
            self.github_notice("PRを作成中...")
            success = self.create_pr(pr_title, pr_body, labels)

            if not success:
                self.github_error("PRの作成に失敗しました")
                return 1

            self.github_notice("PRが作成されました")
            return 0

        except Exception as e:
            self.github_error(f"予期せぬエラーが発生しました: {e}")
            return 1


def main() -> int:
    """メイン関数。

    Returns:
        スクリプトの終了コード。
    """
    creator = PullRequestCreator()
    return creator.run()


if __name__ == "__main__":
    sys.exit(main())
