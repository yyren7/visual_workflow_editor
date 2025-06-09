import logging
import json
from pathlib import Path
from typing import Any, List, Dict

logger = logging.getLogger(__name__)

def save_iteration_data_as_json(
    run_output_directory: str | None,
    revision_iteration: int,
    data_to_save: List[Dict[str, Any]] | Dict[str, Any],
    base_filename_prefix: str,
    file_description: str
) -> bool:
    """
    Saves the provided data to a JSON file in the run_output_directory,
    with a filename including the revision_iteration and a given prefix.

    Args:
        run_output_directory: The base directory for saving run outputs.
        revision_iteration: The current revision iteration number.
        data_to_save: The data (list of dicts or a single dict) to be saved as JSON.
        base_filename_prefix: Prefix for the filename (e.g., "sas_step1_tasks").
        file_description: A short description of what is being saved, for logging.

    Returns:
        True if saving was successful, False otherwise.
    """
    if not run_output_directory:
        logger.warning(
            f"run_output_directory is not set. Skipping saving of {file_description} "
            f"for Iteration {revision_iteration}."
        )
        return False

    try:
        # Ensure the directory path is absolute or correctly relative
        output_dir_path = Path(run_output_directory)
        output_dir_path.mkdir(parents=True, exist_ok=True) # Ensure directory exists
        
        iteration_filename = f"{base_filename_prefix}_iter{revision_iteration}.json"
        iteration_file_path = output_dir_path / iteration_filename
        
        with open(iteration_file_path, "w", encoding="utf-8") as f_write:
            json.dump(data_to_save, f_write, indent=2, ensure_ascii=False)
        logger.info(
            f"Successfully saved {file_description} (Iteration {revision_iteration}) "
            f"to: {iteration_file_path}"
        )
        return True
    except Exception as e:
        logger.error(
            f"Failed to save {file_description} for Iteration {revision_iteration}. Error: {e}",
            exc_info=True
        )
        return False 