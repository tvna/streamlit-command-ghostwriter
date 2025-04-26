module.exports = {
    extends: ["@commitlint/config-conventional"],
    parserPreset: "conventional-changelog-conventionalcommits",
    prompt: {
      settings: {},
      messages: {
        skip: "'Enterでスキップ'",
        max: "最大%d文字",
        min: "最小%d文字",
        emptyWarning: "必須事項です",
        upperLimitWarning: "最大文字数を超えています",
        lowerLimitWarning: "最低文字数に足りていません",
      },
      questions: {
        type: {
          description: "コミットする変更の種類を選択してください",
          enum: {
            feat: {
              description: "新機能の追加",
              title: "Features",
            },
            fix: {
              description: "バグの修正",
              title: "Bug Fixes",
            },
            docs: {
              description: "ドキュメントのみの変更",
              title: "Documentation",
            },
            style: {
              description: "コードの意味に影響を与えない変更",
              title: "Styles",
            },
            refactor: {
              description: "新機能追加でもバグ修正でもないコードの変更",
              title: "Code Refactoring",
            },
            perf: {
              description: "パフォーマンス向上を目的としたコードの変更",
              title: "Performance Improvements",
            },
            test: {
              description: "テストの追加や変更",
              title: "Tests",
            },
            build: {
              description: "ビルドシステムや外部依存関係に影響を与える変更",
              title: "Builds",
            },
            ci: {
              description: "CIの設定ファイルやスクリプトの変更",
              title: "Continuous Integrations",
            },
            chore: {
              description:
                "ソースやテストの変更を含まない変更",
              title: "Chores",
            },
            revert: {
              description: "コミットの取り消し",
              title: "Reverts",
            },
          },
        },
        scope: {
          description: "変更範囲を記述する",
        },
        subject: {
          description: "変更内容を簡潔に記載する",
        },
        body: {
          description: "変更内容を詳述する(body:最大200文字)",
        },
        isBreaking: {
          description: "破壊的変更はあるか?",
        },
        breakingBody: {
          description: "破壊的変更がある場合は必ず変更内容を詳説する",
        },
        breaking: {
          description: "破壊的変更内容を詳述する(footer:最大100文字)",
        },
        isIssueAffected: {
          description: "未解決のissuesに関する変更か",
        },
        issuesBody: {
          description: "issuesをcloseする場合は必ず変更内容の詳説する",
        },
        issues: {
          description: "issue番号を記載する(footer:最大100文字)",
        },
      },
    },
  };
