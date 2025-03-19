import axios, { AxiosResponse } from 'axios';

// 使用环境变量配置API基础URL，如果不存在则使用默认值
const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000';

// 创建axios实例
const apiClient = axios.create({
    baseURL: API_BASE_URL
});

// 添加请求拦截器，自动附加认证token
apiClient.interceptors.request.use(
    (config) => {
        const token = localStorage.getItem('access_token');
        if (token && config.headers) {
            config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
    },
    (error) => {
        return Promise.reject(error);
    }
);

/**
 * 节点模板字段接口
 */
export interface NodeTemplateField {
  /** 字段名称 */
  name: string;
  /** 字段默认值 */
  default_value: string;
  /** 字段类型 */
  type?: string;
}

/**
 * 节点模板接口
 */
export interface NodeTemplate {
  /** 模板ID */
  id: string;
  /** 节点类型 */
  type: string;
  /** 节点标签 */
  label: string;
  /** 节点字段定义 */
  fields: NodeTemplateField[];
  /** 输入连接点 */
  inputs?: Array<{id: string, label: string, position?: number}>;
  /** 输出连接点 */
  outputs?: Array<{id: string, label: string, position?: number}>;
  /** 节点描述 */
  description: string;
  /** 节点图标 */
  icon?: string;
}

/**
 * 节点模板响应接口
 */
export interface NodeTemplatesResponse {
  [key: string]: NodeTemplate;
}

/**
 * API响应接口，包含模板数据和元数据
 */
export interface ApiNodeTemplatesResponse {
  templates: NodeTemplatesResponse;
  metadata: {
    template_count: number;
    template_dir: string;
    template_dir_exists: boolean;
    total_files?: number;
    xml_files?: number;
  };
  error?: string;
}

/**
 * 获取所有可用的节点模板
 * 从后端API获取节点模板定义
 * 
 * @returns Promise<NodeTemplatesResponse> 节点模板数据
 */
export const getNodeTemplates = async (): Promise<NodeTemplatesResponse> => {
  try {
    const response: AxiosResponse<ApiNodeTemplatesResponse> = await apiClient.get('/node-templates/');
    
    // 检查响应是否包含错误信息
    if (response.data.error) {
      console.warn("API返回错误:", response.data.error);
    }
    
    // 如果没有模板或模板为空，抛出错误
    if (!response.data.templates || Object.keys(response.data.templates).length === 0) {
      throw new Error(response.data.error || "未找到节点模板");
    }
    
    // 返回模板部分
    return response.data.templates;
  } catch (error) {
    console.error("获取节点模板失败:", error);
    throw error;
  }
}; 