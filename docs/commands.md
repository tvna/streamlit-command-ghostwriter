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
```

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

### 前提条件

- Python 3.8 以上
- Streamlit アプリケーションが http://localhost:8502/ で実行されていること
- 以下のパッケージがインストールされていること:
  - pytest
  - pytest-playwright
  - playwright

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

## Git 関連

```bash
# pre-commit hooks の手動実行
npm run scan

# コミットログの作成
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

## その他の便利なコマンド

```bash
# 依存関係の更新
poetry update && poetry lock
npm update

# キャッシュのクリーンアップ
poetry cache clear . --all
npm cache clean --force
```
