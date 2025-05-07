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
git clone https://github.com/あなたのユーザー名/visual_workflow_editor.git # あなたのリポジトリURLに置き換えてください
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
# 開発環境を起動（コンテナのビルド/再ビルドを含む）
./start-dev.sh

# コンテナを明示的に再構築（必要な場合、例：Dockerfileの変更時）
./scripts/rebuild-container.sh

# サービスのステータスを確認
./scripts/check-status.sh
```

## プロジェクト構造

```
visual_workflow_editor/
├── .devcontainer/       # Dev Container設定
├── .github/workflows/   # GitHub Actions CI/CD設定
├── backend/             # Pythonバックエンド (FastAPI)
│   ├── app/             # アプリケーションコード
│   ├── langgraphchat/   # Langchainチャット関連コード
│   ├── config/          # バックエンド固有の設定（もしあれば）
│   ├── tests/           # バックエンドテスト
│   ├── scripts/         # バックエンド固有のスクリプト（もしあれば）
│   ├── requirements.txt # Python依存関係
│   ├── run_backend.py   # バックエンド起動スクリプト
│   └── Dockerfile       # バックエンドDockerの設定
├── database/            # データベースファイル
│   └── flow_editor.db   # SQLiteデータベースファイル
├── frontend/            # Reactフロントエンド
│   ├── public/          # パブリックアセット
│   ├── src/             # ソースコード
│   ├── package.json     # Node.js依存関係
│   ├── tsconfig.json    # TypeScript設定
│   ├── craco.config.js  # Craco設定オーバーライド
│   └── Dockerfile       # フロントエンドDockerの設定
├── logs/                # アプリケーションログ
├── scripts/             # 一般的な開発スクリプト
│   ├── check-status.sh
│   ├── dev.sh           # (レガシーまたはヘルパースクリプトの可能性あり)
│   ├── local-start.sh   # (レガシーまたはヘルパースクリプトの可能性あり)
│   ├── post-create-fixed.sh # Dev Containerセットアップスクリプト
│   ├── rebuild-container.sh
│   ├── rebuild.sh       # (レガシーまたはヘルパースクリプトの可能性あり)
│   └── update-version.sh # バージョン更新スクリプト
├── .env                 # 環境変数（APIキー、DBパスなど）- **機密データはコミットしないでください**
├── .gitignore           # Git無視設定
├── start-dev.sh         # 開発環境を起動するためのメインスクリプト
├── CHANGELOG.md         # バージョン更新ログ
├── README.md            # プロジェクト説明（英語）
├── README_ja.md         # プロジェクト説明（日本語）
└── README_zh.md         # プロジェクト説明（中国語）
```

## 開発ワークフロー

1. **ターミナルの使用**

   ```bash
   # コンテナ内でターミナルを開く
   # VS Code Dev Containerを使用している場合は、VS Codeのターミナルを直接使用
   ```

2. **サービスの起動（Dev Container 内）**

   ```bash
   # 開発コンテナでは、フロントエンドとバックエンドのサービスがsupervisord経由で自動的に起動します（.devcontainer/devcontainer.json と scripts/post-create-fixed.sh を確認）
   # 手動で起動する場合（デバッグなどで必要な場合）：
   cd /workspace/frontend && npm start
   cd /workspace/backend && python run_backend.py
   ```

3. **ログの表示**

   ```bash
   # コンテナ内:
   # まず supervisord のログを確認（.devcontainer/supervisor/supervisord.conf で設定）
   tail -f /var/log/supervisor/frontend-stdout.log
   tail -f /var/log/supervisor/frontend-stderr.log
   tail -f /var/log/supervisor/backend-stdout.log
   tail -f /var/log/supervisor/backend-stderr.log

   # アプリケーション固有のログ（設定されている場合）:
   tail -f /workspace/logs/frontend.log
   tail -f /workspace/logs/backend.log
   ```

## CI/CD デプロイメント

このプロジェクトには、GitHub Actions のワークフローが設定されており、main または master ブランチにプッシュすると、自動的に以下を実行します：

1. コードのビルドとテスト
2. Docker イメージを GitHub Container Registry にプッシュ
3. フロントエンドを GitHub Pages（該当する場合）にデプロイ

## 設定

- **環境変数**: 主な設定はプロジェクトルートの `.env` ファイルで管理されます。ファイルが存在しない場合は `example.env` から作成してください。これには以下が含まれます：
  - `DATABASE_URL`: SQLite データベースへのパス（デフォルト：`sqlite:////workspace/database/flow_editor.db`）。
  - `SECRET_KEY`: バックエンドアプリケーションのシークレットキー。
  - API キー: `GOOGLE_API_KEY`, `DEEPSEEK_API_KEY`, `EMBEDDING_LMSTUDIO_API_KEY`（および関連設定）。それぞれのサービスを使用する場合は、これらを入力してください。
  - `CORS_ORIGINS`: クロスオリジンリソース共有（CORS）を許可するオリジン。
- **データベース**: SQLite を使用し、データベースファイルはデフォルトで `database/flow_editor.db` にあります（パスは `.env` で設定）。

**重要**: 機密性の高い API キーをコミットしないように、`.env` ファイルを `.gitignore` に追加してください。

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
