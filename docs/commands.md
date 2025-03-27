# 開発者向けコマンド集

## TL;DR
- https://docs.pytest.org/en/stable/getting-started.html
- https://docs.github.com/ja/actions/writing-workflows/workflow-syntax-for-github-actions

## 環境セットアップ

```bash
# 依存パッケージのインストールと、開発ブランチに切り替え
poetry install
npm install
git checkout develop

# pre-commit hooks のインストール
poetry run pre-commit uninstall
poetry run pre-commit install --hook-type commit-msg

# macosにおけるcompletion
poetry completions zsh > $(brew --prefix)/share/zsh-completions/_poetry
```

---

## 開発コマンド

```bash
# アプリ起動
poetry run streamlit run app.py

# リンター&コードフォーマット実行
npm run lint

# テスト系
npm run test
npm run coverage
npm run benchmark
poetry run pytest --pdb
poetry run pudb app.py

# コードの複雑さ解析
npm run scan

```

## End-to-End テスト

End-to-End テストは pytest-playwright を使用して実装されています。

### セットアップ

```bash
# 必要なパッケージをインストール
poetry run playwright install --with-deps chromium
poetry run playwright install --with-deps firefox
poetry run playwright install --with-deps webkit

# Streamlit アプリケーションを起動（別ターミナルで実行）
streamlit run app.py --server.port=8502
```

### テストの実行

```bash
# 特定のブラウザでテストを実行
poetry run pytest -vv -n auto --browser chromium -m "benchmark" --benchmark-disable
poetry run pytest -vv -n auto --browser firefox -m "benchmark" --benchmark-disable
poetry run pytest -vv -n auto --browser webkit -m "benchmark" --benchmark-disable
```

---

## ソースコード管理

```bash
# pre-commit hooks の手動実行
npm run scan

# コミットメッセージの作成
npm run commit

# タグの確認
git tag
git tag -l

# タグの追加と共有
git tag ${TAG_NAME}
git push origin ${TAG_NAME}

# タグの削除
git tag -d {$TAG_NAME}

# 誤ったmainブランチへのコミットを削除
git checkout main
git reset --hard HEAD~3
```

## コミットメッセージの書き方

