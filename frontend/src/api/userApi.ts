import axios, { AxiosResponse } from 'axios';
import { API_BASE_URL } from './apiClient'; // 导入 API_BASE_URL

// --- 数据接口定义 ---
export interface UserRegisterData {
    username: string;
    password: string;
    email?: string;
}

export interface UserLoginData {
    username: string;
    password: string;
}

export interface LoginResponse {
    access_token: string;
    token_type: string;
    user_id: string; // UUID字符串
}

// --- User 相关函数 ---

/**
 * Registers a new user.
 * @param {UserRegisterData} userData - The user data to register (username, password).
 * @returns {Promise<any>} - A promise that resolves to the registered user data.
 */
export const registerUser = async (userData: UserRegisterData): Promise<any> => {
    console.log("registerUser request:", userData);
    try {
        // 使用原始 axios 实例，因为它是不需要 token 的公共端点
        const response: AxiosResponse<any> = await axios.post(`${API_BASE_URL}/users/register`, userData, {
            withCredentials: true
        });
        return response.data;
    } catch (error) {
        console.error("Error registering user:", error);
        throw error;
    }
};

/**
 * Logs in an existing user.
 * @param {UserLoginData} userData - The user data to login (username, password).
 * @returns {Promise<LoginResponse>} - A promise that resolves to the login token.
 */
export const loginUser = async (userData: UserLoginData): Promise<LoginResponse> => {
    console.log("loginUser request:", userData);
    try {
        // 将JSON转换为表单数据格式，因为后端使用的是OAuth2PasswordRequestForm
        const formData = new URLSearchParams();
        formData.append('username', userData.username);
        formData.append('password', userData.password);

        // 使用原始 axios 实例，因为它是不需要 token 的公共端点
        const response: AxiosResponse<LoginResponse> = await axios.post(`${API_BASE_URL}/users/login`, formData, {
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            withCredentials: true
        });

        console.log('Login Response:', response.data);
        return response.data;
    } catch (error) {
        console.error("Error logging in user:", error);
        throw error;
    }
}; 