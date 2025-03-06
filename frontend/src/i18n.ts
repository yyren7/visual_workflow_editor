// visual_workflow_editor/frontend/src/i18n.ts
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
      'common.noData': '暂无数据',
      'common.failed': '失败',
      
      // 导航栏
      'nav.flowEditor': '流程编辑器',
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
      'flowEditor.delete': '删除',
      'flowEditor.saveSuccess': '流程保存成功！',
      'flowEditor.saveError': '流程保存失败：',
      'flowEditor.loadSuccess': '流程加载成功！',
      'flowEditor.loadError': '流程加载失败：',
      'flowEditor.deleteSuccess': '流程删除成功！',
      'flowEditor.deleteError': '流程删除失败：',
      'flowEditor.noFlowToDelete': '没有要删除的流程',
      'flowEditor.invalidFlowData': '流程数据无效',
      'flowEditor.reactFlowNotInitialized': 'React Flow实例未初始化',
      'flowEditor.untitledFlow': '未命名流程',
      'flowEditor.processingDrop': '开始处理拖放...',
      'flowEditor.invalidReactFlowReference': 'ReactFlow实例或元素引用无效',
      'flowEditor.dropEventDetails': '拖放事件对象:',
      'flowEditor.droppedNodeType': '拖放的节点类型:',
      'flowEditor.nodeTypeNotFound': '未能获取到节点类型数据',
      'flowEditor.calculatedPosition': '计算的放置位置:',
      'flowEditor.nodeAddSuccess': '节点添加成功:',
      'flowEditor.flowInitialization': 'Flow初始化:',
      'flowEditor.reactFlowInstanceMethods': 'ReactFlow实例方法:',
      'flowEditor.reactFlowView': 'ReactFlow视图:',
      'flowEditor.directDragStart': '直接拖拽开始:',
      'flowEditor.chatAssistant': '对话助手',
      
      // 节点类型
      'nodeTypes.input': '输入数据节点',
      'nodeTypes.process': '数据处理节点',
      'nodeTypes.output': '输出数据节点',
      'nodeTypes.decision': '决策节点',
      'nodeTypes.unknown': '未知节点',
      'nodeTypes.dragHint': '拖拽至流程图',
      
      // 节点操作提示
      'nodeDrag.start': '拖拽开始',
      'nodeDrag.end': '拖拽结束',
      'nodeDrag.hint': '拖拽节点到流程图区域',
      'nodeDrag.hover': '拖拽悬停中...',
      
      // 节点属性面板
      'nodeProperties.title': '节点属性',
      'nodeProperties.nodeId': '节点 ID',
      'nodeProperties.nodeType': '节点类型',
      'nodeProperties.dataProperties': '数据属性',
      'nodeProperties.noNode': '未选择节点',
      
      // 全局变量
      'globalVariables.title': '全局变量',
      'globalVariables.newVariable': '新变量名称',
      'globalVariables.add': '添加',
      'globalVariables.variableValue': '变量值',
      'globalVariables.upload': '上传变量',
      'globalVariables.save': '保存变量',
      'globalVariables.loadSuccess': '全局变量加载成功！',
      'globalVariables.loadError': '解析JSON文件错误',
      'globalVariables.invalidFormat': '文件中的JSON格式无效',
      'globalVariables.readError': '读取文件错误',
      'globalVariables.saveSuccess': '全局变量保存成功！',
      'globalVariables.duplicateName': '变量名已存在',
      'globalVariables.emptyName': '请输入变量名称',
      
      // 聊天界面
      'chat.message': '消息',
      'chat.send': '发送',
      'chat.you': '您:',
      'chat.bot': '机器人:',
      'chat.invalidCommand': '无效的命令。请使用"generate node"或"update node"命令',
      'chat.invalidUpdateCommand': '无效的节点更新命令。请指定节点ID和提示信息',
      'chat.nodeGenerated': '节点生成成功！',
      'chat.nodeUpdated': '节点更新成功！',
      'chat.error': '处理消息时出错：',
      
      // 侧边栏
      'sidebar.title': '节点选择器',
      'sidebar.dragHint': '拖拽节点到流程图区域',
      
      // 提交页面
      'submit.title': '写信界面',
      'submit.description': '您可以在此页面写信并发送到指定邮箱。',
      'submit.emailTitle': '标题',
      'submit.emailContent': '内容',
      'submit.backToLogin': '返回登录',
      'submit.sendEmail': '发送邮件',
      'submit.sending': '发送中...',
      'submit.success': '邮件发送成功！',
      'submit.error': '发送邮件失败，请稍后重试',
      'submit.emptyTitle': '请输入标题',
      'submit.emptyContent': '请输入内容'
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
      'common.failed': 'Failed',
      
      // Navigation bar
      'nav.flowEditor': 'Flow Editor',
      'nav.login': 'Login',
      'nav.register': 'Register',
      'nav.logout': 'Logout',
      
      // Login page
      'login.title': 'Login',
      'login.username': 'Username',
      'login.password': 'Password',
      'login.submit': 'Login',
      'login.noAccount': 'No account? Register',
      'login.goSubmit': 'Go to Submit Page',
      'login.success': 'Login successful',
      'login.failed': 'Login failed',
      'login.tokenError': 'Login successful, but token storage failed',
      'login.noToken': 'Login successful, but no valid authentication token received',
      
      // Register page
      'register.title': 'Register',
      'register.username': 'Username',
      'register.password': 'Password',
      'register.submit': 'Register',
      'register.hasAccount': 'Already have an account? Login',
      'register.success': 'Registration successful',
      'register.failed': 'Registration failed',
      
      // Flow editor
      'flowEditor.flowName': 'Flow Name',
      'flowEditor.toggleSidebar': 'Toggle Sidebar',
      'flowEditor.nodeSelector': 'Node Selector',
      'flowEditor.addInputNode': 'Add Input Node',
      'flowEditor.addProcessNode': 'Add Process Node',
      'flowEditor.save': 'Save',
      'flowEditor.delete': 'Delete',
      'flowEditor.saveSuccess': 'Flow saved successfully!',
      'flowEditor.saveError': 'Error saving flow:',
      'flowEditor.loadSuccess': 'Flow loaded successfully!',
      'flowEditor.loadError': 'Error loading flow:',
      'flowEditor.deleteSuccess': 'Flow deleted successfully!',
      'flowEditor.deleteError': 'Error deleting flow:',
      'flowEditor.noFlowToDelete': 'No flow to delete',
      'flowEditor.invalidFlowData': 'Flow data is invalid',
      'flowEditor.reactFlowNotInitialized': 'React Flow instance not initialized',
      'flowEditor.untitledFlow': 'Untitled Flow',
      'flowEditor.processingDrop': 'Processing drop...',
      'flowEditor.invalidReactFlowReference': 'Invalid ReactFlow instance or element reference',
      'flowEditor.dropEventDetails': 'Drop event details:',
      'flowEditor.droppedNodeType': 'Dropped node type:',
      'flowEditor.nodeTypeNotFound': 'Node type data not found',
      'flowEditor.calculatedPosition': 'Calculated position:',
      'flowEditor.nodeAddSuccess': 'Node added successfully:',
      'flowEditor.flowInitialization': 'Flow initialization:',
      'flowEditor.reactFlowInstanceMethods': 'ReactFlow instance methods:',
      'flowEditor.reactFlowView': 'ReactFlow view:',
      'flowEditor.directDragStart': 'Direct drag start:',
      'flowEditor.chatAssistant': 'Chat Assistant',
      
      // Node types
      'nodeTypes.input': 'Input Data Node',
      'nodeTypes.process': 'Process Data Node',
      'nodeTypes.output': 'Output Data Node',
      'nodeTypes.decision': 'Decision Node',
      'nodeTypes.unknown': 'Unknown Node',
      'nodeTypes.dragHint': 'Drag to flow chart',
      
      // Node drag operations
      'nodeDrag.start': 'Drag started',
      'nodeDrag.end': 'Drag ended',
      'nodeDrag.hint': 'Drag node to flow area',
      'nodeDrag.hover': 'Dragging over...',
      
      // Node properties panel
      'nodeProperties.title': 'Node Properties',
      'nodeProperties.nodeId': 'Node ID',
      'nodeProperties.nodeType': 'Node Type',
      'nodeProperties.dataProperties': 'Data Properties',
      'nodeProperties.noNode': 'No node selected',
      
      // Global variables
      'globalVariables.title': 'Global Variables',
      'globalVariables.newVariable': 'New Variable Name',
      'globalVariables.add': 'Add',
      'globalVariables.variableValue': 'Variable Value',
      'globalVariables.upload': 'Upload Variables',
      'globalVariables.save': 'Save Variables',
      'globalVariables.loadSuccess': 'Global variables loaded successfully!',
      'globalVariables.loadError': 'Error parsing JSON file',
      'globalVariables.invalidFormat': 'Invalid JSON format in file',
      'globalVariables.readError': 'Error reading the file',
      'globalVariables.saveSuccess': 'Global variables saved successfully!',
      'globalVariables.duplicateName': 'Variable name already exists',
      'globalVariables.emptyName': 'Please enter a variable name',
      
      // Chat interface
      'chat.message': 'Message',
      'chat.send': 'Send',
      'chat.you': 'You:',
      'chat.bot': 'Bot:',
      'chat.invalidCommand': 'Invalid command. Please use "generate node" or "update node" command',
      'chat.invalidUpdateCommand': 'Invalid update node command. Please specify node ID and prompt',
      'chat.nodeGenerated': 'Node generated successfully!',
      'chat.nodeUpdated': 'Node updated successfully!',
      'chat.error': 'Error processing message:',
      
      // Sidebar
      'sidebar.title': 'Node Selector',
      'sidebar.dragHint': 'Drag nodes to flow area',
      
      // Submit page
      'submit.title': 'Message Interface',
      'submit.description': 'You can write and send messages to the specified email address on this page.',
      'submit.emailTitle': 'Title',
      'submit.emailContent': 'Content',
      'submit.backToLogin': 'Back to Login',
      'submit.sendEmail': 'Send Email',
      'submit.sending': 'Sending...',
      'submit.success': 'Email sent successfully!',
      'submit.error': 'Failed to send email, please try again later',
      'submit.emptyTitle': 'Please enter a title',
      'submit.emptyContent': 'Please enter content'
    }
  }
};

// 初始化配置
const initOptions: InitOptions = {
  resources,
  lng: 'en', // 默认语言
  fallbackLng: 'zh',
  interpolation: {
    escapeValue: false // 不需要对React的输入进行转义
  }
};

i18n
  .use(initReactI18next)
  .init(initOptions);

export default i18n;