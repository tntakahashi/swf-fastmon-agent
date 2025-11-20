#!/usr/bin/env python3
"""
Utility functions for the Fast Monitor Agent.

"""

import logging
import hashlib
import random
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any


# File status constants (matching Django FileStatus choices)
class FileStatus:
    REGISTERED = 'registered'
    PROCESSING = 'processing'
    PROCESSED = 'processed'
    FAILED = 'failed'
    DONE = 'done'


def validate_config(config: dict) -> None:
    """Validate the configuration parameters for message-driven agent."""
    required_keys = [
        "selection_fraction",
    ]

    for key in required_keys:
        if key not in config:
            raise ValueError(f"Missing required configuration key: {key}")

    if not (0.0 <= config["selection_fraction"] <= 1.0):
        raise ValueError("selection_fraction must be between 0.0 and 1.0")


def find_recent_files(config: dict, logger: logging.Logger) -> List[Path]:
    """
    Find files in the watch directories, created within the lookback time period.

    Args:
        config: Configuration dictionary
        logger: Logger instance

    Returns:
        List of Path objects for matching files
    """
    cutoff_timestamp = None
    if config["lookback_time"]:
        logger.debug(f"Looking for files created in the last {config['lookback_time']} minutes")
        cutoff_time = datetime.now() - timedelta(minutes=config["lookback_time"])
        cutoff_timestamp = cutoff_time.timestamp()

    matching_files = []
    for directory in config["watch_directories"]:
        dir_path = Path(directory)
        if not dir_path.exists():
            logger.error(f"Watch directory does not exist: {directory}")
            continue
        try:
            for pattern in config["file_patterns"]:
                for file_path in dir_path.glob(pattern):
                    if file_path.is_file():
                        # Check if file was created after cutoff time, otherwise skip
                        if (
                            cutoff_timestamp
                            and file_path.stat().st_ctime < cutoff_timestamp
                        ):
                            continue
                        matching_files.append(file_path)

        except Exception as e:
            logger.error(f"Error scanning directory {directory}: {e}")
    return matching_files


def sample_files(
    files: List[Path], selection_fraction: float, logger: logging.Logger
) -> List[Path]:
    """
    Select a fraction of files based on configuration.

    Args:
        files: List of file paths to select from
        selection_fraction: Fraction of files to select [0.0, 1.0]
        logger: Logger instance

    Returns:
        List of selected file paths
    """
    if not files:
        return []

    selection_count = max(1, int(len(files) * selection_fraction))
    # Use random selection
    selected = random.sample(files, min(selection_count, len(files)))
    logger.debug(f"Selected {len(selected)} files out of {len(files)} candidates")
    return selected


