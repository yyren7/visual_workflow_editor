# SAS LangGraph コンテキスト最適化・Token 精簡分析

## 概要

SAS（Structured Automation System）LangGraph システムにおけるハイブリッド生成アーキテクチャは、LLM の創造性とテンプレートエンジンの精密性を効果的に組み合わせることで、高品質なコード生成を実現しています。本文書では、各ステップにおけるコンテキスト管理と Token 精簡戦略を詳細に分析します。

## 1. 全体的な最適化戦略

### 1.1 ハイブリッドアーキテクチャの核心原理

```mermaid
graph LR
    NL[自然言語] -->|LLM| SD[構造化データ]
    SD -->|テンプレート| PC[精密コード]
```

**職責分離原則：**

- **LLM 責任**: 自然言語の解釈・翻訳・要約・推論タスク
- **テンプレート責任**: 厳密な構文が要求されるコード生成

**Token 効率化の利点：**

- プロンプト短縮化による推論コスト削減
- 処理速度の向上
- 構文正確性の 100%保証

### 1.2 状態管理による最適化

**Pydantic モデルベースの精密な状態定義：**

```python
class RobotFlowAgentState(BaseModel):
    # 必要な情報のみを厳密に定義
    current_user_request: Optional[str]  # アクティブなリクエストのみ保持
    dialog_state: Optional[Literal[...]]  # 明確な状態定義
    sas_step1_generated_tasks: Optional[List[TaskDefinition]]  # 構造化データ
```

**冗長データ除去：**

- 不要な履歴情報は自動削除
- 段階別に必要な情報のみを伝播
- 状態遷移時の自動クリーンアップ

## 2. 各ステップの詳細分析

### 2.1 initialize_state_node

**機能:** システム初期化と状態準備
**コンテキスト戦略:**

```python
def initialize_state_node(state: RobotFlowAgentState) -> Dict[str, Any]:
    # 初期化時にuser_inputをcurrent_user_requestに移動
    if state.user_input:
        state.current_user_request = state.user_input
        state.user_input = None  # 即座にクリア
```

**最適化技術:**

- 即座の入力データクリア
- 必要最小限の状態初期化
- 不要なメタデータの除去

### 2.2 user_input_to_task_list_node (sas_user_input_to_task_list)

**機能:** 自然言語をタスクリストに変換
**LLM 利用:** ✅ 創造的解釈が必要

**コンテキスト管理:**

```python
async def user_input_to_task_list_node(state: RobotFlowAgentState, llm: BaseChatModel):
    # 現在のリクエストのみを使用
    current_description_for_tasks = state.current_user_request

    # プロンプトテンプレート使用によりトークン効率化
    base_prompt_content = load_raw_prompt_file(SAS_STEP1_TASK_LIST_PROMPT_PATH)
```

**Token 精簡技術:**

- 履歴メッセージを含めない
- current_user_request のみを処理対象とする
- テンプレート化されたプロンプト使用
- 不要なコンテキスト情報の除外

**プロンプト構成:**

- タスクタイプ定義: 事前定義ファイルから読み込み
- ブロック記述: 静的知識ベース活用
- ユーザー入力: 最小限の内容のみ

### 2.3 review_and_refine_node (sas_review_and_refine)

**機能:** ユーザーフィードバックに基づく状態遷移制御
**LLM 利用:** ❌ 純粋なロジック処理

**状態遷移ロジック:**

```python
async def review_and_refine_node(state: RobotFlowAgentState):
    # コンテキストを持たない純粋な状態判定
    if state.task_list_accepted and initial_dialog_state == "sas_awaiting_task_list_review":
        state.dialog_state = "task_list_to_module_steps"
    elif state.user_input and initial_dialog_state == "sas_awaiting_task_list_review":
        state.dialog_state = "user_input_to_task_list"
```

**効率化特徴:**

- LLM 呼び出し不要
- 単純な条件分岐ロジック
- メモリ使用量最小
- 高速な状態判定

### 2.4 task_list_to_module_steps_node (sas_task_list_to_module_steps)

**機能:** 並列処理によるモジュールステップ生成
**LLM 利用:** ✅ 複雑な推論が必要

**並列処理による効率化:**

```python
async def task_list_to_module_steps_node(state: RobotFlowAgentState, llm: BaseChatModel):
    coroutines = []
    for i, task_def in enumerate(state.sas_step1_generated_tasks):
        coroutine = _generate_steps_for_single_task_async(
            task_def, llm, available_blocks_markdown, i, chat_id
        )
        coroutines.append(coroutine)

    # 並列実行でスループット向上
    results = await asyncio.gather(*coroutines, return_exceptions=True)
```

**コンテキスト制限技術:**

- タスクごとに独立したプロンプト
- 利用可能ブロック情報の事前読み込み
- タスク間の依存関係を排除
- 各タスクに最小限のコンテキストのみ提供

