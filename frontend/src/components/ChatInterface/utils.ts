import { DisplayMessage } from './types';

// Helper function to format messages to Markdown
export const formatMessagesToMarkdown = (messages: DisplayMessage[], chatName: string): string => {
  let markdown = `# Chat History: ${chatName}\n\n`;
  
  messages.forEach(message => {
    const role = message.role.charAt(0).toUpperCase() + message.role.slice(1);
    markdown += `## ${role}\n\n`;
    
    if (message.type === 'tool_status') {
      markdown += `**[Tool: ${message.toolName || 'Unknown'}]** - Status: ${message.toolStatus}`;
      if (message.toolOutputSummary) {
        markdown += `\nOutput: ${message.toolOutputSummary}`;
      }
      if (message.toolErrorMessage) {
        markdown += `\nError: ${message.toolErrorMessage}`;
      }
      markdown += '\n\n';
    } else {
      markdown += `${message.content}\n\n`;
    }
    
    markdown += '---\n\n';
  });
  
  return markdown;
};

// Helper function to trigger download
export const downloadMarkdown = (markdownContent: string, filename: string) => {
  const blob = new Blob([markdownContent], { type: 'text/markdown' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename.endsWith('.md') ? filename : `${filename}.md`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}; 