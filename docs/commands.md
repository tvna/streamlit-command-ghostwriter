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
npm run test
poetry run pytest --pdb
poetry run pudb app.py

# コードの複雑さ解析
poetry run lizard -x "./node_modules/*" -x "./.venv/*" -x "./build/*" -x "./dist/*" -x "./htmlcov/*" -x "./tests/*" --CCN "10"
poetry run lizard ./tests/* --CCN "20"

# CUIデバッグ
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
pip install pytest pytest-playwright
playwright install  # ブラウザをインストール

# Streamlit アプリケーションを起動（別ターミナルで実行）
streamlit run app.py --server.port=8502
```

### テストの実行

```bash
# すべてのテストを実行
pytest tests/e2e/test_streamlit_app.py -v

# 特定のテストを実行
pytest tests/e2e/test_streamlit_app.py::test_app_title -v

# ヘッドレスモードでテストを実行
pytest tests/e2e/test_streamlit_app.py --browser chromium --headless -v

# 非ヘッドレスモード（ブラウザを表示）でテストを実行
pytest tests/e2e/test_streamlit_app.py --browser chromium --headed -v

# 特定のブラウザでテストを実行
pytest tests/e2e/test_streamlit_app.py --browser chromium -v  # Chromium
pytest tests/e2e/test_streamlit_app.py --browser firefox -v   # Firefox
pytest tests/e2e/test_streamlit_app.py --browser webkit -v    # WebKit (Safari)
```

### テストの構成

- `conftest.py`: pytest の設定ファイル
- `test_streamlit_app.py`: Streamlit アプリケーションのテスト
- `test_data/`: テストで使用するデータファイル

### テストのカスタマイズとトラブルシューティング

- セレクタの調整ポイント:
  1. ボタンやフィールドのセレクタ（例: `button:has-text('実行')`）
  2. 期待される出力や結果のセレクタ
  3. ファイルアップロードパスやダウンロードファイル名
- テストが失敗する場合は、セレクタが正しいか確認
- Streamlit の UI 構造が変更された場合、セレクタの更新が必要
- デバッグには `page.pause()` を使用して、テスト実行中にブラウザを一時停止可能

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
