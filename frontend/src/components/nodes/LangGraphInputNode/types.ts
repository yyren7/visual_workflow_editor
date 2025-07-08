export interface LangGraphInputNodeData {
  label: string;
  flowId: string;
  userInput?: string;
  currentUserRequest?: string;
}

export interface LangGraphInputNodeProps {
  id: string;
  data: LangGraphInputNodeData;
  selected: boolean;
}

export interface Task {
  name: string;
  type: string;
  description?: string;
  sub_tasks?: string[];
  details?: string[]; // 模块步骤详情
}

export interface NodeState {
  input: string;
  isEditing: boolean;
  showAddForm: boolean;
  isProcessing: boolean;
  streamingContent: string;
  processingStage: string;
  errorMessage: string | null;
}

export interface AgentStateFlags {
  isInReviewMode: boolean;
  isInErrorState: boolean;
  isInXmlApprovalMode: boolean;
  isInProcessingMode: boolean;
  isXmlGenerationComplete: boolean;
  isReadyForReview: boolean;
}

export interface ErrorRecoveryActions {
  handleResetStuckState: () => Promise<void>;
  handleForceReset: () => Promise<void>;
  handleRollbackToPrevious: () => Promise<void>;
  handleForceComplete: () => Promise<void>;
} 