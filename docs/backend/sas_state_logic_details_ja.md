# SAS 状態遷移と判断ロジック詳細解説

## 概要

本文書では、SAS LangGraph システムの状態遷移メカニズムと判断ロジックについて、具体的なコード例とシナリオを用いて詳細に解説します。

## 1. 状態遷移フローの詳細

### 1.1 完全な状態遷移マップ

```
[初期状態] → [タスク生成] → [レビュー] → [モジュール生成] → [レビュー] → [XML生成] → [完了]
    ↓           ↓          ↓         ↓            ↓          ↓         ↓
  initial → sas_step1_tasks_generation → sas_step1_tasks_generated
             ↓
         sas_step2_module_steps_generation → sas_step2_module_steps_generated_for_review
             ↓
         sas_all_steps_accepted_proceed_to_xml → final_xml_generated_success
```

### 1.2 各状態での具体的な判断処理

#### A. 初期化ノード（Initialize State Node）

```python
def initialize_state_node(state: RobotFlowAgentState) -> Dict[str, Any]:
    """
    状態初期化の判断ロジック：
    1. 出力ディレクトリの設定と検証
    2. 設定ファイルのマージと検証
    3. エラー状態の初期化
    """

    # 1. 出力ディレクトリの判定と設定
    provided_output_dir_str = merged_config.get("OUTPUT_DIR_PATH")
    run_output_directory_set = False

    if provided_output_dir_str:
        provided_path_obj = Path(provided_output_dir_str)

        # 判定1: ディレクトリが存在し、かつディレクトリである
        if provided_path_obj.is_dir():
            try:
                provided_path_obj.mkdir(parents=True, exist_ok=True)
                state.run_output_directory = str(provided_path_obj.resolve())
                run_output_directory_set = True
                logger.info("SUCCESS: 提供されたディレクトリを使用")
            except Exception as e_dir:
                logger.error(f"ディレクトリアクセスエラー: {e_dir}")

        # 判定2: パスが存在するがディレクトリでない
        elif provided_path_obj.exists() and not provided_path_obj.is_dir():
            logger.warning("提供されたパスはディレクトリではありません")

        # 判定3: パスが存在しない → 作成を試行
        else:
            try:
                provided_path_obj.mkdir(parents=True, exist_ok=True)
                state.run_output_directory = str(provided_path_obj.resolve())
                run_output_directory_set = True
                logger.info("SUCCESS: ディレクトリを新規作成")
            except Exception as e_create:
                logger.error(f"ディレクトリ作成失敗: {e_create}")

    # フォールバック処理
    if not run_output_directory_set:
        base_output_dir_str = merged_config.get("RUN_BASE_OUTPUT_DIR", "backend/tests/llm_sas_test")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        run_specific_dir_name = f"run_sas_subgraph_{timestamp}"
        run_output_dir = Path(base_output_dir_str) / run_specific_dir_name

        try:
            run_output_dir.mkdir(parents=True, exist_ok=True)
            state.run_output_directory = str(run_output_dir.resolve())
        except Exception as e_dir:
            state.run_output_directory = None  # クリティカル失敗
```

#### B. タスクリスト生成ノード（User Input to Task List Node）

