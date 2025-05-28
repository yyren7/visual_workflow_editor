import { Message, Chat } from '../../types';

// Interface for messages, updated for new event structure
export interface DisplayMessage extends Message {
  type: 'text' | 'tool_status' | 'error'; // Refined types
  isStreaming?: boolean; // Indicate if assistant text message is currently streaming

  // Fields for tool status messages
  toolName?: string;
  toolInput?: any;
  toolOutputSummary?: string;
  toolStatus?: 'running' | 'completed' | 'error'; // Status of the tool call
  toolErrorMessage?: string; // Specific error message for a tool failure
}

export interface ChatInterfaceHandle {
  createNewChat: () => void;
  downloadActiveChat: () => void;
  getChatList: () => Promise<Chat[] | null>;
  renameChat: (chatId: string, newName: string) => Promise<void>;
  deleteChat: (chatId: string) => Promise<void>;
  selectChat: (chatId: string) => void;
}

export interface ChatInteractionState {
  isCreatingChat: boolean;
  canDownload: boolean;
  onActiveChatChange?: (activeChatName: string | null) => void;
  onChatInteractionStateChange?: (state: ChatInteractionState) => void; // New callback for button states
}

export interface ChatInterfaceProps {
  flowId: string | undefined;
  onChatCreated?: (newChatId: string) => void;
  onNodeSelect: (nodeId: string, position?: { x: number; y: number }) => void;
  onActiveChatChange?: (activeChatName: string | null) => void;
  onChatInteractionStateChange?: (state: ChatInteractionState) => void; // New callback for button states
}

export type { Chat };

// You might want to define specific Props for sub-components here as well
// e.g., ChatListPanelProps, ChatMessageAreaProps etc. 