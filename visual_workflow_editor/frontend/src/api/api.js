// frontend/src/api/api.js
import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000/api'; // Default API base URL

/**
 * Creates a new flow.
 * @param {object} flowData - The flow data to be created.
 * @returns {Promise<object>} - A promise that resolves to the created flow's ID.
 */
export const createFlow = async (flowData) => {
    try {
        const response = await axios.post(`${API_BASE_URL}/flows/`, flowData);
        return response.data;
    } catch (error) {
        console.error("Error creating flow:", error);
        throw error;
    }
};

/**
 * Retrieves a flow by its ID.
 * @param {string} flowId - The ID of the flow to retrieve.
 * @returns {Promise<object>} - A promise that resolves to the flow data.
 */
export const getFlow = async (flowId) => {
    try {
        const response = await axios.get(`${API_BASE_URL}/flows/${flowId}`);
        return response.data;
    } catch (error) {
        console.error("Error getting flow:", error);
        throw error;
    }
};

/**
 * Updates a flow by its ID.
 * @param {string} flowId - The ID of the flow to update.
 * @param {object} flowData - The updated flow data.
 * @returns {Promise<void>} - A promise that resolves when the flow is updated.
 */
export const updateFlow = async (flowId, flowData) => {
    try {
        await axios.put(`${API_BASE_URL}/flows/${flowId}`, flowData);
    } catch (error) {
        console.error("Error updating flow:", error);
        throw error;
    }
};

/**
 * Deletes a flow by its ID.
 * @param {string} flowId - The ID of the flow to delete.
 * @returns {Promise<void>} - A promise that resolves when the flow is deleted.
 */
export const deleteFlow = async (flowId) => {
    try {
        await axios.delete(`${API_BASE_URL}/flows/${flowId}`);
    } catch (error) {
        console.error("Error deleting flow:", error);
        throw error;
    }
};

/**
 * Generates a new node using the LLM.
 * @param {string} prompt - The prompt to use for generating the node.
 * @returns {Promise<object>} - A promise that resolves to the generated node data.
 */
export const generateNode = async (prompt) => {
    try {
        const response = await axios.post(`${API_BASE_URL}/llm/generate_node`, { prompt: prompt });
        return response.data;
    } catch (error) {
        console.error("Error generating node:", error);
        throw error;
    }
};

/**
 * Updates a node using the LLM.
 * @param {string} nodeId - The ID of the node to update.
 * @param {string} prompt - The prompt to use for updating the node.
 * @returns {Promise<object>} - A promise that resolves to the updated node data.
 */
export const updateNodeByLLM = async (nodeId, prompt) => {
    try {
        const response = await axios.post(`${API_BASE_URL}/llm/update_node/${nodeId}`, { prompt: prompt });
        return response.data;
    } catch (error) {
        console.error("Error updating node by LLM:", error);
        throw error;
    }
};

/**
 * Registers a new user.
 * @param {object} userData - The user data to register (username, password).
 * @returns {Promise<object>} - A promise that resolves to the registered user data.
 */
export const registerUser = async (userData) => {
    try {
        const response = await axios.post(`${API_BASE_URL}/users/register`, userData);
        return response.data;
    } catch (error) {
        console.error("Error registering user:", error);
        throw error;
    }
};

/**
 * Logs in an existing user.
 * @param {object} userData - The user data to login (username, password).
 * @returns {Promise<object>} - A promise that resolves to the login token.
 */
export const loginUser = async (userData) => {
    try {
        const response = await axios.post(`${API_BASE_URL}/users/login`, userData);
        return response.data;
    } catch (error) {
        console.error("Error logging in user:", error);
        throw error;
    }
};

/**
 * Get all flows for the current user with pagination.
 * @param {number} skip - The number of flows to skip.
 * @param {number} limit - The maximum number of flows to return.
 * @returns {Promise<Array<object>>} - A promise that resolves to the flows data.
 */
export const getFlowsForUser = async (skip = 0, limit = 10) => {
    try {
        const response = await axios.get(`${API_BASE_URL}/flows?skip=${skip}&limit=${limit}`);
        return response.data;
    } catch (error) {
        console.error("Error getting flows for user:", error);
        throw error;
    }
};
