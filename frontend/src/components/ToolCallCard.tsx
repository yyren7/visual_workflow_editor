import React from 'react';
import { JsonChatResponse } from '../api/chatApi';
import {
  Card, CardContent, Typography, Box, Chip, Accordion, AccordionSummary, AccordionDetails, Divider
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ErrorIcon from '@mui/icons-material/Error';
import SettingsIcon from '@mui/icons-material/Settings'; // Icon for tool call
import BuildIcon from '@mui/icons-material/Build';     // Icon for tool result

interface ToolCallCardProps {
  toolInfo: JsonChatResponse;
}

const ToolCallCard: React.FC<ToolCallCardProps> = ({ toolInfo }) => {
  const { summary, tool_calls_info, tool_results_info, error } = toolInfo;

  // Helper to render tool calls
  const renderToolCalls = (calls: Record<string, any>[]) => (
    <Box>
      {calls.map((call, index) => (
        <Box key={index} sx={{ mb: 1.5, '&:last-child': { mb: 0 } }}>
          <Chip
            icon={<SettingsIcon fontSize="small" />}
            label={`调用: ${call.tool_name || '未知工具'}`}
            size="small"
            color="primary"
            variant="outlined"
            sx={{ mb: 0.5 }}
          />
          {/* Use preformatted text for arguments if they are JSON */}
          <Typography variant="body2" component="pre" sx={{ whiteSpace: 'pre-wrap', overflowX: 'auto', bgcolor: 'grey.100', p: 1, borderRadius: 1 }}>
            {/* Attempt to pretty-print JSON */}
            {(() => {
              try {
                const args = typeof call.arguments === 'string' ? JSON.parse(call.arguments) : call.arguments;
                return JSON.stringify(args, null, 2);
              } catch {
                return String(call.arguments); // Fallback to string
              }
            })()}
          </Typography>
          {call.tool_call_id && (
            <Typography variant="caption" display="block" color="text.secondary">
              调用 ID: {call.tool_call_id}
            </Typography>
          )}
        </Box>
      ))}
    </Box>
  );

  // Helper to render tool results
  const renderToolResults = (results: Record<string, any>[]) => (
    <Box>
      {results.map((result, index) => (
        <Box key={index} sx={{ mb: 1.5, '&:last-child': { mb: 0 } }}>
          <Chip
            icon={<BuildIcon fontSize="small" />}
            label={`结果 (调用 ID: ${result.tool_call_id || 'N/A'})`}
            size="small"
            color="secondary"
            variant="outlined"
            sx={{ mb: 0.5 }}
          />
          <Typography variant="body2" component="pre" sx={{ whiteSpace: 'pre-wrap', overflowX: 'auto', bgcolor: 'grey.100', p: 1, borderRadius: 1 }}>
            {/* Attempt to pretty-print JSON if content is JSON string */}
            {(() => {
              try {
                // Check if content is a string that looks like JSON
                if (typeof result.content === 'string' && result.content.trim().startsWith('{') && result.content.trim().endsWith('}')) {
                  return JSON.stringify(JSON.parse(result.content), null, 2);
                }
                // Otherwise, display as is (could be simple string, number, etc.)
                return String(result.content);
              } catch {
                return String(result.content); // Fallback for non-JSON or invalid JSON string
              }
            })()}
          </Typography>
          {result.tool_name && (
            <Typography variant="caption" display="block" color="text.secondary">
              来自工具: {result.tool_name}
            </Typography>
          )}
        </Box>
      ))}
    </Box>
  );


  return (
    <Card variant="outlined" sx={{ borderColor: error ? 'error.main' : 'grey.300', my: 1 }}>
      <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }}> {/* Adjust padding */}
        {/* Summary Section */}
        {summary && (
          <Typography variant="body2" gutterBottom sx={{ mb: 1.5, whiteSpace: 'pre-wrap' }}>
            {summary}
          </Typography>
        )}

        {/* Error Section */}
        {error && (
          <Box sx={{ display: 'flex', alignItems: 'center', color: 'error.main', mb: 1.5 }}>
            <ErrorIcon sx={{ mr: 1 }} />
            <Typography variant="body2" fontWeight="bold">{error}</Typography>
          </Box>
        )}

        {/* Divider if summary/error exists and there are details */}
        {(summary || error) && (tool_calls_info || tool_results_info) && <Divider sx={{ my: 1 }} />}

        {/* Tool Calls Section */}
        {tool_calls_info && tool_calls_info.length > 0 && (
          <Accordion defaultExpanded={!error} sx={{ boxShadow: 'none', '&.Mui-expanded': { margin: 0 }, '&:before': { display: 'none' } }}>
            <AccordionSummary
              expandIcon={<ExpandMoreIcon />}
              aria-controls="tool-calls-content"
              id="tool-calls-header"
              sx={{ p: 0, minHeight: 'auto', '& .MuiAccordionSummary-content': { my: 0.5 } }}
            >
              <Typography variant="body2" fontWeight="medium">工具调用 ({tool_calls_info.length})</Typography>
            </AccordionSummary>
            <AccordionDetails sx={{ p: 0, pt: 1 }}>
              {renderToolCalls(tool_calls_info)}
            </AccordionDetails>
          </Accordion>
        )}

        {/* Tool Results Section */}
        {tool_results_info && tool_results_info.length > 0 && (
          <Accordion defaultExpanded={!error} sx={{ boxShadow: 'none', '&.Mui-expanded': { margin: 0 }, '&:before': { display: 'none' } }}>
            <AccordionSummary
              expandIcon={<ExpandMoreIcon />}
              aria-controls="tool-results-content"
              id="tool-results-header"
              sx={{ p: 0, minHeight: 'auto', '& .MuiAccordionSummary-content': { my: 0.5 } }}
            >
              <Typography variant="body2" fontWeight="medium">工具结果 ({tool_results_info.length})</Typography>
            </AccordionSummary>
            <AccordionDetails sx={{ p: 0, pt: 1 }}>
              {renderToolResults(tool_results_info)}
            </AccordionDetails>
          </Accordion>
        )}

        {/* Status Icon (Optional) */}
        {/* You could add a status icon at the bottom or top right */}
        {/* {!error && (tool_calls_info || tool_results_info) && (
            <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 1 }}>
                <CheckCircleIcon color="success" fontSize="small"/>
            </Box>
        )} */}
      </CardContent>
    </Card>
  );
};

export default ToolCallCard; 