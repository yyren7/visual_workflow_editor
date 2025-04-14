export interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}

export interface Chat {
  id: string;
  flow_id: string;
  user_id: string;
  name: string;
  chat_data: {
    messages?: Message[];
  };
  created_at: string;
  updated_at: string;
  metadata?: {
    langchain_session_id?: string;
    context_used?: boolean;
    [key: string]: any;
  };
}

export interface User {
  id: string;
  email?: string;
  username?: string;
} 