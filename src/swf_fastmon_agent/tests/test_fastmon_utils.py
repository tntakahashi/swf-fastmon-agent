#!/usr/bin/env python3
"""
Unit tests for fastmon_utils.py utilities and REST helpers.
"""

import pytest
import logging
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path
from datetime import datetime
import tempfile
import os

from swf_fastmon_agent.fastmon_utils import (
    get_or_create_run,
    record_stf_file,
    simulate_tf_subsamples,
    record_tf_file,
    find_recent_files,
    sample_files,
    extract_run_number,
    calculate_checksum,
    construct_file_url,
    FileStatus,
)


class TestGetOrCreateRun:
    """Tests for get_or_create_run function."""

    def test_get_existing_run(self):
        """Test getting an existing run via REST API."""
        # Mock agent and logger
        mock_agent = Mock()
        mock_logger = Mock()
        
        # Mock API response for existing run
        mock_agent.call_monitor_api.return_value = {
            'results': [{'run_id': 123, 'run_number': 42, 'start_time': '2023-01-01T00:00:00Z'}]
        }
        
        result = get_or_create_run(42, mock_agent, mock_logger)
        
        # Verify API call was made correctly
        mock_agent.call_monitor_api.assert_called_once_with('get', '/runs/?run_number=42')
        assert result['run_id'] == 123
        assert result['run_number'] == 42

    def test_create_new_run(self):
        """Test creating a new run via REST API when it doesn't exist."""
        # Mock agent and logger
        mock_agent = Mock()
        mock_logger = Mock()
        
        # Mock API responses - first call returns no results, second creates new run
        mock_agent.call_monitor_api.side_effect = [
            {'results': []},  # No existing run found
            {'run_id': 456, 'run_number': 99, 'start_time': '2023-01-01T00:00:00Z'}  # New run created
        ]
        
        result = get_or_create_run(99, mock_agent, mock_logger)
        
        # Verify both API calls were made
        assert mock_agent.call_monitor_api.call_count == 2
        mock_agent.call_monitor_api.assert_any_call('get', '/runs/?run_number=99')
        
        # Check the POST call
        post_call = mock_agent.call_monitor_api.call_args_list[1]
        assert post_call[0][0] == 'post'
        assert post_call[0][1] == '/runs/'
        assert post_call[0][2]['run_number'] == 99
        assert 'auto_created' in post_call[0][2]['run_conditions']

    def test_get_existing_run_list_response(self):
        """Support list responses as returned by some endpoints."""
        mock_agent = Mock()
        mock_logger = Mock()

        # API returns a list directly
        mock_agent.call_monitor_api.return_value = [
            {'run_id': 7, 'run_number': 7}
        ]

        result = get_or_create_run(7, mock_agent, mock_logger)
        mock_agent.call_monitor_api.assert_called_once_with('get', '/runs/?run_number=7')
        assert result['run_id'] == 7


class TestRecordStfFile:
    """Tests for record_stf_file helper."""

    def test_record_new_file_posts_payload(self):
        """Record a new STF file; verify payload and method casing."""
        with tempfile.NamedTemporaryFile(suffix='.stf', delete=False) as tf:
            tf.write(b'test data')
            temp_file_path = Path(tf.name)

        try:
            mock_agent = Mock()
            mock_logger = Mock()

            # Mock POST response from API
            mock_agent.call_monitor_api.return_value = {
                'file_id': 'uuid-123', 'stf_filename': temp_file_path.name
            }

            config = {
                'base_url': 'file://',
                'default_run_number': 1,
                'calculate_checksum': False,
            }

            # Bypass run creation logic
            with patch('swf_fastmon_agent.fastmon_utils.get_or_create_run') as mock_get_run:
                mock_get_run.return_value = {'run_id': 123, 'run_number': 1}
                result = record_stf_file(temp_file_path, config, mock_agent, mock_logger)

            assert result['file_id'] == 'uuid-123'

            # Verify a single POST call with expected keys
            mock_agent.call_monitor_api.assert_called_once()
            method, path, payload = mock_agent.call_monitor_api.call_args[0]
            assert method == 'POST'
            assert path == '/stf-files/'
            assert payload['run'] == 123
            assert payload['stf_filename'] == temp_file_path.name
            assert payload['status'] == FileStatus.REGISTERED
            assert payload['checksum'] == ''
            assert 'file_size_bytes' in payload and payload['file_size_bytes'] > 0
            assert payload['metadata']['file_url'].startswith('file://')

        finally:
            if temp_file_path.exists():
                temp_file_path.unlink()

    def test_record_new_file_checksum(self):
        """When checksum is enabled, include MD5 in payload."""
        content = b'checksum test data\n'
        with tempfile.NamedTemporaryFile(suffix='.stf', delete=False) as tf:
            tf.write(content)
            temp_file_path = Path(tf.name)

        try:
            mock_agent = Mock()
            mock_logger = Mock()
            mock_agent.call_monitor_api.return_value = {
                'file_id': 'uuid-ck', 'stf_filename': temp_file_path.name
            }

            config = {
                'base_url': 'file://',
                'default_run_number': 1,
                'calculate_checksum': True,
            }

            with patch('swf_fastmon_agent.fastmon_utils.get_or_create_run') as mock_get_run:
                mock_get_run.return_value = {'run_id': 55, 'run_number': 55}
                record_stf_file(temp_file_path, config, mock_agent, mock_logger)

            # Inspect posted payload
            _, _, payload = mock_agent.call_monitor_api.call_args[0]
            expected_md5 = calculate_checksum(temp_file_path, mock_logger)
            assert payload['checksum'] == expected_md5

        finally:
            if temp_file_path.exists():
                temp_file_path.unlink()


