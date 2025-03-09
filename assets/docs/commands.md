# 開発者向けコマンド集

## 環境セットアップ

```bash
poetry install
npm install
```

## 開発コマンド

```bash
# アプリ起動
poetry run streamlit run app.py

# リンター&コードフォーマット実行
poetry run ruff check . --fix
poetry run mypy .

# テスト系
poetry run pytest
poetry run pytest --cov=. --cov-report=xml
```

## Git 関連

```bash
# pre-commit hooks のインストール
pre-commit install
pre-commit install --hook-type commit-msg

# pre-commit hooks の手動実行
pre-commit run --all-files

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
```

## その他の便利なコマンド

```bash
# 依存関係の更新
poetry update

# キャッシュのクリーンアップ
poetry cache clear . --all
npm cache clean --force
```
