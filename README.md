# SWF Fast Monitoring Agent

**`swf-fastmon-agent`** is a fast monitoring service for the ePIC streaming workflow testbed.

This agent monitors STF (Super Time Frame) files, samples TF (Time Frame) subsets, and distributes metadata via Server-Sent Events (SSE) streaming, enabling real-time remote monitoring of ePIC data acquisition processes.

## Architecture Overview

The fast monitoring agent is designed as part of the **SWF testbed ecosystem** and integrates with:
- **swf-testbed**: Infrastructure orchestration, process management, and Docker services
- **swf-monitor**: PostgreSQL database and Django web interface for persistent monitoring data
- **swf-common-lib**: Shared utilities and BaseAgent framework for messaging
- **swf-data-agent**: Sends `stf_ready` messages when STF files are available for fast monitoring

The agent operates as a **managed service within swf-testbed**, automatically configured and monitored through the central CLI. It extends the BaseAgent class from swf-common-lib for consistent messaging and logging across the ecosystem.

--------------

## Quick Start

### Prerequisites
- Complete SWF testbed ecosystem installed (swf-testbed, swf-monitor, swf-common-lib as siblings)
- Python 3.9+ virtual environment
- All infrastructure services managed by swf-testbed

### Setup and Run

1. **Install the testbed ecosystem** (from the swf-testbed directory):
```bash
cd $SWF_PARENT_DIR/swf-testbed
source install.sh  # Installs all components including swf-fastmon-agent
```

2. **Configure agent environment**:
```bash
cd $SWF_PARENT_DIR/swf-fastmon-agent
cp .env.example .env
# Edit .env with your values (most defaults work for local development)
```

3. **Start the complete testbed** (infrastructure + agents):
```bash
cd $SWF_PARENT_DIR/swf-testbed
swf-testbed start  # Starts Docker services + all agents including fastmon
```

4. **Check agent status**:
```bash
swf-testbed status  # Shows all services and agents
```

**Note**: All infrastructure services (PostgreSQL, ActiveMQ, Redis) are managed by swf-testbed via Docker Compose. Do not attempt to run them separately.

### Manual Execution (Development/Testing)

For development, you can run the agent manually outside of supervisord:

```bash
cd $SWF_PARENT_DIR/swf-fastmon-agent
source $SWF_PARENT_DIR/swf-testbed/.venv/bin/activate

# Message-driven mode (production mode - waits for stf_ready messages)
python -m swf_fastmon_agent.main

# Continuous mode (development/testing - scans directories)
export FASTMON_MODE=continuous
python -m swf_fastmon_agent.main
```

## Agent Configuration

The fast monitoring agent is configured through environment variables. Copy `.env.example` to `.env` and update with your actual values.

### Required Environment Variables
- **SWF_MONITOR_URL**: HTTPS URL for authenticated API calls
- **SWF_MONITOR_HTTP_URL**: HTTP URL for REST logging (optional)
- **SWF_API_TOKEN**: Authentication token for swf-monitor API access
- **ACTIVEMQ_HOST**, **ACTIVEMQ_PORT**: ActiveMQ broker connection
- **ACTIVEMQ_USER**, **ACTIVEMQ_PASSWORD**: ActiveMQ credentials
- **MQ_USER**, **MQ_PASSWD**: Message queue credentials (for mq_comms module)
- **MQ_CAFILE**: SSL certificate path for secure connections

### Optional Configuration
- **FASTMON_MODE**: Operation mode - `message` (default, message-driven) or `continuous` (polling)
- **FASTMON_SELECTION_FRACTION**: Fraction of STF files to sample (0.0-1.0, default: 0.1)
- **FASTMON_TF_FILES_PER_STF**: Number of TF files per STF (default: 7)
- **SWF_LOG_LEVEL**: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

See `.env.example` for a complete list of configuration options.

## Agent Components

### Fast Monitor Agent
The agent extends **BaseAgent** from swf-common-lib, providing:

- **Message-Driven Processing**: Receives `stf_ready` messages from data agent via ActiveMQ
- **TF Sampling**: Simulates TF subsamples from STF files based on configuration
- **REST API Integration**: Records TF metadata via swf-monitor `/api/fastmon-files/` endpoint
- **Workflow Tracking**: Tracks processing stages via `/api/workflow-stages/` for visibility
- **Enhanced Heartbeats**: Reports workflow metadata (active/completed tasks) to monitor
- **Automatic Registration**: Auto-registers as ActiveMQ subscriber with monitor
- **REST Logging**: Centralized logging via swf-monitor REST API
- **Connection Resilience**: Automatic reconnection on MQ disconnection
- **Dual Operation Modes**:
  - **Message-driven mode** (default): Responds to `stf_ready` messages from data agent
  - **Continuous mode**: Periodically scans directories (for development/testing)

