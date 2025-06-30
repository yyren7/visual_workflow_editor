# SAS LangGraph Checkpoint 持久化システム詳細分析

## 概要

本文書では、SAS（Semi-Automatic Synthesis）システムにおける LangGraph の checkpoint 持久化機能について、状態管理メカニズムと判断ロジックを詳細に分析します。

## 1. アーキテクチャ概要

### 1.1 基本構成

SAS システムは以下の要素で構成されています：

```
ユーザーリクエスト → SAS Chat Router → LangGraph Workflow → PostgreSQL Checkpointer
```

### 1.2 主要コンポーネント

| コンポーネント   | 実装クラス/モジュール | 責任範囲                 |
| ---------------- | --------------------- | ------------------------ |
| Checkpointer     | AsyncPostgresSaver    | 状態の永続化とリストア   |
| State Management | RobotFlowAgentState   | ワークフロー状態の定義   |
| Router           | sas_chat.py           | API エンドポイントの提供 |
| Graph Builder    | graph_builder.py      | ワークフローグラフの構築 |

## 2. 状態管理メカニズム

### 2.1 状態の種類と遷移

SAS システムでは以下の主要な状態が管理されています：

#### A. Dialog State（対話状態）

```python
# 主要な対話状態の遷移パターン
initial → sas_step1_tasks_generation → sas_step1_tasks_generated
→ sas_step2_module_steps_generation → sas_step2_module_steps_generated_for_review
→ sas_all_steps_accepted_proceed_to_xml → final_xml_generated_success
```

**状態遷移の判断ロジック：**

- `task_list_accepted = True` → Step 2 に進む
- `module_steps_accepted = True` → XML 生成に進む
- `is_error = True` → エラー状態に遷移

#### B. Subgraph Completion Status（サブグラフ完了状態）

```python
# 完了状態の種類
"completed_success"    # 正常完了
"completed_partial"    # 部分完了（ユーザー入力待ち）
"needs_clarification"  # 明確化が必要
"error"               # エラー発生
```

### 2.2 状態持久化の実装詳細

#### A. Checkpointer 初期化プロセス

```python
# backend/app/main.py:442-480
async def initialize_checkpointer():
    # 1. データベースURL取得
    db_url = DB_CONFIG.get('DATABASE_URL')

    # 2. URLフォーマット変換（SQLAlchemy → PostgreSQL標準）
    if db_url.startswith('postgresql+psycopg2://'):
        db_url_for_checkpointer = db_url.replace('postgresql+psycopg2://', 'postgresql://')

    # 3. 非同期コンテキストマネージャー作成
    app.state.saver_context_manager = AsyncPostgresSaver.from_conn_string(db_url_for_checkpointer)

    # 4. コンテキスト開始と初期化
    app.state.checkpointer_instance = await app.state.saver_context_manager.__aenter__()
    await app.state.checkpointer_instance.setup()
```

#### B. Thread ID 管理

```python
# backend/app/routers/sas_chat.py:202
config = {"configurable": {"thread_id": chat_id}}
```

**Thread ID の役割：**

- 各チャットセッションを一意に識別
- checkpoint 状態の分離とアクセス制御
- 複数ユーザーの同時実行サポート

### 2.3 状態復元メカニズム

#### A. 状態取得 API

```python
@router.get("/sas/{chat_id}/state")
async def sas_get_state(chat_id: str, sas_app = Depends(get_sas_app)):
    config = {"configurable": {"thread_id": chat_id}}
    current_checkpoint = await sas_app.aget_state(config)
```

#### B. 状態更新 API

```python
@router.post("/sas/{chat_id}/update-state")
async def sas_update_state(chat_id: str, request: Request, sas_app = Depends(get_sas_app)):
    state_update_payload = await request.json()
    config = {"configurable": {"thread_id": chat_id}}
    updated_checkpoint = await sas_app.aupdate_state(config, state_update_payload)
```

## 3. 判断ロジックの詳細分析

### 3.1 ワークフロー制御ロジック

#### A. Review and Refine Node（レビューと改良ノード）

```python
# backend/sas/nodes/review_and_refine.py での判断ロジック

def determine_next_action(state):
    if state.task_list_accepted == False:
        # タスクリストの承認待ち
        return "present_task_list_for_review"
    elif state.module_steps_accepted == False:
        # モジュールステップの承認待ち
        return "present_module_steps_for_review"
    else:
        # 全て承認済み → 次のステップへ
        return "proceed_to_next_phase"
```

#### B. Router Functions（ルーター関数）

```python
# backend/sas/graph_builder.py でのルーティングロジック

def route_after_sas_review_refine(state: RobotFlowAgentState) -> str:
    if state.is_error:
        return END

    if state.dialog_state == "sas_step1_tasks_generated" and state.task_list_accepted:
        return SAS_PROCESS_TO_MODULE_STEPS
    elif state.dialog_state == "sas_step2_module_steps_generated_for_review" and state.module_steps_accepted:
        return SAS_PARAMETER_MAPPING
    elif state.dialog_state in ["needs_clarification", "awaiting_user_input"]:
        return END  # ユーザー入力待ち
    else:
        return SAS_REVIEW_AND_REFINE  # 再レビュー
```

### 3.2 エラー処理と回復ロジック