def extract_run_number(file_path: Path, default_run_number: int) -> int:
    """
    Extract run number from filename or use default.

    Args:
        file_path: Path to the file
        default_run_number: Default run number to use if not found

    Returns:
        Run number
    """
    # Try to extract run number from filename
    # Example: assume filename format like "run_12345_stf_001.stf"
    filename = file_path.name

    # Look for run number patterns
    patterns = [
        r"run_(\d+)",
        r"run(\d+)",
        r"r(\d+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, filename, re.IGNORECASE)
        if match:
            return int(match.group(1))

    # Use default run number if not found
    return default_run_number



def calculate_checksum(file_path: str, logger: logging.Logger) -> str:
    """
    Calculate MD5 checksum of file.

    Args:
        file_path: Path to the file as string
        logger: Logger instance

    Returns:
        MD5 checksum string
    """
    hash_md5 = hashlib.md5()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        logger.error(f"Error calculating checksum for {file_path}: {e}")
        return ""


def get_or_create_run(run_number: int, agent, logger: logging.Logger) -> Dict[str, Any]:
    """
    Get or create a Run object for the given run number using REST API.

    Args:
        run_number: Run number
        agent: BaseAgent instance for API access
        logger: Logger instance

    Returns:
        Run data dictionary
    """
    try:
        # First try to get existing run
        runs_response = agent.call_monitor_api('get', f'/runs/?run_number={run_number}')
        
        # Handle both paginated response (dict with 'results') and direct list response
        if isinstance(runs_response, dict) and runs_response.get('results'):
            if len(runs_response['results']) > 0:
                logger.debug(f"Found existing run: {run_number}")
                return runs_response['results'][0]
        elif isinstance(runs_response, list) and len(runs_response) > 0:
            logger.debug(f"Found existing run: {run_number}")
            return runs_response[0]
        
        # Create new run if not found
        run_data = {
            "run_number": run_number,
            "start_time": datetime.now().isoformat(),
            "run_conditions": {"auto_created": True},
        }
        
        new_run = agent.call_monitor_api('post', '/runs/', run_data)
        logger.info(f"Created new run: {run_number}")
        return new_run
        
    except Exception as e:
        logger.error(f"Error getting or creating run {run_number}: {e}")
        raise


def construct_file_url(file_path: Path, base_url: str = "file://") -> str:
    """
    Construct URL for file access (for now it uses a file URL scheme).

    Args:
        file_path: Path to the file
        base_url: Base URL for constructing file URLs

    Returns:
        URL string
    """
    base_url = base_url.rstrip('/')

    # Convert to absolute path and create URL
    abs_path = file_path.resolve()
    return f"{base_url}/{abs_path}"


def record_stf_file(file_path: Path, config: dict, agent, logger: logging.Logger) -> Dict[str, Any]:
    """
    Record a file in the database using REST API.

    Note: For development purposes, agent in production should react to the data agent with STF files already registered

    Args:
        file_path: Path to the file to record
        config: Configuration dictionary
        agent: BaseAgent instance for API access
        logger: Logger instance
    
    Returns:
        STF file data dictionary
    """
    try:
        # Check if file already exists in database
        file_url = construct_file_url(file_path, config.get("base_url", "file://"))
        
        # TODO: Check if file already recorded

        # Get file information
        file_stat = file_path.stat()
        file_size = file_stat.st_size

        # Extract run number and get/create run
        run_number = extract_run_number(file_path, config["default_run_number"])
        run_data = get_or_create_run(run_number, agent, logger)

        # Calculate checksum (optional, can be expensive)
        checksum = ""
        if config.get("calculate_checksum", False):
            checksum = calculate_checksum(file_path, logger)

        # Create STF file record via API
        stf_file_data = {
            "run": run_data["run_id"],
            "stf_filename": file_path.name,
            "file_size_bytes": file_size,
            "checksum": checksum,
            "status": FileStatus.REGISTERED,
            "metadata": {
                "original_path": str(file_path),
                "file_url": file_url,  # Store original file_url in metadata instead
                "creation_time": datetime.fromtimestamp(file_stat.st_ctime).isoformat(),
                "modification_time": datetime.fromtimestamp(
                    file_stat.st_mtime
                ).isoformat(),
                "agent_version": "1.0.0",
            },
        }

        stf_file = agent.call_monitor_api('POST', '/stf-files/', stf_file_data)
        logger.info(f"Recorded file: {file_path} -> {stf_file['file_id']}")
        return stf_file

    except Exception as e:
        logger.error(f"Error recording file {file_path}: {e}")
        raise


def simulate_tf_subsamples(stf_file: Dict[str, Any], config: dict, logger: logging.Logger, agent_name: str) -> List[
    Dict[str, Any]]:
    """
    Simulate creation of Time Frame (TF) subsamples from a Super Time Frame (STF) file.
    
    Args:
        stf_file: STF data dictionary (follows the keys from daq agent)
        config: Configuration dictionary
        logger: Logger instance
        
    Returns:
        List of TF metadata dictionaries
    """
    try:
        tf_files_per_stf = config.get("tf_files_per_stf", 2)
        tf_size_fraction = config.get("tf_size_fraction", 0.15)
        tf_sequence_start = config.get("tf_sequence_start", 1)
        
        tf_subsamples = []
        stf_size = stf_file.get("size_bytes", 0)
        # filename without extension
        base_filename = stf_file.get("filename", "unknown").rsplit('.', 1)[0]
        
        for i in range(tf_files_per_stf):
            sequence_number = tf_sequence_start + i
            
            # Generate TF filename based on STF filename
            tf_filename = f"{base_filename}_tf_{sequence_number:03d}.tf"
            
            # Calculate TF file size as fraction of STF size with some gaussian randomness
            tf_size = int(stf_size * tf_size_fraction * random.gauss(1.0, 0.1))
            
            # Create TF metadata
            tf_metadata = {
                "tf_filename": tf_filename,
                "file_size_bytes": tf_size,
                "sequence_number": sequence_number,
                "stf_file_id": stf_file.get("file_id"),  # UUID for foreign key reference
                "stf_parent": stf_file.get("filename"),  # Keep filename for reference
                "metadata": {
                    "simulation": True,
                    "created_from": stf_file.get('filename'),
                    "tf_size_fraction": tf_size_fraction,
                    "agent_name": agent_name,
                    "state": stf_file.get('state'),
                    "substate": stf_file.get('substate'),
                    "start": stf_file.get('start'),
                    "end": stf_file.get('end'),
                }
            }
            
            tf_subsamples.append(tf_metadata)

        return tf_subsamples

    except Exception as e:
        logger.error(f"Unexpected error simulating TF subsamples: {e}")
        return []


def record_tf_file(tf_metadata: Dict[str, Any], config: dict, agent, logger: logging.Logger) -> Dict[str, Any]:
    """
    Record a Time Frame (TF) file in the database using REST API.
    
    Args:
        tf_metadata: TF metadata dictionary from simulate_tf_subsamples
        config: Configuration dictionary
        agent: BaseAgent instance for API access
        logger: Logger instance
        
    Returns:
        FastMonFile data dictionary or None if failed
    """
    try:
        # Prepare FastMonFile data for API
        tf_file_data = {
            "stf_file": tf_metadata.get("stf_file_id"),  # UUID foreign key to StfFile
            "tf_filename": tf_metadata["tf_filename"],
            "file_size_bytes": tf_metadata["file_size_bytes"],
            "status": FileStatus.REGISTERED,
            "metadata": tf_metadata.get("metadata", {})
        }
        
        # Create TF file record via FastMonFile API
        tf_file = agent.call_monitor_api('post', '/fastmon-files/', tf_file_data)
        tf_file_id = tf_file.get('tf_file_id') or tf_file.get('id') or 'unknown'
        logger.debug(f"Recorded TF file: {tf_metadata['tf_filename']} -> {tf_file_id}")
        return tf_file

    except Exception as e:
        logger.error(f"Error recording TF file {tf_metadata['tf_filename']}: {e}")
        return {}


def create_tf_message(tf_file: Dict[str, Any], stf_file: Dict[str, Any], agent_name: str) -> Dict[str, Any]:
    """
    Create a message for TF file registration notifications.

    Args:
        tf_file: TF file data from the FastMonFile API
        stf_file: Parent STF file data
        agent_name: Name of the agent sending the message
        
    Returns:
        Message dictionary ready for broadcasting
    """
    from datetime import datetime

    # Extract run number from message data
    run_number = stf_file.get('run_id')

    message = {
        "msg_type": "tf_file_registered",
        "processed_by": agent_name,
        "tf_file_id": tf_file.get('tf_file_id'),
        "tf_filename": tf_file.get('tf_filename'),
        "file_size_bytes": tf_file.get('file_size_bytes'),
        "stf_filename": stf_file.get('stf_filename'),
        "run_number": run_number,
        "status": tf_file.get('status'),
        "timestamp": datetime.now().isoformat(),
        "message": f"TF file {tf_file.get('tf_filename')} registered for fast monitoring"
    }
    
    return message


def create_status_message(agent_name: str, status: str, message_text: str, run_id: str = None) -> Dict[str, Any]:
    """
    Create a status message for agent notifications.

    Args:
        agent_name: Name of the agent sending the message
        status: Status of the operation (e.g., 'started', 'completed', 'error')
        message_text: Human-readable message describing the status
        run_id: Optional run identifier
        
    Returns:
        Message dictionary ready for broadcasting
    """
    from datetime import datetime
    
    message = {
        "msg_type": "fastmon_status",
        "processed_by": agent_name,
        "status": status,
        "message": message_text,
        "timestamp": datetime.now().isoformat()
    }
    
    if run_id:
        message["run_id"] = run_id
        
    return message