### Key Features from BaseAgent Integration
- **Sequential Agent IDs**: Uses persistent state API for unique agent naming
- **Environment Auto-Setup**: Loads virtual environment and ~/.env variables on startup
- **Standard Message Types**: Follows workflow message type conventions
- **MQ Client ID**: Supports durable subscriptions with unique client IDs
- **Status Reporting**: Reports agent status, errors, and performance metrics

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

### Testbed Integration
All development and testing should use the swf-testbed framework:

```bash
# Start testbed services (PostgreSQL, ActiveMQ, Redis via Docker)
cd $SWF_PARENT_DIR/swf-testbed
swf-testbed start

# Check system status
swf-testbed status

# View logs
swf-testbed logs  # All agent logs
tail -f logs/swf-fastmon-agent.log  # Fast monitor agent only

# Stop services
swf-testbed stop
```

### Running Tests
```bash
# Run complete testbed test suite (includes all agents)
cd $SWF_PARENT_DIR/swf-testbed
./run_all_tests.sh

# Run fast monitoring agent tests specifically
cd $SWF_PARENT_DIR/swf-fastmon-agent
source $SWF_PARENT_DIR/swf-testbed/.venv/bin/activate
python -m pytest src/swf_fastmon_agent/tests/
```

## Development Guidelines

This agent is part of the ePIC streaming workflow testbed ecosystem and follows strict integration guidelines:

- **Never run infrastructure services independently** - always use `swf-testbed start`
- **Use swf-testbed CLI** for all service management (start, stop, status, logs)
- **Follow BaseAgent patterns** from swf-common-lib for consistency
- **Coordinate changes** across repositories using infrastructure branches

See `CLAUDE.md` for detailed development guidelines and project-specific conventions.

## Troubleshooting

### Infrastructure Issues

#### Services Not Running
**Symptoms**: Connection refused, "Cannot connect to database/ActiveMQ" errors
**Solutions**:
1. Verify testbed services are running: `swf-testbed status`
2. Start services if needed: `swf-testbed start`
3. Check Docker containers: `docker ps | grep swf`
4. Review service logs: `docker-compose logs postgres activemq redis`

#### Agent Not Starting
**Symptoms**: Agent process fails to start or crashes immediately
**Solutions**:
1. Check agent logs at `$SWF_PARENT_DIR/swf-testbed/logs/`
2. Verify `.env` configuration exists and has required values
3. Ensure virtual environment is activated
4. Check supervisord status: `swf-testbed status`

### API and Database Issues

#### Agent Cannot Record Files
**Symptoms**: API timeout errors, "Cannot connect to swf-monitor" errors
**Solutions**:
1. Verify swf-monitor is running: `swf-testbed status`
2. Check database connection: `docker exec swf-postgres pg_isready`
3. Verify API token is valid: `echo $SWF_API_TOKEN`
4. Test API endpoint: `curl -H "Authorization: Token $SWF_API_TOKEN" $SWF_MONITOR_URL/api/runs/`
5. Review monitor logs for 400/500 errors

#### Foreign Key Constraint Errors
**Symptoms**: "This field may not be null" or "stf_file does not exist" errors
**Solutions**:
1. Verify STF file is registered before creating TF files
2. Check that `file_id` (UUID) is being passed, not filename
3. Ensure message data includes `file_id` field from STF record

### Client and SSE Issues

#### Client Cannot Connect
**Symptoms**: "Auth failed" or "SSE endpoint not available" errors
**Solutions**:
1. Verify swf-monitor SSE endpoints are enabled
2. Check `SWF_API_TOKEN` is set and valid
3. Ensure `SWF_MONITOR_URL` is correct (typically `http://localhost:8002`)
4. Test SSE endpoint: `curl -H "Authorization: Token $SWF_API_TOKEN" http://localhost:8002/api/messages/stream/`

#### No Messages Received
**Symptoms**: Client connects but receives no messages
**Solutions**:
1. Check if agent is processing files: `tail -f logs/swf-fastmon-agent.log`
2. Verify message type filters match (`tf_file_registered`)
3. Check agent is sending notifications (look for "Sent TF file notification" in logs)

### Environment Configuration
```bash
# Minimal local development configuration
export SWF_MONITOR_URL="http://localhost:8002"
export SWF_MONITOR_HTTP_URL="http://localhost:8002"
export SWF_API_TOKEN="your_token_here"
```