export interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}

export interface Chat {
  id: number;
  flow_id: number;
  user_id: number;
  title: string;
  chat_data: {
    messages: Message[];
  };
  created_at: string;
  updated_at: string;
  metadata: {
    langchain_session_id: string;
    context_used: boolean;
    [key: string]: any;
  };
} 