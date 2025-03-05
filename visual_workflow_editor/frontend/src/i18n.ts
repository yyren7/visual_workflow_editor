import i18n from 'i18next';
import { InitOptions, Resource } from 'i18next';
import { initReactI18next } from 'react-i18next';

// 定义多语言资源
const resources: Resource = {
  zh: {
    translation: {
      'app.title': '可视化工作流编辑器',
      'sidebar.nodeSelector': '节点选择器',
      'sidebar.properties': '属性',
      'sidebar.globalVariables': '全局变量',
      'chat.placeholder': '输入自然语言指令来生成或修改节点...',
      'chat.send': '发送',
      'flow.save': '保存流程',
      'flow.load': '加载流程',
      'login.username': '用户名',
      'login.password': '密码',
      'login.submit': '登录',
      'register.submit': '注册',
    }
  },
  en: {
    translation: {
      'app.title': 'Visual Workflow Editor',
      'sidebar.nodeSelector': 'Node Selector',
      'sidebar.properties': 'Properties',
      'sidebar.globalVariables': 'Global Variables',
      'chat.placeholder': 'Enter natural language instructions to generate or modify nodes...',
      'chat.send': 'Send',
      'flow.save': 'Save Flow',
      'flow.load': 'Load Flow',
      'login.username': 'Username',
      'login.password': 'Password',
      'login.submit': 'Login',
      'register.submit': 'Register',
    }
  }
};

// 初始化配置
const initOptions: InitOptions = {
  resources,
  lng: 'zh', // 默认语言
  fallbackLng: 'en',
  interpolation: {
    escapeValue: false // 不需要对React的输入进行转义
  }
};

i18n
  .use(initReactI18next)
  .init(initOptions);

export default i18n;