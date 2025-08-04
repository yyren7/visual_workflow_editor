import axios, { AxiosInstance, InternalAxiosRequestConfig, AxiosResponse, AxiosError } from 'axios';

// 使用环境变量配置API基础URL，如果不存在则使用默认值
export const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000';

// 创建axios实例
export const apiClient: AxiosInstance = axios.create({
    baseURL: API_BASE_URL,
    withCredentials: true  // 添加凭证支持
});

// 添加请求拦截器，自动附加认证token
apiClient.interceptors.request.use(
    (config: InternalAxiosRequestConfig): InternalAxiosRequestConfig => {
        const token = localStorage.getItem('access_token');

        // 排除不需要token的公开API路径
        const publicPaths = ['/users/login', '/users/register'];
        const isPublicPath = publicPaths.some(path => config.url?.includes(path));

        if (!isPublicPath) {
            if (!token) {
                console.warn(`API请求 ${config.url} 需要认证但未找到token`);
            } else {
                console.log(`为请求 ${config.url} 添加认证token`);
                if (config.headers) {
                    config.headers.Authorization = `Bearer ${token}`;
                }
            }
        }

        return config;
    },
    (error: any) => {
        console.error('请求拦截器错误:', error);
        return Promise.reject(error);
    }
);

// 添加响应拦截器，处理认证错误
apiClient.interceptors.response.use(
    (response: AxiosResponse) => {
        return response;
    },
    (error: AxiosError) => {
        // 处理401未授权错误
        if (error.response && error.response.status === 401) {
            console.error('认证失败 (401):', error.config?.url);

            // 可以在这里触发重新认证或跳转到登录页面
            // 如果不是登录请求本身导致的401，可以清除token
            if (!error.config?.url?.includes('/users/login')) {
                console.warn('检测到认证过期，清除token');
                localStorage.removeItem('access_token');

                // 发布认证状态变更事件
                window.dispatchEvent(new Event('loginChange'));
            }
        }

        return Promise.reject(error);
    }
); 