# SWF Fast Monitoring Agent

**`swf-fastmon-agent`** is a fast monitoring service for the ePIC streaming workflow testbed.

This agent monitors STF (Super Time Frame) files, samples TF (Time Frame) subsets, and distributes metadata via Server-Sent Events (SSE) streaming, enabling real-time remote monitoring of ePIC data acquisition processes. The agent includes both server-side monitoring capabilities and a client for remote visualization.

## Architecture Overview

The fast monitoring agent is designed as part of the **SWF testbed ecosystem** and integrates with:
- **swf-monitor**: PostgreSQL database and Django web interface for persistent monitoring data
- **swf-testbed**: Infrastructure orchestration and process management  
- **swf-common-lib**: Shared utilities and BaseAgent framework for messaging
- **swf-data-agent**: Receiving messages when STF files are available for fast monitoring

The agent operates as a managed service within the swf-testbed ecosystem, automatically configured and monitored through the central CLI. It extends the BaseAgent class from swf-common-lib for consistent messaging and logging across the ecosystem.

-------------- 

## Integration with SWF Testbed

### Prerequisites
- Complete SWF testbed ecosystem (swf-testbed, swf-monitor, swf-common-lib as siblings)
- Docker Desktop for infrastructure services
- Python 3.9+ virtual environment

### Running the Agent
```bash
# The agent runs as a managed service within the testbed
cd $SWF_PARENT_DIR/swf-testbed
swf-testbed status  # Check if fast monitoring agent is running
```

The agent relies on `.env` configuration for API tokens and monitor URLs, and uses supervisord for process management.

### Manual execution for development/testing

```bash
# For manual development run (message-driven mode - default)
cd ../swf-fastmon-agent
export SWF_MONITOR_HTTP_URL="http://localhost:8002"
export SWF_API_TOKEN="your_api_token_here"
python -m swf_fastmon_agent.main

# Continuous monitoring mode (for testing)
cd ../swf-fastmon-agent
export FASTMON_MODE=continuous
export SWF_MONITOR_HTTP_URL="http://localhost:8002"
export SWF_API_TOKEN="your_api_token_here"
python -m swf_fastmon_agent.main
```

## Agent Configuration

The fast monitoring agent is configured through the swf-testbed ecosystem:

