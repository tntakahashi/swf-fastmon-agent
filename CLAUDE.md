# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python-based fast monitoring agent (`swf-fastmon-agent`) that is part of the **ePIC streaming workflow testbed** - a distributed scientific computing system for high-energy physics data processing. This agent is one of several optional agent repositories in the larger ecosystem:

**Core Repositories (REQUIRED):**
- `swf-testbed` - Infrastructure, CLI, and orchestration
- `swf-monitor` - Django web application for monitoring and REST API
- `swf-common-lib` - Shared utilities and common code

**Optional Agent Repositories:**
- `swf-fastmon-agent` - Fast monitoring agent (this repository)
- `swf-daqsim-agent` - Data acquisition simulation agent
- `swf-data-agent` - Data management agent
- `swf-processing-agent` - Processing workflow agent

**Critical**: The three core repositories must exist as siblings in the same parent directory. This agent repository should also be placed as a sibling for proper integration.

The project is designed to work with PostgreSQL databases and ActiveMQ messaging systems, communicating via loosely coupled message-based architecture.

## Development Environment

- **Python Version**: 3.9+
- **IDE**: PyCharm or VScode (with Black formatter configured)
- **Code Formatter**: Black
- **License**: Apache 2.0
- **Environment Variable**: `SWF_HOME` automatically set to parent directory containing all swf-* repos (via swf-testbed CLI)
- **Architecture**: Extends BaseAgent from swf-common-lib for standardized agent behavior

## Recent Infrastructure Updates (2025-11)

### BaseAgent Integration
The agent now inherits from **BaseAgent** (swf-common-lib) providing:
- Automatic environment setup and .env loading
- REST logging to swf-monitor
- Sequential agent ID generation
- Enhanced heartbeat with workflow metadata
- Automatic subscriber registration
- Connection resilience with auto-reconnection

### Workflow Tracking
Integrated with swf-monitor's workflow tracking system:
- Creates workflow stages via `/api/workflow-stages/`
- Tracks statuses: `fastmon_received`, `fastmon_processing`, `fastmon_complete`
- Records input/output messages and processing times
- Enables end-to-end workflow visibility

### MQ Communications
Updated to use swf-common-lib's mq_comms module:
- Requires `client_id` parameter for durable subscriptions
- SSL support with `MQ_CAFILE` environment variable
- Standardized error handling and reconnection logic

## Project Structure

The project has been converted to Django framework with modern packaging:
```
src/swf_fastmon_agent/   # Agent implementations
├── __init__.py          # Package initialization
├── main.py              # Main file monitoring agent
├── fastmon_utils.py     # Utility functions for the agent
└── database/            # Django database configuration
    └── settings.py      # Django settings
```

```
src/swf_fastmon_client/  # Lightweight monitoring client
├── __init__.py          # Package initialization
├── main.py              # Typer CLI client for TF monitoring
└── README.md            # Client documentation
```

Additional project files:
```
├── manage.py            # Django management script
├── requirements.txt     # Python dependencies
├── pyproject.toml       # Modern Python packaging configuration
├── setup_db.py          # Database setup utility
├── test_client.py       # Client functionality tests
└── demo_integration.py  # Integration demonstration
```


### Agent Components

- **`main.py`**: Main file monitoring agent (`FastMonitorAgent`) that:
  - Monitors specified directories for newly created STF files
  - Applies time-based filtering (files created within X minutes)
  - Randomly selects a configurable fraction of discovered files
  - Records selected files in the database with metadata
  - Broadcasts selected files to ActiveMQ message queues
  - Designed for continuous operation under supervisord
  - Supports environment variable configuration for deployment flexibility

- **`fastmon_utils.py`**: Core utility functions including:
  - File discovery and time-based filtering
  - Random file selection algorithms
  - Database operations for STF file recording via REST API
  - Run number extraction from filenames
  - Checksum calculation and validation
  - ActiveMQ message broadcasting to client queues
  - TF (Time Frame) file simulation and sampling from STF files

### Client Components