```python
async def user_input_to_task_list_node(state: RobotFlowAgentState, llm: BaseChatModel) -> Dict[str, Any]:
    """
    タスクリスト生成の判断ロジック：
    1. ユーザー入力の解析と検証
    2. LLMを使用したタスク分解
    3. 生成されたタスクの妥当性チェック
    """

    logger.info("--- SAS Step 1: ユーザー入力からタスクリスト生成 ---")

    # 判定1: ユーザー入力の有効性チェック
    user_input = state.user_input
    if not user_input or user_input.strip() == "":
        state.is_error = True
        state.error_message = "ユーザー入力が空です"
        state.dialog_state = "error"
        return state.model_dump(exclude_none=True)

    # 判定2: 既存のタスクリストがある場合の処理
    if state.sas_step1_generated_tasks and not state.task_list_accepted:
        logger.info("既存のタスクリストが存在し、未承認状態です")
        state.dialog_state = "sas_step1_tasks_generated"
        return state.model_dump(exclude_none=True)

    try:
        # LLM呼び出しによるタスク生成
        state.dialog_state = "sas_step1_tasks_generation"
        state.current_step_description = "ユーザー入力からタスクリストを生成中..."

        task_generation_result = await llm.ainvoke(prompt_messages)

        # 判定3: LLM結果の解析
        if task_generation_result and task_generation_result.content:
            parsed_tasks = parse_task_list_from_llm_response(task_generation_result.content)

            # 判定4: 解析されたタスクの妥当性
            if parsed_tasks and len(parsed_tasks) > 0:
                state.sas_step1_generated_tasks = parsed_tasks
                state.dialog_state = "sas_step1_tasks_generated"
                state.task_list_accepted = False  # ユーザー承認待ち
                logger.info(f"SUCCESS: {len(parsed_tasks)}個のタスクを生成")
            else:
                state.is_error = True
                state.error_message = "有効なタスクを生成できませんでした"
                state.dialog_state = "error"

    except Exception as e:
        state.is_error = True
        state.error_message = f"タスク生成中にエラー: {str(e)}"
        state.dialog_state = "error"
        logger.error(f"タスク生成エラー: {e}", exc_info=True)
```

## 2. ルーティング判断の詳細ロジック

### 2.1 Review and Refine ノード後のルーティング

```python
def route_after_sas_review_and_refine(state: RobotFlowAgentState) -> str:
    """
    レビューノード後のルーティング判断：
    複数の条件を階層的に評価
    """

    logger.info("--- SAS Review/Refineノード後のルーティング判断 ---")
    logger.info(f"    is_error: {state.is_error}")
    logger.info(f"    dialog_state: '{state.dialog_state}'")
    logger.info(f"    task_list_accepted: {state.task_list_accepted}")
    logger.info(f"    module_steps_accepted: {state.module_steps_accepted}")

    # 判定1: エラー状態のチェック（最高優先度）
    if state.is_error:
        logger.error("エラー状態のため終了")
        return END

    # ユーザーの承認状態に基づいてルーティング
    if state.module_steps_accepted:
        # モジュールステップが承認された場合、XML生成へ
        return GENERATE_INDIVIDUAL_XMLS

    if state.task_list_accepted:
        # タスクリストが承認された場合、モジュールステップ生成へ
        return SAS_TASK_LIST_TO_MODULE_STEPS

    # ユーザーからのフィードバックに基づいて再生成ループへ
    if state.dialog_state == "user_input_to_task_list":
        return SAS_USER_INPUT_TO_TASK_LIST

    if state.dialog_state == "task_list_to_module_steps":
        return SAS_TASK_LIST_TO_MODULE_STEPS

    # 判定4: 明確化が必要な状態
    if state.dialog_state in ["needs_clarification", "awaiting_user_input"]:
        logger.info("ユーザー入力待ち状態 → 終了（フロントエンドで処理）")
        return END

    # 判定5: 再レビューが必要
    if (state.dialog_state in ["sas_step1_tasks_generated", "sas_step2_module_steps_generated_for_review"] and
        not (state.task_list_accepted and state.module_steps_accepted)):
        logger.info("再レビューが必要 → Review and Refineノードに戻る")
        return SAS_REVIEW_AND_REFINE

    # 判定6: 予期しない状態
    logger.warning(f"予期しない状態: {state.dialog_state}")
    return SAS_REVIEW_AND_REFINE  # 安全な選択として再レビュー
```

### 2.2 Step 2（モジュールステップ生成）後のルーティング