class TestSimulateTfSubsamples:
    """Tests for simulate_tf_subsamples function."""

    def test_generate_tf_subsamples(self):
        """Test generating TF subsamples from STF file."""
        mock_logger = Mock()

        stf_file = {
            'file_id': 'stf-uuid-123',
            'filename': 'test_run001.stf',
            'size_bytes': 1000000
        }

        config = {
            'tf_files_per_stf': 3,
            'tf_size_fraction': 0.2,
            'tf_sequence_start': 1,
            'agent_name': 'test-agent'
        }

        result = simulate_tf_subsamples(stf_file, config, mock_logger, agent_name='test-agent')

        # Verify correct number of TF files generated
        assert len(result) == 3

        # Verify TF file structure and new foreign key field
        for i, tf in enumerate(result):
            assert 'tf_filename' in tf
            assert 'file_size_bytes' in tf
            assert 'sequence_number' in tf
            assert tf['sequence_number'] == i + 1
            assert tf['stf_file_id'] == 'stf-uuid-123'  # UUID for foreign key
            assert tf['stf_parent'] == 'test_run001.stf'  # Filename for reference
            assert 'simulation' in tf['metadata']

    def test_generate_tf_with_defaults(self):
        """Test TF generation with default configuration values."""
        mock_logger = Mock()

        stf_file = {
            'file_id': 'stf-uuid-456',
            'filename': 'test.stf',
            'size_bytes': 500000
        }

        config = {}  # Empty config to test defaults

        result = simulate_tf_subsamples(stf_file, config, mock_logger, agent_name='test-agent')

        # Should use default values (2 TF files)
        assert len(result) == 2

        # Verify default sequence numbering and foreign key
        assert result[0]['sequence_number'] == 1
        assert result[-1]['sequence_number'] == 2
        assert all(tf['stf_file_id'] == 'stf-uuid-456' for tf in result)


class TestRecordTfFile:
    """Tests for record_tf_file function."""

    def test_record_tf_file_success(self):
        """Test successful TF file recording via REST API with UUID foreign key."""
        # Mock agent and logger
        mock_agent = Mock()
        mock_logger = Mock()

        # Mock API response for successful creation
        mock_agent.call_monitor_api.return_value = {
            'tf_file_id': 'tf-uuid-123',
            'tf_filename': 'test_tf_001.tf',
            'status': 'REGISTERED'
        }

        # TF metadata now includes stf_file_id (UUID) for foreign key
        tf_metadata = {
            'stf_file_id': 'stf-uuid-parent-456',  # UUID foreign key
            'stf_parent': 'test_run001.stf',  # Filename for reference
            'tf_filename': 'test_tf_001.tf',
            'file_size_bytes': 150000,
            'metadata': {'simulation': True}
        }
        config = {}

        result = record_tf_file(tf_metadata, config, mock_agent, mock_logger)

        # Verify TF file was recorded with UUID foreign key
        assert result['tf_file_id'] == 'tf-uuid-123'
        mock_agent.call_monitor_api.assert_called_once_with('post', '/fastmon-files/', {
            'stf_file': 'stf-uuid-parent-456',  # UUID, not filename
            'tf_filename': 'test_tf_001.tf',
            'file_size_bytes': 150000,
            'status': FileStatus.REGISTERED,
            'metadata': {'simulation': True}
        })

    def test_record_tf_file_failure(self):
        """Test handling of TF file recording failure."""
        # Mock agent and logger
        mock_agent = Mock()
        mock_logger = Mock()
        
        # Mock API call that raises exception
        mock_agent.call_monitor_api.side_effect = Exception("API Error")
        
        stf_file = {'file_id': 'stf-uuid-123'}
        tf_metadata = {
            'tf_filename': 'test_tf_001.tf',
            'file_size_bytes': 150000
        }
        config = {}
        
        result = record_tf_file(tf_metadata, config, mock_agent, mock_logger)
        
        # Should return empty on failure
        assert not result
        mock_logger.error.assert_called_once()


class TestMiscUtilities:
    """Tests for standalone utility helpers."""

    def test_extract_run_number_patterns(self):
        assert extract_run_number(Path('run_12345_stf_001.stf'), 1) == 12345
        assert extract_run_number(Path('run9999.stf'), 1) == 9999
        assert extract_run_number(Path('r77_data.stf'), 1) == 77
        assert extract_run_number(Path('no_run_here.stf'), 5) == 5

    def test_construct_file_url(self, tmp_path):
        f = tmp_path / 'a.stf'
        f.write_text('x')
        url = construct_file_url(f, 'file://')
        assert url.startswith('file://') and f.name in url

    def test_calculate_checksum(self, tmp_path):
        f = tmp_path / 'data.stf'
        content = b'abcdefg'
        f.write_bytes(content)
        cs = calculate_checksum(f, logging.getLogger(__name__))
        import hashlib as _hashlib

        assert cs == _hashlib.md5(content).hexdigest()

    def test_find_recent_files_and_sample(self, tmp_path):
        # Create files
        files = []
        for i in range(5):
            p = tmp_path / f'f{i}.stf'
            p.write_text('data')
            files.append(p)

        config = {
            'watch_directories': [str(tmp_path)],
            'file_patterns': ['*.stf'],
            'check_interval': 1,
            'lookback_time': 0,
            'selection_fraction': 0.4,
            'default_run_number': 1,
        }

        found = find_recent_files(config, logging.getLogger(__name__))
        assert set(found) == set(files)

        # Sample ~40% => 2 files (min 1)
        sampled = sample_files(found, config['selection_fraction'], logging.getLogger(__name__))
        assert len(sampled) == 2