- **`src/swf_fastmon_client/main.py`**: Lightweight monitoring client (`FastMonitoringClient`) that:
  - Receives TF metadata from ActiveMQ using STOMP protocol
  - Stores metadata in local SQLite database for remote monitoring
  - Provides Typer-based CLI with `start`, `status`, and `init-db` commands
  - Supports SSL connections and flexible ActiveMQ configuration
  - Designed for minimal infrastructure requirements and portability
  - Enables remote monitoring of ePIC data acquisition with local data persistence
  - **Future Development**: Will become a standalone application separate from the agent repository

## Dependencies and External Systems

This project integrates with:
- **PostgreSQL**: Database operations using Django ORM (credentials in `.pgpass`, logs excluded)
- **ActiveMQ**: Message queuing system (logs and kahadb excluded)
- **Agent framework**: Secrets/credentials managed through `secrets.yaml`, `credentials.json`, `config.ini`

### Python Dependencies
**Core Dependencies:**
- **Django**: Web framework with ORM for database operations (>=4.2, <5.0)
- **psycopg**: Modern PostgreSQL adapter for Python (>=3.2.0)
- **psycopg2-binary**: Legacy PostgreSQL adapter for Python (>=2.9.0)
- **typer**: Command-line interface framework (>=0.9.0)
- **stomp.py**: STOMP protocol client for ActiveMQ (>=8.1.0)

**Development Dependencies:**
- **pytest**: Testing framework (>=7.0.0)
- **pytest-django**: Django testing integration (>=4.5.0)
- **pytest-cov**: Test coverage reporting (>=4.0.0)
- **black**: Code formatter (>=22.0.0)
- **flake8**: Code linter (>=4.0.0)
- **isort**: Import sorting utility (>=5.10.0)
- **mypy**: Static type checking (>=1.0.0)
- **django-stubs**: Django type stubs (>=1.13.0)

### Environment Variables Configuration

The agent requires a `.env` file with the following variables:

**Monitor Connection:**
- `SWF_MONITOR_URL` - HTTPS URL for authenticated API calls (required)
- `SWF_MONITOR_HTTP_URL` - HTTP URL for REST logging (optional)
- `SWF_API_TOKEN` - Authentication token for swf-monitor API (required)

**ActiveMQ Configuration:**
- `ACTIVEMQ_HOST` - ActiveMQ broker host (default: localhost)
- `ACTIVEMQ_PORT` - STOMP port (default: 61612)
- `ACTIVEMQ_USER` - ActiveMQ username (required)
- `ACTIVEMQ_PASSWORD` - ActiveMQ password (required)
- `ACTIVEMQ_USE_SSL` - Enable SSL connections (true/false)
- `ACTIVEMQ_SSL_CA_CERTS` - Path to CA certificate file

**MQ Communications (swf-common-lib):**
- `MQ_USER` - Message queue username (required)
- `MQ_PASSWD` - Message queue password (required)
- `MQ_HOST` - Message queue host (required)
- `MQ_PORT` - Message queue port (required)
- `MQ_CAFILE` - SSL CA certificate path (required for SSL)

**Logging:**
- `SWF_LOG_LEVEL` - Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `SWF_STOMP_DEBUG` - Enable STOMP protocol debugging (true/false)
- `SWF_AGENT_QUIET` - Minimal output mode (true/false)

**Agent Configuration:**
- `FASTMON_MODE` - Operation mode: `message` (default) or `continuous`
- `FASTMON_SELECTION_FRACTION` - STF sampling fraction (0.0-1.0, default: 0.1)
- `FASTMON_TF_FILES_PER_STF` - TF files per STF (default: 7)

See `.env.example` for a complete template with all available options.

### Database Environment Variables (Django Legacy)
Legacy Django settings (if needed for local development):
- `POSTGRES_HOST` (default: localhost)
- `POSTGRES_PORT` (default: 5432)
- `POSTGRES_DB` (default: epic_monitoring)
- `POSTGRES_USER` (default: postgres)
- `POSTGRES_PASSWORD` (default: empty)

## Security Notes

- Configuration files containing secrets are gitignored: `secrets.yaml`, `credentials.json`, `config.ini`, `*.session`
- Database credentials (`.pgpass`) are excluded from version control
- Log files are excluded from commits