```python
def route_after_sas_step2(state: RobotFlowAgentState) -> str:
    """
    Step 2完了後のルーティング判断：
    モジュールステップ生成の成功/失敗に基づく分岐
    """

    logger.info("--- SAS Step 2後のルーティング判断 ---")
    logger.info(f"    is_error: {state.is_error}")
    logger.info(f"    dialog_state: '{state.dialog_state}'")

    # 判定1: エラー状態の確認
    if state.is_error:
        logger.error("Step 2でエラーが発生 → 終了")
        return END

    # 判定2: 正常完了の確認
    if state.dialog_state == "sas_step2_module_steps_generated_for_review":
        logger.info("Step 2正常完了 → レビューノードでユーザー承認待ち")
        return SAS_REVIEW_AND_REFINE

    # 判定3: 予期しない状態
    logger.warning(f"Step 2で予期しない状態: {state.dialog_state}")
    return END  # 安全のため終了
```

## 3. エラー処理と回復の判断ロジック

### 3.1 自動回復の判定アルゴリズム

```python
async def should_auto_recover_flow(thread_id, dialog_state, step_description, messages, logger):
    """
    自動回復が必要かどうかの詳細判定：
    複数のヒューリスティック規則を適用
    """

    recovery_reasons = []

    # 規則1: XML生成状態での停止判定
    if dialog_state in ['generating_xml_relation', 'generating_xml_final']:
        if not step_description or step_description.strip() == "":
            recovery_reasons.append("XML生成状態でstep_descriptionが空")

        # より詳細なチェック: 長時間停止状態
        # (実装する場合は最後更新時刻をチェック)

    # 規則2: メッセージ状態の異常判定
    if not messages:
        recovery_reasons.append("メッセージリストが空")
    elif isinstance(messages, list) and len(messages) == 0:
        recovery_reasons.append("メッセージリストが空のリスト")
    elif isinstance(messages, list) and len(messages) == 1:
        # 初期メッセージのみの場合は処理が進んでいない可能性
        recovery_reasons.append("初期メッセージのみで処理が進行していない可能性")

    # 規則3: dialog_stateとmessagesの整合性チェック
    advanced_states = [
        'sas_step2_module_steps_generated_for_review',
        'sas_all_steps_accepted_proceed_to_xml',
        'final_xml_generated_success'
    ]

    if dialog_state in advanced_states:
        if isinstance(messages, list) and len(messages) < 3:
            recovery_reasons.append("高度な状態なのにメッセージが少なすぎる")

    # 判定結果
    should_recover = len(recovery_reasons) > 0

    if should_recover:
        logger.warning(f"Flow {thread_id} の自動回復が必要: {', '.join(recovery_reasons)}")
    else:
        logger.info(f"Flow {thread_id} は正常状態です")

    return should_recover
```

### 3.2 回復戦略の選択ロジック

```python
async def auto_recover_flow(thread_id, dialog_state, logger):
    """
    状態に応じた回復戦略の選択と実行：
    状態の重要度に基づく階層的回復
    """

    logger.info(f"Flow {thread_id} の自動回復を開始 (状態: {dialog_state})")

    # 戦略1: XML生成段階での停止 → 部分完了として処理
    if dialog_state in ['generating_xml_relation', 'generating_xml_final']:
        logger.info("戦略1: XML生成停止 → 完了状態に設定")

        recovered_state = {
            'dialog_state': 'sas_step3_completed',
            'subgraph_completion_status': 'completed_success',
            'is_error': False,
            'error_message': None,
            'current_step_description': 'XML生成停止状態から自動回復',
            # 既存の final_flow_xml_path がない場合はダミーパスを設定
            'final_flow_xml_path': current_state.get('final_flow_xml_path') or
                                 f'/tmp/flow_{thread_id}_auto_recovered.xml'
        }

        await sas_app.aupdate_state(config, recovered_state)
        logger.info(f"Flow {thread_id} を {dialog_state} から完了状態に回復")

    # 戦略2: 中間段階での停止 → 安全な初期化
    elif dialog_state in [
        'sas_step1_tasks_generation',
        'sas_step2_module_steps_generation',
        'sas_generating_individual_xmls'
    ]:
        logger.info("戦略2: 中間処理停止 → 前の安定状態に戻す")

        # 現在の進行度に基づく回復
        if 'step1' in dialog_state:
            reset_state = {
                'dialog_state': 'initial',
                'task_list_accepted': False,
                'sas_step1_generated_tasks': None
            }
        elif 'step2' in dialog_state:
            reset_state = {
                'dialog_state': 'sas_step1_tasks_generated',
                'module_steps_accepted': False,
                'sas_step2_module_steps': None
            }
        else:
            reset_state = {
                'dialog_state': 'sas_step2_module_steps_generated_for_review',
                'module_steps_accepted': False
            }

        # 共通のリセット項目
        reset_state.update({
            'is_error': False,
            'error_message': None,
            'current_step_description': f'{dialog_state}停止状態から自動回復',
            'revision_iteration': current_state.get('revision_iteration', 0)
        })

        await sas_app.aupdate_state(config, reset_state)
        logger.info(f"Flow {thread_id} を {dialog_state} から安全状態に回復")

    # 戦略3: 重大な状態異常 → 完全初期化
    else:
        logger.warning("戦略3: 重大な異常 → 完全初期化")

        complete_reset_state = {
            'dialog_state': 'initial',
            'subgraph_completion_status': None,
            'is_error': False,
            'error_message': None,
            'current_step_description': '重大な異常状態から完全回復',
            'task_list_accepted': False,
            'module_steps_accepted': False,
            'revision_iteration': 0,
            'sas_step1_generated_tasks': None,
            'sas_step2_module_steps': None,
            'clarification_question': None
        }

        await sas_app.aupdate_state(config, complete_reset_state)
        logger.info(f"Flow {thread_id} を完全初期化で回復")
```

