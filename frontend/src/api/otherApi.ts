import { AxiosResponse } from 'axios';
import { apiClient } from './apiClient';

/**
 * 发送邮件到指定邮箱
 * @param {string} title - 邮件标题
 * @param {string} content - 邮件内容
 * @returns {Promise<any>} - Promise，成功resolve，失败reject
 */
export const sendEmail = async (title: string, content: string): Promise<any> => {
    console.log("sendEmail request:", title, content);
    try {
        const response: AxiosResponse<any> = await apiClient.post('/email/send', {
            to: 'ren.yiyu@nidec.com', // 接收者邮箱
            subject: title,
            body: content,
        });
        return response.data;
    } catch (error) {
        console.error("Error sending email:", error);
        throw error;
    }
}; 