## API Integration

The agent integrates with swf-monitor REST API endpoints:

### Core Endpoints Used
- `POST /api/runs/` - Create/retrieve run records
- `POST /api/stf-files/` - Register STF files (development mode only)
- `POST /api/fastmon-files/` - Register TF files (primary endpoint)
- `POST /api/workflow-stages/` - Create workflow stage tracking
- `PATCH /api/workflow-stages/{id}/` - Update stage status and timestamps
- `POST /api/subscribers/` - Auto-register as ActiveMQ subscriber (via BaseAgent)

### FastMonFile API Schema
```json
{
  "stf_file": "parent_stf_filename.stf",
  "tf_filename": "tf_001.tf",
  "file_size_bytes": 1234567,
  "status": "registered",
  "metadata": {
    "simulation": true,
    "created_from": "stf_filename.stf",
    "agent_name": "swf-fastmon-agent-1"
  }
}
```

### Workflow Stage Tracking
The agent creates and updates workflow stages for each STF processed:
```python
# Create stage
stage_data = {
    'workflow': workflow_id,
    'agent_name': 'swf-fastmon-agent-1',
    'agent_type': 'fastmon',
    'status': 'fastmon_received',
    'input_message': {...}
}

# Update during processing
{'status': 'fastmon_processing', 'started_at': '2025-11-19T10:30:00Z'}

# Mark complete
{'status': 'fastmon_complete', 'completed_at': '2025-11-19T10:30:15Z', 'output_message': {...}}
```

## Development Commands

### System Initialization
```bash
cd $SWF_PARENT_DIR/swf-testbed
source .venv/bin/activate  # or conda activate your_env_name
pip install -e $SWF_PARENT_DIR/swf-common-lib $SWF_PARENT_DIR/swf-monitor $SWF_PARENT_DIR/swf-fastmon-agent .

# CRITICAL: Set up environment configuration
cd $SWF_PARENT_DIR/swf-fastmon-agent
cp .env.example .env
# Edit .env with actual values for SWF_MONITOR_URL, SWF_API_TOKEN, ActiveMQ credentials, etc.

# Set up Django environment (swf-monitor)
cp $SWF_PARENT_DIR/swf-monitor/.env.example $SWF_PARENT_DIR/swf-monitor/.env
# Edit .env to set DB_PASSWORD='your_db_password' and SECRET_KEY
cd $SWF_PARENT_DIR/swf-monitor/src && python manage.py migrate

# Initialize testbed
cd $SWF_PARENT_DIR/swf-testbed && swf-testbed init
```

With Django framework in place, use these standard commands:

### Django Management
- `python manage.py runserver` - Start development server
- `python manage.py makemigrations` - Create database migrations
- `python manage.py migrate` - Apply database migrations
- `python manage.py shell` - Django interactive shell
- `python manage.py dbshell` - Database shell

### Testing and Code Quality
- `python manage.py test` - Run Django tests
- `python manage.py test swf_fastmon_agent` - Run specific app tests
- `pytest` - Run all tests using pytest-django
- `pytest src/swf_fastmon_agent/tests/test_fastmon_utils.py` - Run specific test module
- `pytest -vs -q src/swf_fastmon_agent/tests/test_fastmon_utils.py` - Run with verbose output
- `black .` - Format code with Black
- `flake8 .` - Lint code with Flake8
- `isort .` - Sort imports
- `mypy src/` - Static type checking

### Database Setup
- `python setup_db.py` - Custom database setup utility

### Agent Operations
- `python -m swf_fastmon_agent.main` - Run file monitoring agent
- Use supervisord for deployment with appropriate configuration

### Client Operations
Fast monitoring client commands (from `src/swf_fastmon_client/`):
- `python -m swf_fastmon_client.main start` - Start monitoring client with default settings
- `python -m swf_fastmon_client.main start --host localhost --port 61612` - Start with custom ActiveMQ settings
- `python -m swf_fastmon_client.main start --ssl --ca-certs /path/to/ca.pem` - Start with SSL
- `python -m swf_fastmon_client.main status` - Show client configuration
- `python -m swf_fastmon_client.main version` - Show version information
- Client dependencies are included in project requirements (typer, stomp.py)