#### A. 自動回復判定

```python
# backend/app/main.py:220-250
async def should_auto_recover_flow(thread_id, dialog_state, step_description, messages, logger):
    # 1. XML生成状態でstep_descriptionが空の場合
    if dialog_state in ['generating_xml_relation', 'generating_xml_final']:
        if not step_description or step_description.strip() == "":
            return True

    # 2. メッセージが空または不十分な場合
    if not messages or (isinstance(messages, list) and len(messages) == 0):
        return True

    return False
```

#### B. 回復戦略の実装

```python
async def auto_recover_flow(thread_id, dialog_state, logger):
    if dialog_state in ['generating_xml_relation', 'generating_xml_final']:
        # XML生成が停止 → 完了状態に設定
        recovered_state = {
            'dialog_state': 'sas_step3_completed',
            'subgraph_completion_status': 'completed_success',
            'current_step_description': 'Auto-recovered from stuck XML generation state'
        }
    else:
        # その他の処理状態 → 初期状態にリセット
        reset_state = {
            'dialog_state': 'initial',
            'task_list_accepted': False,
            'module_steps_accepted': False,
            'revision_iteration': 0
        }
```

## 4. 性能とモニタリング

### 4.1 定期監視タスク

```python
# backend/app/main.py:140-180
async def stuck_state_monitor_task():
    while True:
        await asyncio.sleep(300)  # 5分間隔
        await check_and_recover_stuck_states(logger)
```

**監視対象の状態：**

- `generating_xml_relation`
- `generating_xml_final`
- `sas_generating_individual_xmls`
- `sas_module_steps_accepted_proceeding`

### 4.2 イベント処理システム

#### A. SSE（Server-Sent Events）ブロードキャスト

```python
# backend/app/routers/sas_chat.py:130-170
class SASEventBroadcaster:
    def __init__(self):
        self.chat_queues: Dict[str, asyncio.Queue] = {}
        self.active_connections: Dict[str, int] = defaultdict(int)

    async def broadcast_event(self, chat_id: str, event_data: dict):
        if chat_id in self.chat_queues:
            await self.chat_queues[chat_id].put(event_data)
```

#### B. 前端同期ロジック

```python
# 重要な状態変更の検出
important_fields = [
    'sas_step1_generated_tasks',
    'dialog_state',
    'subgraph_completion_status',
    'task_list_accepted',
    'module_steps_accepted'
]

# 前端更新の判定
should_sync = any(field in outputs_from_chain for field in important_fields)
```

## 5. 設定パラメータ詳細

### 5.1 データベース設定

```python
# backend/config/db_config.py
DB_CONFIG = {
    "DATABASE_URL": os.getenv("DATABASE_URL"),
    "DB_POOL_SIZE": get_env_int("DB_POOL_SIZE", "5"),
    "DB_MAX_OVERFLOW": get_env_int("DB_MAX_OVERFLOW", "10"),
    "AUTO_MIGRATE": get_env_bool("AUTO_MIGRATE", "1")
}
```

### 5.2 エラー処理設定

```python
# タイムアウト設定
SSE_TIMEOUT = 30.0  # 秒
MONITOR_INTERVAL = 300  # 5分

# キューサイズ制限
EVENT_QUEUE_MAXSIZE = 1000
```

## 6. トラブルシューティングガイド

### 6.1 一般的な問題と解決策

| 問題                   | 症状                                 | 原因                 | 解決策                     |
| ---------------------- | ------------------------------------ | -------------------- | -------------------------- |
| 状態が復元されない     | 新しいセッションで前の状態が失われる | thread_id 不一致     | chat_id 一致確認           |
| XML 生成が停止         | generating_xml 状態で進行しない      | LLM API 問題         | 自動回復機能作動           |
| メモリリーク           | 長時間実行でメモリ使用量増加         | イベントキューの蓄積 | 接続切断時のクリーンアップ |
| データベース接続エラー | checkpointer 初期化失敗              | PostgreSQL 接続問題  | DATABASE_URL 確認          |

### 6.2 デバッグ手順

1. **状態確認**

   ```bash
   curl http://localhost:8000/api/sas/{chat_id}/state
   ```

2. **ログ確認**

   ```bash
   tail -f /workspace/logs/backend.log
   ```

3. **データベース直接確認**
   ```sql
   SELECT thread_id, checkpoint->>'dialog_state'
   FROM checkpoints
   WHERE thread_id = 'target_chat_id';
   ```

## 7. 最適化と推奨事項

### 7.1 性能最適化

- Checkpoint サイズの監視（大きな state オブジェクトの最適化）
- 古い checkpoint の定期削除
- データベースインデックスの最適化

### 7.2 運用推奨事項

- 定期的なデータベースバックアップ
- モニタリングアラートの設定
- ログローテーションの実装

## 8. 今後の改善点

1. **分散処理対応**: 複数サーバー間での checkpoint 共有
2. **圧縮**: 大きな状態オブジェクトの圧縮保存
3. **キャッシング**: 頻繁にアクセスされる状態のメモリキャッシュ
4. **メトリクス**: より詳細な性能メトリクスの収集

---

_本文書は SAS LangGraph Checkpoint 持久化システムの詳細分析です。_
_更新日: 2024 年_
