# ビジュアルワークフローエディタ

[English](README.md) | [中文](README_zh.md) | [日本語](README_ja.md)

これは Docker コンテナ化されたビジュアルワークフローエディタプロジェクトで、クロスプラットフォーム開発と CI/CD デプロイメントをサポートしています。

## プロジェクト概要

このプロジェクトには以下が含まれています：

- FastAPI ベースのバックエンドサービス
- React ベースのフロントエンドアプリケーション
- SQLite データベースストレージ

## 開発環境要件

- Docker と Docker Compose
- Visual Studio Code（推奨、Dev Container をサポート）
- Git

Python、Node.js などの依存関係をインストールする必要はなく、すべて Docker コンテナ内で実行されます。

## Dev Container を使用した開発（推奨）

### 1. 必要なツールのインストール

- [Docker Desktop](https://www.docker.com/products/docker-desktop) をインストール
- [Visual Studio Code](https://code.visualstudio.com/) をインストール
- VSCode で [Dev Containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) 拡張機能をインストール

### 2. プロジェクトのクローンと開発コンテナの起動

```bash
git clone https://github.com/あなたのユーザー名/visual_workflow_editor.git
cd visual_workflow_editor
```

VSCode でプロジェクトフォルダを開きます。「Devcontainer 設定が検出されました」というプロンプトが表示されたら、「コンテナで再度開く」をクリックします。または、コマンドパレット（F1）を使用して「Dev Containers: コンテナでフォルダを開く」を選択します。

初回起動時、Dev Container は自動的に開発環境を構築し、すべての依存関係をインストールし、フロントエンドとバックエンドのサービスを準備します。

### 3. アプリケーションへのアクセス

コンテナが実行されたら：

- フロントエンド: http://localhost:3000
- バックエンド API: http://localhost:8000

## スクリプトを使用した開発（代替方法）

VS Code Dev Container を使用しない場合は、プロジェクトで提供されているスクリプトを使用することもできます：

```bash
# 開発環境を起動
./scripts/dev.sh

# コンテナを再構築（依存関係が更新された場合）
./scripts/rebuild.sh

# サービスのステータスを確認
./scripts/check-status.sh
```

## プロジェクト構造

```
visual_workflow_editor/
├── .devcontainer/       # Dev Container設定
├── .github/workflows/   # GitHub Actions CI/CD設定
├── backend/             # Pythonバックエンド
│   ├── app/             # アプリケーションコード
│   └── Dockerfile       # バックエンドDockerの設定
├── config/              # 設定ファイルディレクトリ
│   └── global_variables.json # グローバル変数設定
├── deployment/          # デプロイメント関連の設定
├── dev_docs/            # 開発ドキュメント
├── frontend/            # Reactフロントエンド
│   ├── src/             # ソースコード
│   └── Dockerfile       # フロントエンドDockerの設定
├── logs/                # アプリケーションログ
├── scripts/             # 開発スクリプト
├── CHANGELOG.md         # バージョン更新ログ
└── README.md            # プロジェクト説明
```

## 開発ワークフロー

1. **ターミナルの使用**

   ```bash
   # コンテナ内でターミナルを開く
   # VS Code Dev Containerを使用している場合は、VS Codeのターミナルを直接使用
   ```

2. **サービスの起動**

   ```bash
   # 開発コンテナでは、フロントエンドとバックエンドのサービスが自動的に起動
   # 手動で起動する場合：
   cd /workspace/frontend && npm start
   cd /workspace/backend && python run_backend.py
   ```

3. **ログの表示**

   ```bash
   # フロントエンドログ
   tail -f /workspace/logs/frontend.log

   # バックエンドログ
   tail -f /workspace/logs/backend.log
   ```

## CI/CD デプロイメント

このプロジェクトには、GitHub Actions のワークフローが設定されており、main または master ブランチにプッシュすると、自動的に以下を実行します：

1. コードのビルドとテスト
2. Docker イメージを GitHub Container Registry にプッシュ
3. フロントエンドを GitHub Pages（該当する場合）にデプロイ

## 設定

- バックエンド設定は`backend/.env`ファイルにあります
- グローバル変数は`config/global_variables.json`に保存されています
- データベースは SQLite を使用し、`config/flow_editor.db`にあります

## バージョン管理

プロジェクトはセマンティックバージョニングを使用し、フォーマットは`メジャー.マイナー.パッチ`です

- メジャー：互換性のない API 変更を行う場合に増分
- マイナー：後方互換性のある機能を追加する場合に増分
- パッチ：後方互換性のあるバグ修正を行う場合に増分

### バージョン更新ツール

プロジェクトには、バージョン番号の更新、Git タグの作成、変更ログの更新を自動的に行うバージョン更新スクリプトが用意されています：

```bash
# パッチバージョンの更新
./scripts/update-version.sh

# マイナーバージョンの更新
./scripts/update-version.sh minor "新機能の追加"

# メジャーバージョンの更新
./scripts/update-version.sh major "メジャーアップデート"
```

### バージョン履歴

完全なバージョン履歴と変更ノートについては、[CHANGELOG.md](CHANGELOG.md)を参照してください。