### Continuous Integration
- **GitHub Actions**: Automated testing workflow configured in `.github/workflows/test-fastmon-utils.yml`
- **Python Version**: Tests run on Python 3.11 in CI environment
- **Test Execution**: `pytest -vs -q src/swf_fastmon_agent/tests/test_fastmon_utils.py`
- **Environment**: Uses `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` to avoid external plugin conflicts

## Fast Monitoring Client Integration

### Agent-Client Messaging
The FastMon agent now sends real-time notifications to clients when TF files are registered:

#### Message Flow
1. **Agent Processing**: When STF files are processed and TF subsamples created
2. **Database Recording**: TF files are recorded in the FastMonFile table via REST API
3. **Message Broadcasting**: Agent sends notifications to `/queue/fastmon_client` queue
4. **Client Display**: Client receives and displays TF file information in formatted terminal output

#### Message Format
```json
{
  "msg_type": "tf_file_registered",
  "tf_file_id": "uuid",
  "tf_filename": "run001_stf_001_tf_001.tf",
  "file_size_bytes": 15728640,
  "stf_filename": "run001_stf_001.stf",
  "run_number": 1,
  "status": "registered",
  "timestamp": "2025-08-21T10:30:00Z",
  "agent_name": "swf-fastmon-agent"
}
```

#### Client Features
- **Real-time monitoring**: Live display of TF file registrations
- **Formatted output**: Color-coded status, human-readable file sizes
- **Statistics tracking**: Per-run TF counts, total data processed
- **Graceful shutdown**: Ctrl+C handling with summary display
- **Configurable connection**: SSL support, custom ActiveMQ settings

#### Testing and Demo
- `python test_client.py` - Basic functionality tests
- `python demo_integration.py` - Integration demonstration
- Both agent and client can run independently for testing

## Testing Infrastructure

### Test Organization
The project includes comprehensive test coverage:

```
src/swf_fastmon_agent/tests/
├── __init__.py              # Test package initialization
├── README.md                # Testing documentation
├── test_fastmon_utils.py    # Core utility function tests
└── test_api_conversion.py   # API conversion and integration tests
```

### Test Modules
- **`test_fastmon_utils.py`**: Tests core FastMon utilities including file discovery, filtering, and database operations
- **`test_api_conversion.py`**: Tests REST API integration and data conversion between agent and monitor systems
- **`test_client.py`**: Tests client functionality and integration with ActiveMQ
- **`demo_integration.py`**: Demonstrates end-to-end integration between agent and client

### Test Execution
Tests are integrated with both local development and CI/CD:
- **Local execution**: `pytest src/swf_fastmon_agent/tests/`
- **CI execution**: Automated via GitHub Actions on push/PR
- **Specific tests**: `pytest -vs -q src/swf_fastmon_agent/tests/test_fastmon_utils.py`

## Related Projects

This agent is part of a multi-module scientific workflow system. Dependencies on `swf-testbed`, `swf-monitor`, and `swf-daqsim-agent` suggest coordination with other components in the ecosystem.

## Troubleshooting

### Common Issues
- **Virtual Environment Persistence**: The shell environment, including the activated virtual environment, does **not** persist between command calls. You **MUST** chain environment setup and the command that requires it in a single call.
  - **Correct**: `cd $SWF_PARENT_DIR/swf-testbed && source .venv/bin/activate && python manage.py migrate`
  - **Incorrect**: Running `source .venv/bin/activate` in one call and `python manage.py migrate` in another.
- **Conda Environment Support**: Scripts now support both virtual environments and Conda environments. The improved environment detection checks for both `sys.prefix != sys.base_prefix` (venv) and `CONDA_DEFAULT_ENV` environment variable.
- **Core repository structure**: Ensure swf-testbed, swf-monitor, swf-common-lib, and swf-fastmon-agent are siblings
- **Database connections**: Verify PostgreSQL is running and accessible
- **ActiveMQ connectivity**: Check message broker is running on expected ports

### API Integration Issues (Recently Fixed)

