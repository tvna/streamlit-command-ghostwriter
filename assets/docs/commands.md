# 開発者向けコマンド集

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
poetry run ruff check . --fix
poetry run mypy .

# テスト系
poetry run pytest --cov=. --cov-report=html
poetry run pytest --pdb
poetry run pudb app.py

# コードの複雑さ解析
poetry run lizard -x "./node_modules/*" -x "./.venv/*" -x "./build/*" -x "./dist/*" -x "./htmlcov/*" -x "./.github/*" --CCN "10"
poetry run lizard ./.github/* --CCN "13"

# CUIデバッグ
```

## Git 関連

```bash
# pre-commit hooks の手動実行
poetry run pre-commit run --all-files

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
poetry update
npm update

# キャッシュのクリーンアップ
poetry cache clear . --all
npm cache clean --force
```