**プロンプト最適化:**

```python
def _get_formatted_sas_step2_user_prompt(
    task_definition: TaskDefinition,
    available_blocks_markdown: str,
    base_prompt_template: str
):
    # テンプレート + タスク定義 + ブロック情報のみ
    # 不要な履歴や状態情報は除外
```

### 2.5 generate_individual_xmls_node

**機能:** テンプレートベースの XML 生成
**LLM 利用:** ❌ 完全にテンプレートエンジン

**テンプレート精密生成:**

```python
async def _generate_xml_from_template(
    block_type: str,
    target_block_id: str,
    data_block_no_in_task: str,
    node_template_dir_str: str,
    source_description: str,
    parameters: Dict[str, Any]
):
    # LLM不使用、純粋なテンプレート処理
    # 構文精度100%保証
```

**効率化特徴:**

- LLM 呼び出し完全排除
- 事前定義 XML テンプレート活用
- パラメータマッピング処理
- 高速・決定論的な生成

### 2.6 parameter_mapping_node (sas_parameter_mapping)

**機能:** パラメータの論理-物理マッピング
**LLM 利用:** ❌ 構造化データ処理

**最適化手法:**

- 辞書ベースの高速検索
- 事前定義マッピングルール
- 構造化データ変換のみ

### 2.7 sas_merge_xmls_node

**機能:** 個別 XML ファイルの統合
**LLM 利用:** ❌ 純粋な XML 操作

**処理効率化:**

- ファイルシステム操作最適化
- ストリーミング処理
- メモリ効率的な XML 結合

### 2.8 sas_concatenate_xmls_node

**機能:** 最終 XML 連結
**LLM 利用:** ❌ 自動化されたファイル処理

**完全自動化:**

- 人間の介入不要
- 決定論的な結果
- 高速処理

## 3. コンテキスト最適化の具体的技術

### 3.1 履歴メッセージ制限

**task_router_node での実装:**

```python
for msg in context_messages[-10:]:  # 最大10メッセージに制限
    if isinstance(msg, HumanMessage):
        content = msg.content.strip() if msg.content else ""
        if content:
            context_lines.append(f"ユーザー: {content}")
```

**効果:**

- Token 使用量の予測可能な制限
- 関連性の高い近傍コンテキストの維持
- 古い情報によるノイズの除去

### 3.2 段階的情報伝播

**状態遷移でのデータクリーンアップ:**

```python
# user_inputの即座のクリア
if state.user_input:
    state.current_user_request = state.user_input
    state.user_input = None
```

**利点:**

- 不要なデータの蓄積防止
- メモリ使用量の最適化
- 状態の明確性向上

### 3.3 テンプレート化プロンプト

**静的テンプレートの活用:**

```python
base_prompt_content = load_raw_prompt_file(SAS_STEP1_TASK_LIST_PROMPT_PATH)
placeholders = {
    "TASK_TYPE_DESCRIPTIONS": task_type_descriptions_content,
    "ALLOWED_BLOCK_TYPES": block_descriptions_content
}
prompt_with_context = fill_placeholders(base_prompt_content, placeholders)
```

**効率化効果:**

- 動的プロンプト生成コストの削減
- 一貫した品質の維持
- デバッグの容易さ

### 3.4 並列処理による時間効率化

**asyncio.gather の活用:**

```python
results = await asyncio.gather(*coroutines, return_exceptions=True)
```

**スケーラビリティ:**

- I/O バウンドなタスクの並列化
- LLM 呼び出しの同時実行
- 全体処理時間の短縮

## 4. ハイブリッドアーキテクチャの利点

### 4.1 信頼性の向上

- **構文エラー**: テンプレートエンジンにより 0%
- **論理エラー**: LLM による意図理解で最小化
- **一貫性**: 事前定義ルールで保証

### 4.2 コスト効率

- **Token 使用量**: LLM を創造的タスクに限定
- **処理速度**: テンプレート処理の高速化
- **保守性**: 明確な責任分離

### 4.3 拡張性

- **新ブロック追加**: テンプレート追加のみ
- **言語サポート**: プロンプトテンプレート拡張
- **カスタマイゼーション**: 設定ベースの調整

## 5. 結論

SAS LangGraph システムのハイブリッド生成アーキテクチャは、以下の核心技術により効率的なコンテキスト管理と Token 精簡を実現しています：

1. **明確な職責分離**: LLM vs テンプレートエンジン
2. **構造化状態管理**: Pydantic モデルによる精密制御
3. **段階的処理**: 必要情報のみの伝播
4. **並列化**: I/O バウンドタスクの効率化
5. **テンプレート活用**: 決定論的な品質保証

この設計により、自然言語からの高精度なコード生成を、最小限のコストと最大限の信頼性で実現しています。
