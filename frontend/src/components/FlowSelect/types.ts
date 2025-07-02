import { FlowData } from '../../api/flowApi';

export interface FlowSelectProps {
  open: boolean;
  onClose: () => void;
}

export interface EditDialogState {
  open: boolean;
  flow: FlowData | null;
  newName: string;
}

export interface DeleteDialogState {
  open: boolean;
  flow: FlowData | null;
}

export interface FlowItemProps {
  flow: FlowData;
  onSelect: (flowId: string | number | undefined) => void;
  onEdit: (event: React.MouseEvent, flow: FlowData) => void;
  onDelete: (event: React.MouseEvent, flow: FlowData) => void;
  onDuplicate: (event: React.MouseEvent, flow: FlowData) => void;
}

export interface SearchBarProps {
  searchTerm: string;
  onSearchChange: (term: string) => void;
  onCreateNew: () => void;
  loading: boolean;
}

export interface FlowListProps {
  flows: FlowData[];
  loading: boolean;
  error: string | null;
  searchTerm: string;
  onFlowSelect: (flowId: string | number | undefined) => void;
  onEditClick: (event: React.MouseEvent, flow: FlowData) => void;
  onDeleteClick: (event: React.MouseEvent, flow: FlowData) => void;
  onDuplicateClick: (event: React.MouseEvent, flow: FlowData) => void;
}

export interface FlowDialogsProps {
  editDialog: EditDialogState;
  deleteDialog: DeleteDialogState;
  loading: boolean;
  onEditDialogClose: () => void;
  onSaveFlowName: () => void;
  onDeleteDialogClose: () => void;
  onConfirmDelete: () => void;
  onNewFlowNameChange: (name: string) => void;
} 