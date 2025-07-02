export interface ChatInterfaceProps {
  flowId: string | undefined;
  onNodeSelect: (nodeId: string, position?: { x: number; y: number }) => void;
  onActiveChatChange?: (chatName: string | null) => void;
  onChatInteractionStateChange?: (state: ChatInteractionState) => void;
}

export interface ChatInterfaceHandle {
  createNewChat: () => Promise<void>;
  downloadActiveChat: () => void;
  getChatList: () => Promise<any>;
  renameChat: (chatId: string, newName: string) => Promise<void>;
  deleteChat: (chatId: string) => void;
  selectChat: (chatId: string) => void;
}

export interface ChatInteractionState {
  isCreatingChat: boolean;
  canDownload: boolean;
}

export interface DisplayMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  type: 'text' | 'tool_status' | 'error';
  isStreaming?: boolean;
  
  // Fields for tool status messages
  toolName?: string;
  toolInput?: any;
  toolOutputSummary?: string;
  toolStatus?: 'running' | 'completed' | 'error';
  toolErrorMessage?: string;
}

export interface ChatState {
  chatList: any[];
  activeChatId: string | null;
  messages: DisplayMessage[];
  inputMessage: string;
  isLoadingList: boolean;
  isLoadingChat: boolean;
  isSending: boolean;
  isCreatingChat: boolean;
  isDeletingChatId: string | null;
  isRenamingChatId: string | null;
  renameInputValue: string;
  error: string | null;
  showDeleteConfirm: boolean;
  chatToDelete: string | null;
  editingMessageTimestamp: string | null;
  editingMessageContent: string;
}

export interface SSEHandlerState {
  streamingAssistantMsgIdRef: React.MutableRefObject<string | null>;
  closeEventSourceRef: React.MutableRefObject<(() => void) | null>;
} 