The FastMon agent integrates with the swf-monitor Django REST API. Several issues were identified and resolved:

#### 1. Field Name Migration Mismatch
**Issue**: After Django migration 0016, the `file_url` field was renamed to `stf_filename`, but the agent was still using the old parameter.
**Symptoms**: API timeouts when querying for existing files
**Solution**: Updated `fastmon_utils.py` to use `stf_filename` parameter in API queries

#### 2. Missing Django REST Framework Filter Support
**Issue**: The `StfFileViewSet` lacked proper filtering configuration for query parameters
**Symptoms**: API timeouts when filtering by `stf_filename`
**Solution**: Added `DjangoFilterBackend` and `filterset_fields` to the ViewSet in swf-monitor

#### 3. Status Value Case Mismatch
**Issue**: Django model expects lowercase status values (`"registered"`) but agent was sending uppercase (`"REGISTERED"`)
**Symptoms**: HTTP 400 errors with "not a valid choice" messages
**Solution**: Updated `FileStatus` constants in `fastmon_utils.py` to match Django model choices:
```python
class FileStatus:
    REGISTERED = 'registered'  # was 'REGISTERED'
    PROCESSING = 'processing'  # was 'PROCESSING'
    PROCESSED = 'processed'    # was 'PROCESSED'
    FAILED = 'failed'         # was 'ERROR'
    DONE = 'done'             # was 'ARCHIVED'
```

#### 4. Response Format Handling
**Issue**: Agent code assumed paginated API responses `{"results": [...]}` but API sometimes returns direct lists
**Symptoms**: `'list' object has no attribute 'get'` errors
**Solution**: Added robust response handling for both formats in `get_or_create_run()` and `record_file()` functions

### Diagnostic Commands
```bash
# Check if in proper environment (works for both venv and conda)
python -c "import sys, os; print('Virtual env:', sys.prefix != sys.base_prefix); print('Conda env:', 'CONDA_DEFAULT_ENV' in os.environ)"

# Verify core repository structure
ls -la $SWF_PARENT_DIR/swf-testbed $SWF_PARENT_DIR/swf-monitor $SWF_PARENT_DIR/swf-common-lib $SWF_PARENT_DIR/swf-fastmon-agent
```

## AI Development Guidelines

**Note to AI Assistant:** The following guidelines ensure consistent, high-quality contributions aligned with the ePIC streaming workflow testbed project standards.

(Taken from the `swf-testbed` README)

### General Guidelines

- **Do not delete anything added by a human without explicit approval!!**
- **Adhere to established standards and conventions.** When implementing new features, prioritize the use of established standards, conventions, and naming schemes provided by the programming language, frameworks, or widely-used libraries. Avoid introducing custom terminology or patterns when a standard equivalent exists.
- **Portability is paramount.** All code must work across different platforms (macOS, Linux, Windows), Python installations (system, homebrew, pyenv, etc.), and deployment environments (Docker, local, cloud). Never hardcode absolute paths, assume specific installation directories, or rely on system-specific process names or command locations. Use relative paths, environment variables, and standard tools rather than platform-specific process detection. When in doubt, choose the more portable solution.
- **Favor Simplicity and Maintainability.** Strive for clean, simple, and maintainable solutions. When faced with multiple implementation options, recommend the one that is easiest to understand, modify, and debug. Avoid overly complex or clever code that might be difficult for others (or your future self) to comprehend. Adhere to the principle of "Keep It Simple, Stupid" (KISS).
- **Follow Markdown Linting Rules.** Ensure all markdown content adheres to the project's linting rules. This includes, but is not limited to, line length, list formatting, and spacing. Consistent formatting improves readability and maintainability.
- **Maintain the prompts.** Proactively suggest additions or modifications to these tips as the project evolves and new collaboration patterns emerge.

### Project-Specific Guidelines

