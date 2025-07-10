import logging
import yaml
import re
from typing import Dict, Any, List, Tuple, Optional, Set
from pathlib import Path

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, AIMessage

from ..state import RobotFlowAgentState

logger = logging.getLogger(__name__)

# Parameter file paths
SYNCED_FILES_DIR = "/workspace/backend/langgraphchat/synced_files"
TEACHING_FILE_PATH = f"{SYNCED_FILES_DIR}/teaching.yaml"
NUMBER_PARAM_FILE_PATH = f"{SYNCED_FILES_DIR}/number_parameter.yaml"
FLAG_PARAM_FILE_PATH = f"{SYNCED_FILES_DIR}/flag_parameter.yaml"

class ParameterMapper:
    """
    Handles mapping of logical parameters from step 2 to actual parameter file slots.
    """
    
    def __init__(self):
        self.teaching_data = None
        self.number_data = None
        self.flag_data = None
        self.load_parameter_files()
    
    def load_parameter_files(self):
        """Load all parameter files into memory."""
        try:
            with open(TEACHING_FILE_PATH, 'r', encoding='utf-8') as f:
                self.teaching_data = yaml.safe_load(f)
            logger.info(f"Loaded teaching.yaml with {len(self.teaching_data)} points")
        except Exception as e:
            logger.error(f"Failed to load teaching.yaml: {e}")
            self.teaching_data = {}
        
        try:
            with open(NUMBER_PARAM_FILE_PATH, 'r', encoding='utf-8') as f:
                self.number_data = yaml.safe_load(f)
            logger.info(f"Loaded number_parameter.yaml with {len(self.number_data)} numbers")
        except Exception as e:
            logger.error(f"Failed to load number_parameter.yaml: {e}")
            self.number_data = {}
        
        try:
            with open(FLAG_PARAM_FILE_PATH, 'r', encoding='utf-8') as f:
                self.flag_data = yaml.safe_load(f)
            logger.info(f"Loaded flag_parameter.yaml with {len(self.flag_data)} flags")
        except Exception as e:
            logger.error(f"Failed to load flag_parameter.yaml: {e}")
            self.flag_data = {}
    
    def extract_parameters_from_module_steps(self, module_steps: str) -> Dict[str, Set[str]]:
        """
        Extract logical parameters mentioned in the module steps.
        Now focuses on semantic point descriptions rather than just P1, P21 format.
        
        Returns:
            Dict with keys 'semantic_points', 'numbers', 'flags' and sets of parameter names as values
        """
        extracted = {
            'semantic_points': set(),
            'numbers': set(), 
            'flags': set()
        }
        
        # Extract semantic point descriptions (looking for descriptive point references)
        # Common patterns in step2 output: "initial/safe point", "standby point", "precise grasping point", etc.
        import re
        
        # Look for point descriptions in parentheses or quotes
        semantic_point_patterns = [
            r'"([^"]*point[^"]*)"',  # "initial/safe point"
            r'"([^"]*Point[^"]*)"',  # "Initial Point" 
            r'\*\*([^*]*point[^*]*)\*\*',  # **standby point**
            r'\(([^)]*point[^)]*)\)',  # (safe point)
            r'to\s+([a-zA-Z_][a-zA-Z0-9_\s]*point)(?:\s|$|\.)',  # to bearing standby point
            r'at\s+([a-zA-Z_][a-zA-Z0-9_\s]*point)(?:\s|$|\.)',  # at initial point
            r'Move to\s+([a-zA-Z_][a-zA-Z0-9_\s]*point)(?:\s|$|\.)',  # Move to safe point
        ]
        
        for pattern in semantic_point_patterns:
            matches = re.findall(pattern, module_steps, re.IGNORECASE)
            for match in matches:
                # Clean up the match
                clean_point = match.strip().lower()
                # Remove common prefixes/suffixes
                clean_point = re.sub(r'^(the\s+|a\s+|an\s+)', '', clean_point)
                clean_point = re.sub(r'\s*\([^)]*\)$', '', clean_point)  # Remove trailing parentheses
                clean_point = re.sub(r'\s+', ' ', clean_point)  # Normalize spaces
                
                if clean_point and 'point' in clean_point and len(clean_point.split()) >= 2:
                    extracted['semantic_points'].add(clean_point)
        
        # Also extract traditional P1, P21 format for backward compatibility
        point_pattern = r'\bP(\d+)\b'
        points = re.findall(point_pattern, module_steps)
        for p in points:
            extracted['semantic_points'].add(f"P{p}")
        
        # Extract number variable references (N5, N483, etc.)
        number_pattern = r'\bN(\d+)\b'
        numbers = re.findall(number_pattern, module_steps)
        extracted['numbers'].update(f"N{n}" for n in numbers)
        
        # Extract flag variable references (F1, F2, etc.)
        flag_pattern = r'\bF(\d+)\b'
        flags = re.findall(flag_pattern, module_steps)
        extracted['flags'].update(f"F{f}" for f in flags)
        
        logger.info(f"Extracted parameters: Semantic Points={len(extracted['semantic_points'])}, Numbers={len(extracted['numbers'])}, Flags={len(extracted['flags'])}")
        logger.info(f"Semantic Points: {sorted(extracted['semantic_points'])}")
        logger.info(f"Numbers: {sorted(extracted['numbers'])}")
        logger.info(f"Flags: {sorted(extracted['flags'])}")
        
        return extracted

    def find_semantic_point_match(self, semantic_point: str) -> Optional[str]:
        """
        Find an existing point in teaching.yaml that matches the semantic description.
        
        Args:
            semantic_point: Semantic description like "initial point", "safe point", etc.
            
        Returns:
            Point ID (like "P1") if found, None otherwise
        """
        if not self.teaching_data:
            return None
            
        # Normalize the semantic point for comparison
        normalized_target = self.normalize_semantic_name(semantic_point)
        
        # Search through existing points
        for point_id, point_data in self.teaching_data.items():
            if isinstance(point_data, dict):
                existing_name = point_data.get('name', '').strip()
                if existing_name:
                    normalized_existing = self.normalize_semantic_name(existing_name)
                    
                    # Check for exact match
                    if normalized_existing == normalized_target:
                        logger.info(f"Found exact semantic match: '{semantic_point}' -> {point_id} ('{existing_name}')")
                        return point_id
                    
                    # Check for partial matches (contains key words)
                    target_words = set(normalized_target.split())
                    existing_words = set(normalized_existing.split())
                    
                    # If they share significant words, consider it a match
                    common_words = target_words & existing_words
                    if common_words and len(common_words) >= min(2, len(target_words)):
                        logger.info(f"Found semantic match: '{semantic_point}' -> {point_id} ('{existing_name}') [shared: {common_words}]")
                        return point_id
        
        return None

    def normalize_semantic_name(self, name: str) -> str:
        """
        Normalize semantic names for comparison.
        """
        # Convert to lowercase and remove extra spaces
        normalized = name.lower().strip()
        
        # Remove common words that don't add semantic meaning
        stop_words = {'the', 'a', 'an', 'to', 'at', 'in', 'on', 'for', 'of', 'with'}
        words = normalized.split()
        words = [w for w in words if w not in stop_words]
        
        # Handle common synonyms
        synonyms = {
            'initial': 'home',
            'start': 'home', 
            'beginning': 'home',
            'safe': 'home',
            'default': 'home',
            'standby': 'wait',
            'approach': 'near',
            'departure': 'exit',
            'precise': 'exact',
            'accurate': 'exact'
        }
        
        # Replace synonyms
        words = [synonyms.get(w, w) for w in words]
        
        return ' '.join(words)

    def find_available_slots(self, param_type: str, needed_count: int) -> List[str]:
        """
        Find available slots in the parameter files.
        
        Args:
            param_type: 'points', 'numbers', or 'flags'
            needed_count: Number of slots needed
            
        Returns:
            List of available slot names
        """
        available_slots = []
        
        if param_type == 'points':
            data = self.teaching_data
            for key, value in data.items():
                if isinstance(value, dict) and value.get('name', '').strip() == '':
                    # Empty name indicates available slot
                    available_slots.append(key)
                    if len(available_slots) >= needed_count:
                        break
        
        elif param_type == 'numbers':
            data = self.number_data
            for key, value in data.items():
                if isinstance(value, dict) and value.get('name', '').strip() == '':
                    # Empty name indicates available slot
                    available_slots.append(key)
                    if len(available_slots) >= needed_count:
                        break
        
        elif param_type == 'flags':
            data = self.flag_data
            for key, value in data.items():
                if isinstance(value, dict) and value.get('name', '').strip() == '':
                    # Empty name indicates available slot
                    available_slots.append(key)
                    if len(available_slots) >= needed_count:
                        break
        
        logger.info(f"Found {len(available_slots)} available slots for {param_type} (needed: {needed_count})")
        return available_slots
    
    def create_parameter_mapping(self, extracted_params: Dict[str, Set[str]]) -> Dict[str, Dict[str, str]]:
        """
        Create mapping from semantic parameters to actual parameter slots.
        
        Returns:
            Dict with structure: {'points': {'initial point': 'P1', 'standby point': 'P7'}, 'numbers': {...}, 'flags': {...}}
        """
        mapping = {'points': {}, 'numbers': {}, 'flags': {}}
        
        # Track used slots to prevent conflicts
        used_point_slots = set()
        
        # Map semantic points
        semantic_points = sorted(extracted_params['semantic_points'])
        for semantic_point in semantic_points:
            # First try to find existing semantic match
            existing_match = self.find_semantic_point_match(semantic_point)
            
            if existing_match and existing_match not in used_point_slots:
                mapping['points'][semantic_point] = existing_match
                used_point_slots.add(existing_match)
                logger.info(f"Mapped '{semantic_point}' to existing point {existing_match}")
            else:
                # Find an available slot for new semantic point
                available_slots = self.find_available_slots('points', 1)
                # Filter out already used slots
                available_slots = [slot for slot in available_slots if slot not in used_point_slots]
                
                if available_slots:
                    new_slot = available_slots[0]
                    mapping['points'][semantic_point] = new_slot
                    used_point_slots.add(new_slot)
                    logger.info(f"Assigned new slot {new_slot} for semantic point '{semantic_point}'")
                else:
                    logger.warning(f"No available slot for semantic point '{semantic_point}'")
        
        # Map numbers
        logical_numbers = sorted(extracted_params['numbers'])
        available_number_slots = self.find_available_slots('numbers', len(logical_numbers))
        
        for i, logical_number in enumerate(logical_numbers):
            if i < len(available_number_slots):
                mapping['numbers'][logical_number] = available_number_slots[i]
            else:
                logger.warning(f"No available slot for logical number {logical_number}")
        
        # Map flags
        logical_flags = sorted(extracted_params['flags'])
        available_flag_slots = self.find_available_slots('flags', len(logical_flags))
        
        for i, logical_flag in enumerate(logical_flags):
            if i < len(available_flag_slots):
                mapping['flags'][logical_flag] = available_flag_slots[i]
            else:
                logger.warning(f"No available slot for logical flag {logical_flag}")
        
        return mapping
    
    def update_parameter_files(self, mapping: Dict[str, Dict[str, str]], extracted_params: Dict[str, Set[str]]) -> bool:
        """
        Update parameter files with assigned names for mapped slots.
        For semantic points, update the name field with the semantic description.
        
        Args:
            mapping: Parameter mapping from create_parameter_mapping
            extracted_params: Extracted parameters for context
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Update teaching.yaml with semantic point names
            if mapping['points']:
                for semantic_point, actual_slot in mapping['points'].items():
                    if actual_slot in self.teaching_data:
                        # For semantic points, use the semantic description as the name
                        # unless it's already set (existing match case)
                        current_name = self.teaching_data[actual_slot].get('name', '').strip()
                        if not current_name:
                            # This is a new assignment, use the semantic description
                            self.teaching_data[actual_slot]['name'] = semantic_point
                            logger.info(f"Assigned semantic point '{semantic_point}' -> {actual_slot}")
                        else:
                            # This was an existing match, just log it
                            logger.info(f"Using existing point '{semantic_point}' -> {actual_slot} ('{current_name}')")
                
                with open(TEACHING_FILE_PATH, 'w', encoding='utf-8') as f:
                    yaml.dump(self.teaching_data, f, default_flow_style=False, allow_unicode=True)
                logger.info("Updated teaching.yaml with semantic point mappings")
            
            # Update number_parameter.yaml
            if mapping['numbers']:
                for logical_number, actual_slot in mapping['numbers'].items():
                    if actual_slot in self.number_data:
                        self.number_data[actual_slot]['name'] = f"auto_assigned_{logical_number}"
                        logger.info(f"Assigned number {logical_number} -> {actual_slot}")
                
                with open(NUMBER_PARAM_FILE_PATH, 'w', encoding='utf-8') as f:
                    yaml.dump(self.number_data, f, default_flow_style=False, allow_unicode=True)
                logger.info("Updated number_parameter.yaml")
            
            # Update flag_parameter.yaml
            if mapping['flags']:
                for logical_flag, actual_slot in mapping['flags'].items():
                    if actual_slot in self.flag_data:
                        self.flag_data[actual_slot]['name'] = f"auto_assigned_{logical_flag}"
                        logger.info(f"Assigned flag {logical_flag} -> {actual_slot}")
                
                with open(FLAG_PARAM_FILE_PATH, 'w', encoding='utf-8') as f:
                    yaml.dump(self.flag_data, f, default_flow_style=False, allow_unicode=True)
                logger.info("Updated flag_parameter.yaml")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update parameter files: {e}", exc_info=True)
            return False
    
    def generate_mapping_report(self, mapping: Dict[str, Dict[str, str]], extracted_params: Dict[str, Set[str]]) -> str:
        """Generate a human-readable mapping report for semantic mappings."""
        report_lines = [
            "# Semantic Parameter Mapping Report",
            f"Generated by SAS Step 3 - Semantic Point Mapping",
            "",
            f"## Summary",
            f"- Semantic Points: {len(mapping['points'])} mapped",
            f"- Numbers: {len(mapping['numbers'])} mapped", 
            f"- Flags: {len(mapping['flags'])} mapped",
            ""
        ]
        
        if mapping['points']:
            report_lines.extend([
                "## Semantic Point Mappings",
                ""
            ])
            for semantic_point, actual_slot in sorted(mapping['points'].items()):
                # Check if this was an existing match or new assignment
                point_data = self.teaching_data.get(actual_slot, {})
                existing_name = point_data.get('name', '').strip()
                
                if existing_name and existing_name != semantic_point:
                    # This was an existing match
                    report_lines.append(f"- **{semantic_point}** → {actual_slot} (existing: '{existing_name}')")
                else:
                    # This was a new assignment
                    status = "✅ configured" if point_data.get('x_pos', 0) != 0 or point_data.get('y_pos', 0) != 0 else "⚠️ needs coordinates"
                    report_lines.append(f"- **{semantic_point}** → {actual_slot} ({status})")
            report_lines.append("")
        
        if mapping['numbers']:
            report_lines.extend([
                "## Number Variable Mappings",
                ""
            ])
            for logical, actual in sorted(mapping['numbers'].items()):
                report_lines.append(f"- {logical} → {actual}")
            report_lines.append("")
        
        if mapping['flags']:
            report_lines.extend([
                "## Flag Variable Mappings",
                ""
            ])
            for logical, actual in sorted(mapping['flags'].items()):
                report_lines.append(f"- {logical} → {actual}")
            report_lines.append("")
        
        # Add unmapped parameters if any
        unmapped_points = extracted_params['semantic_points'] - set(mapping['points'].keys())
        unmapped_numbers = extracted_params['numbers'] - set(mapping['numbers'].keys())
        unmapped_flags = extracted_params['flags'] - set(mapping['flags'].keys())
        
        if unmapped_points or unmapped_numbers or unmapped_flags:
            report_lines.extend([
                "## Unmapped Parameters (Insufficient Available Slots)",
                ""
            ])
            if unmapped_points:
                report_lines.append(f"- Unmapped Points: {', '.join(sorted(unmapped_points))}")
            if unmapped_numbers:
                report_lines.append(f"- Unmapped Numbers: {', '.join(sorted(unmapped_numbers))}")
            if unmapped_flags:
                report_lines.append(f"- Unmapped Flags: {', '.join(sorted(unmapped_flags))}")
            report_lines.append("")
        
        report_lines.extend([
            "## Next Steps",
            "1. **Review semantic point mappings above**",
            "2. **For points marked '⚠️ needs coordinates'**: Use the teaching interface to set actual positions",
            "3. **For existing points**: Verify that the coordinates are correct for your application",
            "4. **Configure number values and flag states** as needed for your specific process",
            ""
        ])
        
        return "\n".join(report_lines)

async def parameter_mapping_node(state: RobotFlowAgentState, llm: Optional[BaseChatModel] = None) -> Dict[str, Any]:
    """
    SAS Step 3: Map logical parameters from Step 2 to actual parameter file slots.
    
    This node analyzes the module steps from step 2, extracts logical parameters,
    maps them to available slots in synced_files, and updates the parameter files.
    """
    logger.info(f"--- Entering SAS Step 3: Parameter Mapping (dialog_state: {state.dialog_state}) ---")
    state.current_step_description = "SAS Step 3: Mapping logical parameters to actual parameter slots."
    state.is_error = False
    state.error_message = None

    # Check if we have module steps from step 2
    module_steps = state.sas_step2_module_steps
    if not module_steps:
        logger.error("Module steps from SAS Step 2 are missing.")
        state.is_error = True
        state.error_message = "Module steps from SAS Step 2 are required but were not found."
        state.dialog_state = "error"
        state.completion_status = "error"
        return state.dict(exclude_none=True)

    # try:
        # Initialize parameter mapper
        # mapper = ParameterMapper()
        
        # Extract logical parameters from module steps
        # extracted_params = mapper.extract_parameters_from_module_steps(module_steps)
        
        # Create parameter mapping
        # mapping = mapper.create_parameter_mapping(extracted_params)
        
        # Update parameter files
        # update_success = mapper.update_parameter_files(mapping, extracted_params)
        
        # if not update_success:
        #     logger.error("Failed to update parameter files")
        #     state.is_error = True
        #     state.error_message = "Failed to update parameter files during mapping process."
        #     state.dialog_state = "error"
        #     state.subgraph_completion_status = "error"
        #     return state.dict(exclude_none=True)
        
        # Generate mapping report
        # mapping_report = mapper.generate_mapping_report(mapping, extracted_params)
        
        # Store results in state
        # state.sas_step3_parameter_mapping = mapping
        # state.sas_step3_mapping_report = mapping_report
        
    logger.info("SAS Step 3: Parameter Mapping - SKIPPED (logic commented out for now).")
    state.dialog_state = "sas_step3_completed" # Mark as completed even if skipped
    state.current_step_description = "SAS Step 3: Parameter mapping SKIPPED (logic commented out)."
    state.completion_status = "completed_success" # Mark as success even if skipped
        

    return state.dict(exclude_none=True) 