import { useCallback } from 'react';
import { ErrorRecoveryActions } from './types';

export const useErrorRecovery = (
  operationChatId: string | null | undefined,
  setErrorMessage: (message: string | null) => void
): ErrorRecoveryActions => {
  
  // Reset stuck state
  const handleResetStuckState = useCallback(async () => {
    if (!operationChatId) return;
    
    try {
      const response = await fetch(`${process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000'}/sas/${operationChatId}/reset-stuck-state`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        }
      });
      
      if (response.ok) {
        console.log(`Successfully reset stuck state for flow ${operationChatId}`);
        window.location.reload();
      } else {
        console.error('Failed to reset stuck state:', response.statusText);
        setErrorMessage('重置状态失败，请刷新页面重试');
      }
    } catch (error) {
      console.error('Error resetting stuck state:', error);
      setErrorMessage('重置状态时发生错误');
    }
  }, [operationChatId, setErrorMessage]);

  // Force reset to initial state
  const handleForceReset = useCallback(async () => {
    if (!operationChatId) return;
    
    try {
      const response = await fetch(`${process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000'}/sas/${operationChatId}/force-reset-state`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        }
      });
      
      if (response.ok) {
        console.log(`Successfully force reset state for flow ${operationChatId}`);
        window.location.reload();
      } else {
        console.error('Failed to force reset state:', response.statusText);
        setErrorMessage('强制重置失败，请刷新页面重试');
      }
    } catch (error) {
      console.error('Error force resetting state:', error);
      setErrorMessage('强制重置时发生错误');
    }
  }, [operationChatId, setErrorMessage]);

  // Rollback to previous stable state
  const handleRollbackToPrevious = useCallback(async () => {
    if (!operationChatId) return;
    
    try {
      const response = await fetch(`${process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000'}/sas/${operationChatId}/rollback-to-previous`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        }
      });
      
      if (response.ok) {
        const result = await response.json();
        console.log(`Successfully rolled back state for flow ${operationChatId}:`, result.message);
        window.location.reload();
      } else {
        console.error('Failed to rollback state:', response.statusText);
        setErrorMessage('状态回退失败，请刷新页面重试');
      }
    } catch (error) {
      console.error('Error rolling back state:', error);
      setErrorMessage('状态回退时发生错误');
    }
  }, [operationChatId, setErrorMessage]);

  // Force complete current processing step
  const handleForceComplete = useCallback(async () => {
    if (!operationChatId) return;
    
    try {
      const response = await fetch(`${process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000'}/sas/${operationChatId}/force-complete-processing`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        }
      });
      
      if (response.ok) {
        console.log(`Successfully force completed processing for flow ${operationChatId}`);
        window.location.reload();
      } else {
        console.error('Failed to force complete:', response.statusText);
        setErrorMessage('强制完成失败，请刷新页面重试');
      }
    } catch (error) {
      console.error('Error force completing:', error);
      setErrorMessage('强制完成时发生错误');
    }
  }, [operationChatId, setErrorMessage]);

  return {
    handleResetStuckState,
    handleForceReset,
    handleRollbackToPrevious,
    handleForceComplete,
  };
}; 