## 4. フロントエンド同期の判断ロジック

### 4.1 重要な状態変更の検出

```python
def detect_important_state_changes(final_state: dict) -> dict:
    """
    フロントエンド更新が必要な状態変更の検出：
    状態の重要度とユーザーエクスペリエンスに基づく判定
    """

    # 重要度レベル1: ユーザーアクション必須
    critical_fields = [
        'clarification_question',    # ユーザー応答が必要
        'dialog_state',             # 現在の処理段階
        'subgraph_completion_status' # 完了状態
    ]

    # 重要度レベル2: プログレス表示用
    progress_fields = [
        'sas_step1_generated_tasks',      # タスクリスト生成完了
        'sas_step2_generated_task_details', # タスク詳細生成完了
        'sas_step2_module_steps',         # モジュールステップ生成完了
        'current_step_description'        # 現在の処理説明
    ]

    # 重要度レベル3: ユーザー承認状態
    approval_fields = [
        'task_list_accepted',    # タスクリスト承認状態
        'module_steps_accepted'  # モジュールステップ承認状態
    ]

    detected_changes = {
        'critical': [],
        'progress': [],
        'approval': [],
        'needs_update': False
    }

    # 検出ロジック
    for field in critical_fields:
        if field in final_state:
            detected_changes['critical'].append(field)

    for field in progress_fields:
        if field in final_state:
            detected_changes['progress'].append(field)

    for field in approval_fields:
        if field in final_state:
            detected_changes['approval'].append(field)

    # 総合判定
    detected_changes['needs_update'] = (
        len(detected_changes['critical']) > 0 or
        len(detected_changes['progress']) > 0 or
        len(detected_changes['approval']) > 0
    )

    return detected_changes
```

### 4.2 SSE イベント配信の優先度制御

