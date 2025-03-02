<div align="center">

[![streamlit][streamlit-img]](https://streamlit.io/)
[![build status][build-img]][build-link]
[![codecov][codecov-img]][codecov-link]
[![License: MIT][license-img]][license-link]

</div>

# Welcome to Command ghostwriter
このアプリケーションは、IaCをはじめ自動化ツール導入が困難なインフラ運用現場において、CLIによる形式的な運用作業を効率化するソリューションです。

繰り返しが多くなりがちなCLI実行コマンドを、設定定義ファイル(csv/yaml/toml)とJinjaテンプレートファイルの2つに分けて記述することで、設定定義ファイルの変更のみでCLIコマンドが生成できます。また、コマンドに留まらず、Markdownによる作業手順書の生成にも対応しています。

まずはサンプルファイルをアップロードして、「CLIコマンド生成」をクリックした結果を確認してみてください。

## 主な利用ケース
- PowerShellコマンド
- Linuxコマンド
- ネットワーク機器の操作コマンド
- Markdown由来の手順書やマニュアル

# Quick start

## Windows client (amd64)
1. 実行環境のインストール (Python, Git)

```ps1
# chocolateyを使う場合
Set-ExecutionPolicy Bypass -Scope Process -Force; iex ((New-Object System.Net.WebClient).DownloadString('https://chocolatey.org/install.ps1'))
choco install python312
choco install git
```

2. PowerShellにて、以下のコマンドを実行する
```ps1
cd $env:USERPROFILE\Downloads
git clone https://github.com/tvna/streamlit-command-ghostwriter.git
cd streamlit-command-ghostwriter

(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python -

[System.Environment]::SetEnvironmentVariable('path', $env:APPDATA + "\Python\Scripts;" + [System.Environment]::GetEnvironmentVariable('path', "User"),"User")

poetry install
poetry run streamlit run app.py
```

[streamlit-img]: https://img.shields.io/badge/-Streamlit-FF4B4B?style=flat&logo=streamlit&logoColor=white
[streamlit-cloud-img]: https://static.streamlit.io/badges/streamlit_badge_black_white.svg
[streamlit-cloud-link]: https://command-ghostwriter.streamlit.app/
[build-link]: https://github.com/tvna/streamlit-command-ghostwriter/actions/workflows/test-develop-branch.yml
[build-img]: https://github.com/tvna/streamlit-command-ghostwriter/actions/workflows/test-develop-branch.yml/badge.svg?branch=develop
[codecov-link]: https://codecov.io/gh/tvna/streamlit-command-ghostwriter
[codecov-img]: https://codecov.io/gh/tvna/streamlit-command-ghostwriter/graph/badge.svg?token=I2LDXQHXB5
[license-link]: https://github.com/tvna/streamlit-command-ghostwriter/blob/main/LICENSE
[license-img]: https://img.shields.io/badge/license-MIT-blue