コミットメッセージは [Angular Commit Message Format](https://github.com/angular/angular/blob/main/CONTRIBUTING.md#-commit-message-format) に準拠しています。

### コミットタイプの使い分け

各タイプの使用例と使い分けは以下の通りです：

- `feat`: 新機能の追加
  - 新しいユーザー向け機能の追加
  - 新しいAPIエンドポイントの実装
  - 既存機能への新しいオプション追加
  - エンドユーザーに影響する変更全般

- `fix`: バグ修正
  - 既知のバグの修正
  - タイプミスの修正
  - 実行時エラーの修正
  - エンドユーザーに影響するバグ修正全般

- `docs`: ドキュメントのみの変更
  - READMEの更新
  - コメントの追加や修正
  - APIドキュメントの更新
  - 開発者向けドキュメントの変更

- `style`: コードの意味に影響を与えない変更
  - インデントの修正
  - フォーマットの調整
  - セミコロンの追加
  - 空白の調整

- `refactor`: 新機能追加でもバグ修正でもないコードの変更
  - コードのリファクタリング
  - 変数名の改善
  - コードの構造化
  - 未使用コードの削除

- `perf`: パフォーマンス向上を目的としたコードの変更
  - 実行速度の改善
  - メモリ使用量の最適化
  - データベースクエリの最適化
  - キャッシュの実装

- `test`: テストの追加や変更
  - ユニットテストの追加
  - E2Eテストの修正
  - テストケースの追加
  - テストフレームワークの設定変更

- `build`: ビルドシステムや外部依存関係に影響を与える変更
  - 依存パッケージの追加・削除
  - ビルドスクリプトの変更
  - パッケージバージョンの更新
  - ビルド設定の変更

- `ci`: CIの設定ファイルやスクリプトの変更
  - GitHub Actionsの設定変更
  - CIパイプラインの修正
  - デプロイスクリプトの更新
  - CI/CD関連の設定変更

- `chore`: ソースやテストの変更を含まない変更
  - gitignoreの更新
  - 開発環境の設定変更
  - パッケージマネージャーの設定
  - その他の雑務的な変更

- `revert`: コミットの取り消し
  - 以前のコミットの取り消し
  - 機能のロールバック
  - 変更の巻き戻し

### 紛らわしいタイプの使い分け

以下のタイプは特に混同しやすいため、注意が必要です：

#### `feat` vs `perf`
- `feat`: 新しい機能や振る舞いを追加する変更
- `perf`: 既存機能の実行効率を改善する変更
```bash
# feat の例（新しい機能を追加）
feat: キャッシュ機能を追加

# perf の例（既存機能を最適化）
perf: キャッシュのアルゴリズムを改善
```

#### `fix` vs `refactor`
- `fix`: 誤った動作を修正する変更
- `refactor`: 正しく動作しているコードの構造を改善する変更
```bash
# fix の例（バグ修正）
fix: nullチェックの欠落による例外を修正

# refactor の例（コード改善）
refactor: nullチェックをユーティリティ関数に集約
```

#### `style` vs `refactor`
- `style`: コードの動作に影響しない体裁の変更
- `refactor`: コードの構造を改善する変更（動作は同じ）
```bash
# style の例（見た目のみ）
style: 行末の空白を削除

# refactor の例（構造改善）
refactor: 重複したバリデーション処理をクラスに集約
```

#### `chore` vs `build`
- `chore`: 開発プロセスやツールの変更
- `build`: プロジェクトのビルドや依存関係の変更
```bash
# chore の例（開発環境）
chore: VSCode設定ファイルを更新

# build の例（依存関係）
build: Pytestを7.1.1から7.4.0にアップデート
```

#### `docs` vs `chore`
- `docs`: ドキュメントの内容に関する変更
- `chore`: ドキュメント生成ツールなどの変更
```bash
# docs の例（内容の変更）
docs: デプロイ手順のタイプミスを修正

# chore の例（ツールの変更）
chore: Sphinxの設定を更新
```

### その他の注意事項

1. 複数の変更を含む場合は、最も影響の大きい変更に基づいてタイプを選択します：
```bash
# パフォーマンス改善のためにコードをリファクタリングした場合
perf: データベースクエリを最適化

# バグ修正のためにリファクタリングした場合
fix: 重複処理による無限ループを修正
```

2. 迷った場合は、エンドユーザーへの影響を基準に判断します：
- エンドユーザーに新しい機能や変更が見える → `feat`
- エンドユーザーに修正が見える → `fix`
- エンドユーザーには変更が見えない → `refactor`/`style`/`chore`など

3. セキュリティ関連の変更は、影響の種類に応じて適切なタイプを選択します：
```bash
# セキュリティバグの修正
fix: SQLインジェクションの脆弱性を修正

# セキュリティ機能の追加
feat: 二要素認証を追加

# セキュリティ設定の変更
chore: セキュリティヘッダーの設定を更新
```

### コミットメッセージの例

```bash
# 新機能追加
feat: Streamlitのマルチページ機能を追加

# バグ修正
fix: Pydanticのバリデーションエラーを修正

# ドキュメント更新
docs: Streamlitコンポーネントの使用例を追加

# コードスタイル修正
style: Ruffの設定に従ってインデントを修正

# リファクタリング
refactor: Jinja2テンプレート処理を別クラスに分離

# パフォーマンス改善
perf: PyYAML設定の読み込みをキャッシュ化

# テスト追加
test: Playwrightを使用したE2Eテストを追加

# ビルド関連
build: streamlitを1.43.2にアップデート

# CI関連
ci: pytest-xdistによる並列テスト実行を追加

# その他の変更
chore: mypy設定のpython_versionを3.12に更新

# 変更取り消し
revert: feat(ui)のマルチページ追加を取り消し
```

### スコープの指定

変更範囲を明確にするため、必要に応じてスコープを指定できます：

```bash
feat(ui): Streamlitのサイドバーにフィルター機能を追加
fix(validation): Pydanticのバリデーションルールを修正
docs(api): Jinja2テンプレートの使用例を追加
```

### 破壊的変更の明示

破壊的変更がある場合は、タイプの後に`!`を付けるか、フッターに`BREAKING CHANGE:`を記載します：

```bash
# タイプに!を付ける場合
feat!: Pydanticv2へのアップグレード

# フッターに記載する場合
feat: Pydanticv2へのアップグレード

BREAKING CHANGE: ValidationErrorの戻り値の型が変更されました
```

## その他の便利なコマンド

```bash
# 依存関係の更新
poetry update && poetry lock
npm update

# キャッシュのクリーンアップ
poetry cache clear . --all
npm cache clean --force
```