### Environment Variables
- **SWF_MONITOR_HTTP_URL**: swf-monitor REST API base URL (default: http://localhost:8002)
- **SWF_API_TOKEN**: Authentication token for swf-monitor API access (required)
- **FASTMON_MODE**: Operation mode - `message` (default) or `continuous`

## Agent Components

### Fast Monitor Agent
- **STF File Monitoring**: Monitors directories for newly created STF files
- **TF Sampling**: Simulates TF subsamples from STF files based on configuration
- **REST API Integration**: Records STF and TF metadata via swf-monitor REST API endpoints
- **SSE Message Broadcasting**: Distributes TF file notifications via swf-monitor's SSE streaming API
- **Dual Operation Modes**:
  - **Message-driven mode**: Responds to data_ready messages from swf-data-agent
  - **Continuous mode**: Periodically scans directories (for development/testing)
- **Status Reporting**: Provides health checks and performance metrics via BaseAgent

### Fast Monitoring Client (in development)
- **Real-time Display**: Receives and displays TF file notifications in terminal via SSE streaming
- **Statistics Tracking**: Monitors per-run TF counts and data volume
- **Graceful Shutdown**: Handles Ctrl+C with summary statistics
- **Authentication**: Uses API tokens for secure SSE stream access

### Data Flow
1. **STF File Detection**: Agent monitors directories for new STF files or receives data_ready messages
2. **TF Simulation**: Generates TF subsamples from STF files based on configuration parameters
3. **Database Recording**: Records TF metadata in swf-monitor database via REST API
4. **SSE Message Broadcasting**: Agent sends TF file notifications to swf-monitor's `/api/messages/` endpoint
5. **Real-time Streaming**: swf-monitor broadcasts messages via SSE to connected clients at `/api/messages/stream/`
6. **Client Display**: Client receives SSE stream and displays formatted TF information in real-time
7. **Historical Access**: All data accessible via swf-monitor Django web application

### SSE Integration Benefits
- **Simplified Architecture**: No ActiveMQ dependency for clients - only HTTP access required
- **Better Scalability**: SSE handles many concurrent read-only client connections efficiently
- **Enhanced Security**: API token-based authentication with fine-grained access control
- **Web Integration Ready**: Easy to add web-based dashboards that consume the same SSE stream

## SSE Client Usage

### Basic Usage
```bash
# Start the SSE client with default settings
python -m swf_fastmon_client.main start

# Connect to a specific monitor URL
python -m swf_fastmon_client.main start --monitor-url https://my-monitor.domain.com

# Filter by specific message types
python -m swf_fastmon_client.main start --message-types tf_file_registered,fastmon_status

# Filter by specific agents
python -m swf_fastmon_client.main start --agents swf-fastmon-agent

# Combined filtering
python -m swf_fastmon_client.main start --message-types tf_file_registered --agents swf-fastmon-agent
```

### Environment Configuration
```bash
# Set up environment variables (recommended)
export SWF_MONITOR_URL="http://localhost:8002"
export SWF_API_TOKEN="your_api_token_here"

# Then start with defaults
python -m swf_fastmon_client.main start
```

### Client Commands
```bash
# Check client configuration
python -m swf_fastmon_client.main status

# Show version information  
python -m swf_fastmon_client.main version
```

## Development and Testing

### Testing within Ecosystem
```bash
# Run all testbed tests (includes fast monitoring agent)
cd $SWF_PARENT_DIR/swf-testbed
./run_all_tests.sh

# Test agent integration specifically
cd ../swf-fastmon-agent
python -m pytest src/swf_fastmon_agent/tests/


# Check agent status in testbed
swf-testbed status
```

### Code Quality
```bash
# Format and lint (from swf-fastmon-agent directory)
black .
flake8 .
```

## Development Guidelines

This library follows the ePIC streaming workflow testbed development guidelines for portability, maintainability, and consistency across the ecosystem. See `CLAUDE.md` for detailed development guidelines and project-specific conventions.

## Troubleshooting SSE Integration

### Common Issues

#### Client Cannot Connect to SSE Stream
**Symptoms**: "Auth failed" or "SSE endpoint not available" errors
**Solutions**:
1. Verify `SWF_API_TOKEN` is set and valid
2. Check `SWF_MONITOR_URL` points to the correct monitor instance
3. Ensure swf-monitor is running and SSE endpoints are enabled
4. For production: Verify Apache/WSGI configuration passes Authorization headers

#### Agent Cannot Send Messages or Record Files
**Symptoms**: "Error sending SSE message" or API timeout errors in agent logs
**Solutions**:
1. Verify agent has valid API token with message posting permissions
2. Check monitor's `/api/messages/` and `/api/stf-files/` endpoints are accessible
3. Ensure monitor database is running and accepting connections
4. Verify API field names match (e.g., `stf_filename` not `file_url`, `status='registered'` not `REGISTERED`)
5. Check that monitor ViewSets have proper filtering configured (DjangoFilterBackend)
6. Review monitor logs for 400/500 errors with detailed error messages

#### No Messages Received by Client
**Symptoms**: Client connects successfully but receives no messages
**Solutions**:
1. Check if agent is actually processing files and sending messages
2. Verify message type filters match what agent is sending (`tf_file_registered`)
3. Check agent name filters match the actual agent name
4. Monitor swf-monitor logs for message processing issues

#### Message Format Issues
**Symptoms**: Client receives messages but fails to parse them
**Solutions**:
1. Ensure agent uses `create_sse_tf_message()` utility function
2. Check message contains required fields: `msg_type`, `processed_by`, `timestamp`
3. Verify JSON formatting is correct in agent message creation

### Environment Variables Reference
```bash
# Required for both agent and client
export SWF_MONITOR_URL="http://localhost:8002"
export SWF_API_TOKEN="your_token_here"

# Optional - for custom endpoints
export SWF_MONITOR_HTTP_URL="http://localhost:8002"  # Agent API calls
```

### Testing SSE Integration
```bash
# Test agent message sending (check monitor logs)
python -m swf_fastmon_agent.main

# Test client SSE reception in another terminal
python -m swf_fastmon_client.main start --message-types tf_file_registered

# Verify with curl (if SSE endpoint is accessible)
curl -H "Authorization: Token your_token" \
     -H "Accept: text/event-stream" \
     http://localhost:8002/api/messages/stream/
```