```python
class SASEventBroadcaster:
    async def broadcast_event_with_priority(self, chat_id: str, event_data: dict, priority: str = "normal"):
        """
        優先度に基づくイベント配信：
        緊急度により配信方法を調整
        """

        if chat_id not in self.chat_queues:
            logger.warning(f"キューが存在しません: {chat_id}")
            return

        try:
            if priority == "critical":
                # クリティカルイベントは既存イベントを一部削除して確実に配信
                queue = self.chat_queues[chat_id]

                # キューサイズチェック
                if queue.qsize() > 800:  # 80%で警告
                    logger.warning(f"キューサイズが大きいです ({queue.qsize()}), 古いイベントを削除")

                    # 非クリティカルイベントを削除
                    temp_events = []
                    while not queue.empty():
                        event = queue.get_nowait()
                        if event.get('priority') == 'critical':
                            temp_events.append(event)

                    # クリティカルイベントを戻す
                    for event in temp_events:
                        await queue.put(event)

                # 優先度マーク付きで配信
                event_data['priority'] = 'critical'
                await queue.put(event_data)
                logger.info(f"クリティカルイベント配信: {chat_id}")

            elif priority == "progress":
                # プログレスイベントは重複チェック
                event_data['priority'] = 'progress'

                # 同じタイプのプログレスイベントが既にある場合は置換
                queue = self.chat_queues[chat_id]
                existing_events = []
                found_duplicate = False

                while not queue.empty():
                    existing_event = queue.get_nowait()
                    if (existing_event.get('type') == event_data.get('type') and
                        existing_event.get('priority') == 'progress'):
                        found_duplicate = True
                        # 重複イベントは破棄
                        continue
                    existing_events.append(existing_event)

                # 既存イベントを戻す
                for event in existing_events:
                    await queue.put(event)

                # 新しいプログレスイベントを追加
                await queue.put(event_data)

                if found_duplicate:
                    logger.debug(f"プログレスイベント置換: {chat_id}")
                else:
                    logger.debug(f"プログレスイベント追加: {chat_id}")

            else:
                # 通常イベント
                await self.chat_queues[chat_id].put(event_data)
                logger.debug(f"通常イベント配信: {chat_id}")

        except asyncio.QueueFull:
            logger.error(f"キューが満杯です: {chat_id}, イベント破棄")
        except Exception as e:
            logger.error(f"イベント配信エラー: {chat_id}, {e}", exc_info=True)
```

## 5. パフォーマンス監視の判断基準

### 5.1 性能メトリクスの収集と評価

```python
class SASPerformanceMonitor:
    def __init__(self):
        self.metrics = {
            'checkpoint_sizes': {},      # checkpoint サイズ追跡
            'processing_times': {},      # 処理時間追跡
            'error_rates': {},          # エラー率追跡
            'recovery_counts': {}       # 回復実行回数
        }

    async def evaluate_performance_thresholds(self, thread_id: str) -> dict:
        """
        性能しきい値に基づく判定：
        リソース使用量と処理効率の評価
        """

        evaluation = {
            'status': 'healthy',
            'warnings': [],
            'critical_issues': [],
            'recommendations': []
        }

        # しきい値設定
        thresholds = {
            'max_checkpoint_size': 10 * 1024 * 1024,  # 10MB
            'max_processing_time': 300,  # 5分
            'max_error_rate': 0.1,      # 10%
            'max_recovery_per_hour': 3   # 1時間に3回
        }

        # チェックポイントサイズ評価
        if thread_id in self.metrics['checkpoint_sizes']:
            size = self.metrics['checkpoint_sizes'][thread_id]
            if size > thresholds['max_checkpoint_size']:
                evaluation['critical_issues'].append(
                    f"チェックポイントサイズが異常: {size / 1024 / 1024:.2f}MB"
                )
                evaluation['recommendations'].append(
                    "状態オブジェクトの最適化を検討してください"
                )

        # 処理時間評価
        if thread_id in self.metrics['processing_times']:
            times = self.metrics['processing_times'][thread_id]
            avg_time = sum(times) / len(times)
            if avg_time > thresholds['max_processing_time']:
                evaluation['warnings'].append(
                    f"平均処理時間が長い: {avg_time:.1f}秒"
                )

        # エラー率評価
        if thread_id in self.metrics['error_rates']:
            error_rate = self.metrics['error_rates'][thread_id]
            if error_rate > thresholds['max_error_rate']:
                evaluation['critical_issues'].append(
                    f"エラー率が高い: {error_rate * 100:.1f}%"
                )
                evaluation['status'] = 'critical'

        return evaluation
```

---

_本文書は SAS LangGraph システムの状態遷移と判断ロジックの詳細解説です。_
_更新日: 2024 年_