- **Context Refresh.** To regain context on the SWF Testbed project, follow these steps:
  1. Review the high-level goals and architecture in `swf-testbed/README.md` and `swf-testbed/docs/architecture_and_design_choices.md`.
  2. Examine the dependencies and structure by checking the `pyproject.toml` and `requirements.txt` files in each sub-project (`swf-testbed`, `swf-monitor`, `swf-common-lib`).
  3. Use file and code exploration tools to investigate the existing codebase relevant to the current task. For data models, check `models.py`; for APIs, check `urls.py` and `views.py`.
  4. Consult the conversation summary to understand recent changes and immediate task objectives.

- **Verify and Propose Names.** Before implementing new names for variables, functions, classes, context keys, or other identifiers, first check for consistency with existing names across the relevant context. Once verified, propose them for review. This practice ensures clarity and reduces rework.

### Testing Guidelines

**Ensuring Robust and Future-Proof Tests:**

- Write tests that assert on outcomes, structure, and status codes—not on exact output strings or UI text, unless absolutely required for correctness.
- For CLI and UI tests, check for valid output structure (e.g., presence of HTML tags, table rows, or any output) rather than specific phrases or case.
- For API and backend logic, assert on status codes, database state, and required keys/fields, not on full response text.
- This approach ensures your tests are resilient to minor UI or output changes, reducing maintenance and avoiding false failures.
- Always run tests using the provided scripts (`./run_tests.sh` or `./run_all_tests.sh`) to guarantee the correct environment and configuration.

## Multi-Repository Development Workflow

### Infrastructure Branching Strategy

This agent repository participates in the coordinated multi-repository development workflow:

- **Always use infrastructure branches**: `infra/baseline-v1`, `infra/baseline-v2`, etc.
- **Create coordinated branches** with the same name across all affected repositories
- **Document changes** through descriptive commit messages, not branch names
- **Never push directly to main** - always use branches and pull requests

### Current Infrastructure Versions

**CURRENT STATUS**: Core repositories are on coordinated `infra/baseline-v3` branches with:
- Virtual environment documentation updates (CRITICAL warnings added)
- Top-level CLAUDE.md moved to swf-testbed/CLAUDE-toplevel.md with symlink
- Directory verification guidance added

Check for existing infrastructure branches:
```bash
# Check all repos for current infrastructure baseline
cd $SWF_PARENT_DIR
for repo in swf-testbed swf-monitor swf-common-lib swf-fastmon-agent; do
  echo "=== $repo ==="
  cd $repo && git branch -a | grep infra && cd ..
done
```

### Coordination Commands

```bash
# Create coordinated infrastructure branch across repos
cd $SWF_PARENT_DIR
for repo in swf-testbed swf-monitor swf-common-lib swf-fastmon-agent; do
  cd $repo && git checkout -b infra/baseline-vN && cd ..
done

# Run comprehensive tests across all repositories
cd swf-testbed && ./run_all_tests.sh
```

### Cross-Repository Changes

1. **Plan infrastructure phase**: Identify all repositories that need changes
2. **Create coordinated branches**: Same `infra/baseline-vN` across affected repos
3. **Work systematically**: Make changes across repositories as needed
4. **Test integration**: Run `./run_all_tests.sh` from swf-testbed before merging
5. **Coordinate merges**: Merge pull requests simultaneously across repositories

### Git Branch Management (Critical for Claude)

- **ALWAYS use `git push -u origin branch-name` on first push** - this sets up tracking
- After pushing, verify tracking with `git branch -vv` - should show `[origin/branch-name]`
- If tracking is missing, fix with: `git branch --set-upstream-to=origin/branch-name branch-name`
- VS Code "Publish branch" button indicates missing tracking - resolve immediately

## Infrastructure Services

### Two Deployment Modes

**Development Mode** (Docker-managed infrastructure):
- Managed via `swf-testbed start`, `stop`, `status` commands
- PostgreSQL and ActiveMQ run in Docker containers
- Best for development and testing

**System Mode** (System-managed infrastructure):
- Managed via `swf-testbed start-local`, `stop-local`, `status-local` commands
- Uses system-level PostgreSQL and ActiveMQ services (e.g., on production servers)
- Best for production deployment

### Service Status Checking

From swf-testbed repository:
```bash
# Docker mode
swf-testbed status

# System mode
swf-testbed status-local

# Comprehensive system readiness check
python report_system_status.py
```