import i18n from 'i18next';
import { InitOptions, Resource } from 'i18next';
import { initReactI18next } from 'react-i18next';

// 定义多语言资源
const resources: Resource = {
  zh: {
    translation: {
      // 应用程序标题和通用文本
      'app.title': '可视化工作流编辑器',
      'common.yes': '是',
      'common.no': '否',
      'common.error': '错误',
      'common.success': '成功',
      'common.unknown': '未知',
      'common.loading': '加载中...',
      'common.save': '保存',
      'common.delete': '删除',
      'common.cancel': '取消',
      'common.confirm': '确认',
      'common.back': '返回',
      'common.next': '下一步',
      'common.done': '完成',
      'common.add': '添加',
      'common.edit': '编辑',
      'common.update': '更新',
      'common.remove': '移除',
      'common.noData': '没有可用数据',

      // API错误
      'api.error': 'API错误',
      'api.requestFailed': '请求失败',
      'api.networkError': '网络错误',
      'api.timeout': '请求超时',
      'api.serverError': '服务器错误',
      'api.validationError': '验证错误',
      'api.notFound': '资源未找到',
      'api.unauthorized': '未授权',

      // 版本信息
      'version.title': '版本信息',
      'version.newAvailable': '新版本可用',
      'version.current': '当前版本',

      // 导航栏
      'nav.flowEditor': '流程编辑器',
      'nav.flowSelect': '选择流程图',
      'nav.login': '登录',
      'nav.register': '注册',
      'nav.logout': '退出登录',

      // 登录页面
      'login.title': '登录',
      'login.username': '用户名',
      'login.password': '密码',
      'login.submit': '登录',
      'login.noAccount': '没有账号？去注册',
      'login.goSubmit': '前往提交页面',
      'login.success': '登录成功',
      'login.failed': '登录失败',
      'login.tokenError': '登录成功，但令牌存储失败',
      'login.noToken': '登录成功，但未收到有效的认证令牌',

      // 注册页面
      'register.title': '注册',
      'register.username': '用户名',
      'register.password': '密码',
      'register.submit': '注册',
      'register.hasAccount': '已有账号？去登录',
      'register.success': '注册成功',
      'register.failed': '注册失败',

      // 流程编辑器
      'flowEditor.flowName': '流程名称',
      'flowEditor.toggleSidebar': '切换侧边栏',
      'flowEditor.nodeSelector': '节点选择器',
      'flowEditor.addInputNode': '添加输入节点',
      'flowEditor.addProcessNode': '添加处理节点',
      'flowEditor.save': '保存',
      'flowEditor.saveSuccess': '流程保存成功',
      'flowEditor.saveError': '保存流程图失败',
      'flowEditor.loadSuccess': '流程加载成功！',
      'flowEditor.loadError': '加载流程图失败',
      'flowEditor.deleteSuccess': '流程图已成功删除',
      'flowEditor.deleteError': '删除流程图时出错:',
      'flowEditor.noFlowToDelete': '没有流程图可以删除',
      'flowEditor.invalidFlowData': '无效的流程图数据',
      'flowEditor.reactFlowNotInitialized': 'React Flow实例未初始化',
      'flowEditor.untitledFlow': '未命名流程',
      'flowEditor.processingDrop': '开始处理拖放...',
      'flowEditor.invalidReactFlowReference': 'ReactFlow实例或元素引用无效',
      'flowEditor.dropEventDetails': '拖放事件对象:',
      'flowEditor.droppedNodeType': '放置的节点类型',
      'flowEditor.nodeTypeNotFound': '未找到节点类型',
      'flowEditor.calculatedPosition': '计算的放置位置:',
      'flowEditor.nodeAddSuccess': '节点添加成功:',
      'flowEditor.flowInitialization': 'Flow初始化:',
      'flowEditor.reactFlowInstanceMethods': 'ReactFlow实例方法:',
      'flowEditor.reactFlowView': 'ReactFlow视图:',
      'flowEditor.directDragStart': '直接拖拽开始:',
      'flowEditor.chatAssistant': '对话助手',
      'flowEditor.toggleMenu': '打开菜单',
      'flowEditor.addNode': '添加节点',
      'flowEditor.openNodeSelector': '打开节点选择器',
      'flowEditor.closeNodeSelector': '关闭节点选择器',
      'flowEditor.openGlobalVars': '打开全局变量',
      'flowEditor.closeGlobalVars': '关闭全局变量',
      'flowEditor.openChat': '打开对话助手',
      'flowEditor.closeChat': '关闭对话助手',
      'flowEditor.nodeProperties': '节点属性',
      'flowEditor.globalVariables': '全局变量',
      'flowEditor.newNode': '新节点',
      'flowEditor.deleteConfirmTitle': '确认删除流程图?',
      'flowEditor.deleteConfirmContent': '此操作无法撤销',
      'flowEditor.delete': '删除',
      'flowEditor.cancel': '取消',
      'flowEditor.permissionDenied': '没有权限访问此流程图',
      'flowEditor.nodeUpdated': '节点已更新',
      'flowEditor.nodeNotFound': '未找到节点',
      'flowEditor.edgeAdded': '已连接节点',
      'flowEditor.edgeAddedError': '连接节点失败',

      // 节点类型
      'nodeType.input': '输入节点',
      'nodeType.output': '输出节点',
      'nodeType.process': '处理节点',
      'nodeType.decision': '决策节点',
      'nodeType.generic': '通用节点',
      'nodeType.condition': '条件节点',

      // 节点属性
      'nodeProps.title': '节点属性',
      'nodeProps.id': '节点ID',
      'nodeProps.name': '名称',
      'nodeProps.description': '描述',
      'nodeProps.type': '节点类型',
      'nodeProps.save': '保存属性',
      'nodeProps.cancel': '取消',
      'nodeProps.data': '数据',
      'nodeProps.saveSuccess': '属性已保存',
      'nodeProps.saveError': '保存属性失败',

      // 全局变量
      'globalVars.title': '全局变量',
      'globalVars.name': '变量名',
      'globalVars.value': '变量值',
      'globalVars.add': '添加变量',
      'globalVars.save': '保存变量',
      'globalVars.delete': '删除变量',
      'globalVars.empty': '尚无全局变量',

      // 聊天界面
      'chat.title': '对话助手',
      'chat.placeholder': '输入您的消息...',
      'chat.send': '发送',
      'chat.generating': '生成中...',
      'chat.error': '生成节点失败',
      'chat.welcome': '欢迎！我是您的流程编辑助手。您可以告诉我您需要什么类型的节点，我会帮您生成。',

      // 命令提示
      'command.createNode': '创建一个：',
      'command.updateNode': '更新节点：',
      'command.examples': '例如：创建一个处理CSV文件的节点',
      'command.help': '输入"帮助"以查看可用命令',

      // 提交页面
      'submit.title': '提交',
      'submit.description': '您可以在此页面写信并发送到指定邮箱。',
      'submit.emailTitle': '标题',
      'submit.emailContent': '内容',
      'submit.backToLogin': '返回登录',
      'submit.sendEmail': '发送邮件',
      'submit.sending': '发送中...',
      'submit.success': '邮件发送成功！',
      'submit.error': '发送邮件失败，请稍后重试',
      'submit.emptyTitle': '请输入标题',
      'submit.emptyContent': '请输入内容',

      // 流程图选择
      'flowSelect.title': '选择流程图',
      'flowSelect.noFlows': '没有找到流程图',
      'flowSelect.error': '加载流程图失败',
      'flowSelect.updateNameSuccess': '流程图名称已更新',
      'flowSelect.updateNameError': '更新名称失败',
      'flowSelect.deleteSuccess': '流程图已删除',
      'flowSelect.deleteError': '删除流程图失败',

      // 节点选择器
      'nodeSelector.loadError': '加载节点模板失败，使用默认节点',
      'nodeSelector.noTemplates': '未找到节点模板，请检查节点模板路径',
      'nodeSelector.title': '可用节点',
      'nodeDrag.start': '开始拖拽节点',
      'nodeDrag.end': '结束拖拽节点',
      'nodeDrag.hover': '拖拽至此处放置'
    }
  },
  en: {
    translation: {
      // Application title and common text
      'app.title': 'Visual Workflow Editor',
      'common.yes': 'Yes',
      'common.no': 'No',
      'common.error': 'Error',
      'common.success': 'Success',
      'common.unknown': 'Unknown',
      'common.loading': 'Loading...',
      'common.save': 'Save',
      'common.delete': 'Delete',
      'common.cancel': 'Cancel',
      'common.confirm': 'Confirm',
      'common.back': 'Back',
      'common.next': 'Next',
      'common.done': 'Done',
      'common.add': 'Add',
      'common.edit': 'Edit',
      'common.update': 'Update',
      'common.remove': 'Remove',
      'common.noData': 'No data available',

      // API Errors
      'api.error': 'API Error',
      'api.requestFailed': 'Request Failed',
      'api.networkError': 'Network Error',
      'api.timeout': 'Request Timeout',
      'api.serverError': 'Server Error',
      'api.validationError': 'Validation Error',
      'api.notFound': 'Resource Not Found',
      'api.unauthorized': 'Unauthorized',

      // Version Info
      'version.title': 'Version Information',
      'version.newAvailable': 'New Version Available',
      'version.current': 'Current Version',

      // Navigation
      'nav.flowEditor': 'Flow Editor',
      'nav.flowSelect': 'Flow Selection',
      'nav.login': 'Login',
      'nav.register': 'Register',
      'nav.logout': 'Logout',

      // Login Page
      'login.title': 'Login',
      'login.username': 'Username',
      'login.password': 'Password',
      'login.submit': 'Login',
      'login.noAccount': 'No account? Register',
      'login.goSubmit': 'Go to Submission',
      'login.success': 'Login Successful',
      'login.failed': 'Login Failed',
      'login.tokenError': 'Login successful but token storage failed',
      'login.noToken': 'Login successful but no valid auth token received',

      // Register Page
      'register.title': 'Register',
      'register.username': 'Username',
      'register.password': 'Password',
      'register.submit': 'Register',
      'register.hasAccount': 'Already have an account? Login',
      'register.success': 'Registration Successful',
      'register.failed': 'Registration Failed',

      // Flow Editor
      'flowEditor.flowName': 'Flow Name',
      'flowEditor.toggleSidebar': 'Toggle Sidebar',
      'flowEditor.nodeSelector': 'Node Selector',
      'flowEditor.addInputNode': 'Add Input Node',
      'flowEditor.addProcessNode': 'Add Process Node',
      'flowEditor.save': 'Save',
      'flowEditor.saveSuccess': 'Flow saved successfully',
      'flowEditor.saveError': 'Failed to save flow',
      'flowEditor.loadSuccess': 'Flow loaded successfully!',
      'flowEditor.loadError': 'Failed to load flow',
      'flowEditor.deleteSuccess': 'Flow deleted successfully',
      'flowEditor.deleteError': 'Error deleting flow:',
      'flowEditor.noFlowToDelete': 'No flow to delete',
      'flowEditor.invalidFlowData': 'Invalid flow data',
      'flowEditor.reactFlowNotInitialized': 'React Flow instance not initialized',
      'flowEditor.untitledFlow': 'Untitled Flow',
      'flowEditor.processingDrop': 'Processing drop...',
      'flowEditor.invalidReactFlowReference': 'Invalid ReactFlow instance or element reference',
      'flowEditor.dropEventDetails': 'Drop event details:',
      'flowEditor.droppedNodeType': 'Dropped node type',
      'flowEditor.nodeTypeNotFound': 'Node type not found',
      'flowEditor.calculatedPosition': 'Calculated position:',
      'flowEditor.nodeAddSuccess': 'Node added successfully:',
      'flowEditor.flowInitialization': 'Flow initialization:',
      'flowEditor.reactFlowInstanceMethods': 'ReactFlow instance methods:',
      'flowEditor.reactFlowView': 'ReactFlow view:',
      'flowEditor.directDragStart': 'Direct drag start:',
      'flowEditor.chatAssistant': 'Chat Assistant',
      'flowEditor.toggleMenu': 'Open Menu',
      'flowEditor.addNode': 'Add Node',
      'flowEditor.openNodeSelector': 'Open Node Selector',
      'flowEditor.closeNodeSelector': 'Close Node Selector',
      'flowEditor.openGlobalVars': 'Open Global Variables',
      'flowEditor.closeGlobalVars': 'Close Global Variables',
      'flowEditor.openChat': 'Open Chat Assistant',
      'flowEditor.closeChat': 'Close Chat Assistant',
      'flowEditor.nodeProperties': 'Node Properties',
      'flowEditor.globalVariables': 'Global Variables',
      'flowEditor.newNode': 'New Node',
      'flowEditor.deleteConfirmTitle': 'Delete Flow?',
      'flowEditor.deleteConfirmContent': 'This action cannot be undone',
      'flowEditor.delete': 'Delete',
      'flowEditor.cancel': 'Cancel',
      'flowEditor.permissionDenied': 'Permission denied to access this flow',
      'flowEditor.nodeUpdated': 'Node updated successfully!',
      'flowEditor.nodeNotFound': 'Node not found',
      'flowEditor.edgeAdded': 'Edge added successfully',
      'flowEditor.edgeAddedError': 'Failed to add edge',

      // Node Types
      'nodeType.input': 'Input Node',
      'nodeType.output': 'Output Node',
      'nodeType.process': 'Process Node',
      'nodeType.decision': 'Decision Node',
      'nodeType.generic': 'Generic Node',
      'nodeType.condition': 'Condition Node',

      // Node Properties
      'nodeProps.title': 'Node Properties',
      'nodeProps.id': 'Node ID',
      'nodeProps.name': 'Name',
      'nodeProps.description': 'Description',
      'nodeProps.type': 'Node Type',
      'nodeProps.save': 'Save Properties',
      'nodeProps.cancel': 'Cancel',
      'nodeProps.data': 'Data',
      'nodeProps.saveSuccess': 'Properties saved',
      'nodeProps.saveError': 'Failed to save properties',

      // Global Variables
      'globalVars.title': 'Global Variables',
      'globalVars.name': 'Variable Name',
      'globalVars.value': 'Variable Value',
      'globalVars.add': 'Add Variable',
      'globalVars.save': 'Save Variables',
      'globalVars.delete': 'Delete Variable',
      'globalVars.empty': 'No global variables yet',

      // Chat Interface
      'chat.title': 'Chat Assistant',
      'chat.placeholder': 'Type your message...',
      'chat.send': 'Send',
      'chat.generating': 'Generating...',
      'chat.error': 'Failed to generate node',
      'chat.welcome': 'Welcome! I am your flow editing assistant. You can tell me what type of node you need, and I\'ll help you generate it.',

      // Command Prompts
      'command.createNode': 'Create a:',
      'command.updateNode': 'Update node:',
      'command.examples': 'Examples: Create a node to process CSV files',
      'command.help': 'Type "help" to see available commands',

      // Submit Page
      'submit.title': 'Submit',
      'submit.description': 'You can write and send email to specified address on this page.',
      'submit.emailTitle': 'Title',
      'submit.emailContent': 'Content',
      'submit.backToLogin': 'Back to Login',
      'submit.sendEmail': 'Send Email',
      'submit.sending': 'Sending...',
      'submit.success': 'Email sent successfully!',
      'submit.error': 'Failed to send email, please try again later',
      'submit.emptyTitle': 'Please enter title',
      'submit.emptyContent': 'Please enter content',

      // Flow Selection
      'flowSelect.title': 'Select Flow',
      'flowSelect.noFlows': 'No flows found',
      'flowSelect.error': 'Failed to load flows',
      'flowSelect.updateNameSuccess': 'Flow name updated',
      'flowSelect.updateNameError': 'Failed to update name',
      'flowSelect.deleteSuccess': 'Flow deleted',
      'flowSelect.deleteError': 'Failed to delete flow',

      // Node Selector
      'nodeSelector.loadError': 'Failed to load node templates, using defaults',
      'nodeSelector.noTemplates': 'No node templates found, please check template path',
      'nodeSelector.title': 'Available Nodes',
      'nodeDrag.start': 'Started dragging node',
      'nodeDrag.end': 'Ended dragging node',
      'nodeDrag.hover': 'Drop here to place'
    }
  },
  ja: {
    translation: {
      // アプリケーションタイトルと一般的なテキスト
      'app.title': 'ビジュアルワークフローエディタ',
      'common.yes': 'はい',
      'common.no': 'いいえ',
      'common.error': 'エラー',
      'common.success': '成功',
      'common.unknown': '不明',
      'common.loading': '読み込み中...',
      'common.save': '保存',
      'common.delete': '削除',
      'common.cancel': 'キャンセル',
      'common.confirm': '確認',
      'common.back': '戻る',
      'common.next': '次へ',
      'common.done': '完了',
      'common.add': '追加',
      'common.edit': '編集',
      'common.update': '更新',
      'common.remove': '削除',
      'common.noData': '利用可能なデータがありません',

      // APIエラー
      'api.error': 'APIエラー',
      'api.requestFailed': 'リクエスト失敗',
      'api.networkError': 'ネットワークエラー',
      'api.timeout': 'リクエストタイムアウト',
      'api.serverError': 'サーバーエラー',
      'api.validationError': '検証エラー',
      'api.notFound': 'リソースが見つかりません',
      'api.unauthorized': '権限がありません',

      // バージョン情報
      'version.title': 'バージョン情報',
      'version.newAvailable': '新しいバージョンが利用可能です',
      'version.current': '現在のバージョン',

      // ナビゲーション
      'nav.flowEditor': 'フローエディタ',
      'nav.flowSelect': 'フロー選択',
      'nav.login': 'ログイン',
      'nav.register': '登録',
      'nav.logout': 'ログアウト',

      // フローエディタ
      'flowEditor.flowName': 'フロー名',
      'flowEditor.toggleSidebar': 'サイドバー切替',
      'flowEditor.nodeSelector': 'ノードセレクタ',
      'flowEditor.addInputNode': '入力ノードを追加',
      'flowEditor.addProcessNode': '処理ノードを追加',
      'flowEditor.save': '保存',
      'flowEditor.saveSuccess': 'フローの保存に成功しました！',
      'flowEditor.saveError': 'フローの保存中にエラーが発生しました：',
      'flowEditor.loadSuccess': 'フローの読み込みに成功しました！',
      'flowEditor.loadError': 'フローの読み込みに失敗しました',
      'flowEditor.deleteSuccess': 'フローが正常に削除されました',
      'flowEditor.deleteError': 'フロー削除中にエラーが発生しました：',
      'flowEditor.noFlowToDelete': '削除するフローがありません',
      'flowEditor.invalidFlowData': '無効なフローデータ',
      'flowEditor.reactFlowNotInitialized': 'React Flowインスタンスが初期化されていません',
      'flowEditor.untitledFlow': '無題のフロー',
      'flowEditor.processingDrop': 'ドロップを処理中...',
      'flowEditor.invalidReactFlowReference': '無効なReactFlowインスタンスまたは要素参照',
      'flowEditor.dropEventDetails': 'ドロップイベントの詳細：',
      'flowEditor.droppedNodeType': 'ドロップされたノードタイプ：',
      'flowEditor.nodeTypeNotFound': 'ノードタイプが見つかりません',
      'flowEditor.calculatedPosition': '計算された位置：',
      'flowEditor.nodeAddSuccess': 'ノードが正常に追加されました：',
      'flowEditor.chatAssistant': 'チャットアシスタント',
      'flowEditor.toggleMenu': 'メニューを開く',
      'flowEditor.addNode': 'ノードを追加',
      'flowEditor.openNodeSelector': 'ノードセレクタを開く',
      'flowEditor.closeNodeSelector': 'ノードセレクタを閉じる',
      'flowEditor.openGlobalVars': 'グローバル変数を開く',
      'flowEditor.closeGlobalVars': 'グローバル変数を閉じる',
      'flowEditor.openChat': 'チャットアシスタントを開く',
      'flowEditor.closeChat': 'チャットアシスタントを閉じる',
      'flowEditor.nodeProperties': 'ノードプロパティ',
      'flowEditor.globalVariables': 'グローバル変数',
      'flowEditor.newNode': '新しいノード',
      'flowEditor.deleteConfirmTitle': 'フローを削除しますか？',
      'flowEditor.deleteConfirmContent': 'この操作は元に戻せません',
      'flowEditor.delete': '削除',
      'flowEditor.cancel': 'キャンセル',
      'flowEditor.permissionDenied': 'このフローにアクセスする権限がありません',
      'flowEditor.nodeUpdated': 'ノードが更新されました',
      'flowEditor.nodeNotFound': 'ノードが見つかりません',
      'flowEditor.edgeAdded': 'エッジが正常に追加されました',
      'flowEditor.edgeAddedError': 'エッジの追加に失敗しました',

      // ノードタイプ
      'nodeType.input': '入力ノード',
      'nodeType.output': '出力ノード',
      'nodeType.process': '処理ノード',
      'nodeType.decision': '決定ノード',
      'nodeType.generic': '一般ノード',
      'nodeType.condition': '条件ノード',

      // ノードプロパティ
      'nodeProps.title': 'ノードプロパティ',
      'nodeProps.id': 'ノードID',
      'nodeProps.name': '名前',
      'nodeProps.description': '説明',
      'nodeProps.type': 'ノードタイプ',
      'nodeProps.save': 'プロパティを保存',
      'nodeProps.cancel': 'キャンセル',
      'nodeProps.data': 'データ',
      'nodeProps.saveSuccess': 'プロパティが保存されました',
      'nodeProps.saveError': 'プロパティの保存に失敗しました',

      // グローバル変数
      'globalVars.title': 'グローバル変数',
      'globalVars.name': '変数名',
      'globalVars.value': '変数値',
      'globalVars.add': '変数を追加',
      'globalVars.save': '変数を保存',
      'globalVars.delete': '変数を削除',
      'globalVars.empty': 'グローバル変数はまだありません',

      // チャットインターフェース
      'chat.title': 'チャットアシスタント',
      'chat.placeholder': 'メッセージを入力...',
      'chat.send': '送信',
      'chat.generating': '生成中...',
      'chat.error': 'ノードの生成に失敗しました',
      'chat.welcome': 'ようこそ！フロー編集アシスタントです。必要なノードのタイプを教えていただければ、生成をお手伝いします。',

      // コマンドプロンプト
      'command.createNode': '作成：',
      'command.updateNode': 'ノードを更新：',
      'command.examples': '例：CSVファイルを処理するノードを作成',
      'command.help': '利用可能なコマンドを見るには「ヘルプ」と入力してください',

      // ノードセレクタ
      'nodeSelector.loadError': 'ノードテンプレートの読み込みに失敗しました、デフォルトを使用します',
      'nodeSelector.noTemplates': 'ノードテンプレートが見つかりません、テンプレートパスを確認してください',
      'nodeSelector.title': '利用可能なノード',
      'nodeDrag.start': 'ノードのドラッグを開始しました',
      'nodeDrag.end': 'ノードのドラッグを終了しました',
      'nodeDrag.hover': 'ここにドロップして配置'
    }
  }
};

// 初期化オプション
const i18nOptions: InitOptions = {
  resources,
  lng: 'zh', // 默认语言
  fallbackLng: 'en', // 当当前语言不存在时使用的后备语言
  interpolation: {
    escapeValue: false // 允许在翻译中使用HTML
  }
};

// 初始化i18n
i18n.use(initReactI18next).init(i18nOptions);

export default i18n;