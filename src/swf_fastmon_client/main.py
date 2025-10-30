#!/usr/bin/env python3
"""
Fast Monitoring Client for SWF Testbed

This client receives TF file notifications from the swf-fastmon-agent
and displays them in real-time in the terminal.
"""

import os
import sys
import json
import time
import signal
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path

import typer
import requests


class FastMonitoringClient:
    """
    Client that receives TF file notifications via SSE and displays monitoring information.
    """

    def __init__(self, monitor_base_url=None, api_token=None):
        """Initialize the fast monitoring client."""
        # Setup environment variables from ~/.env file if present
        self._setup_environment()
        
        # Monitor configuration
        self.monitor_base_url = monitor_base_url or os.getenv('SWF_MONITOR_URL', 'http://localhost:8002').rstrip('/')
        self.api_token = api_token or os.getenv('SWF_API_TOKEN')
        
        if not self.api_token:
            raise ValueError("SWF_API_TOKEN environment variable is required")
        
        # Client-specific state
        self.tf_files_received = 0
        self.total_file_size = 0
        self.run_statistics = {}
        self.start_time = datetime.now()
        self.running = True
        
        # HTTP session configuration
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Token {self.api_token}',
            'Cache-Control': 'no-cache',
            'Accept': 'text/event-stream',
            'Connection': 'keep-alive',
        })
        
        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        print("🔧 Fast Monitoring Client initialized")
        print(f"   Monitor URL: {self.monitor_base_url}")
        print(f"   Token prefix: {self.api_token[:12]}..." if len(self.api_token) >= 12 else "   Token: [short token]")

    def _setup_environment(self):
        """Load environment variables from ~/.env file if present."""
        env_file = Path.home() / ".env"
        if env_file.exists():
            with env_file.open() as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#') or '=' not in line:
                        continue
                    if line.startswith('export '):
                        line = line[7:]
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip("'\"")

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        print(f"\n📡 Received signal {signum}, shutting down gracefully...")
        self.running = False

    def connect_and_receive(self, msg_types=None, agents=None):
        """Connect to SSE stream and process messages in a loop."""
        # Build stream URL with filters
        stream_url = f"{self.monitor_base_url}/api/messages/stream/"
        params = []
        if msg_types:
            params.append(f"msg_types={','.join(msg_types)}")
        if agents:
            params.append(f"agents={','.join(agents)}")
        if params:
            stream_url += "?" + "&".join(params)
        
        status_url = f"{self.monitor_base_url}/api/messages/stream/status/"
        print(f"📡 Connecting to SSE stream: {stream_url}")

        while self.running:
            try:
                # Status precheck
                print("🔌 Testing SSE endpoint...")
                status_resp = self.session.get(status_url, timeout=20, allow_redirects=False, headers={'Accept': 'application/json'})
                if status_resp.status_code != 200:
                    if status_resp.status_code in (401, 403):
                        print(f"❌ Auth failed (HTTP {status_resp.status_code}). Check SWF_API_TOKEN.")
                    else:
                        print(f"❌ SSE endpoint not available: HTTP {status_resp.status_code}")
                    print("   Retrying in 15 seconds...")
                    time.sleep(15)
                    continue

                # Open the SSE stream
                response = self.session.get(stream_url, stream=True, timeout=(10, 3600), allow_redirects=False)
                if response.status_code != 200:
                    if response.status_code in (401, 403):
                        print(f"❌ Auth failed opening stream (HTTP {response.status_code}). Check SWF_API_TOKEN.")
                    else:
                        print(f"❌ Failed to open stream: HTTP {response.status_code}")
                    print("   Retrying in 15 seconds...")
                    time.sleep(15)
                    continue

                print("✅ SSE stream opened - waiting for events... (Ctrl+C to exit)")
                print("-" * 60)
                
                # Process SSE stream
                self._process_sse_stream(response)

            except requests.exceptions.ReadTimeout as e:
                print(f"⏱️  Read timeout while waiting for messages: {e}")
                print("   Reconnecting in 15 seconds...")
                time.sleep(15)
            except requests.exceptions.RequestException as e:
                print(f"❌ Connection error: {e}")
                print("   Retrying in 15 seconds...")
                time.sleep(15)
            except Exception as e:
                print(f"❌ Unexpected error: {e}")
                time.sleep(15)

    def _process_sse_stream(self, response):
        """Process the SSE stream for incoming messages."""
        event_buffer = []
        try:
            for line in response.iter_lines(decode_unicode=True, chunk_size=1):
                if line is None:
                    continue
                line = line.strip()
                if not line:
                    if event_buffer:
                        self._handle_sse_event(event_buffer)
                        event_buffer = []
                else:
                    event_buffer.append(line)
        except KeyboardInterrupt:
            print("\n📡 Received interrupt - closing connection...")
        except Exception as e:
            print(f"❌ Error processing stream: {e}")
        finally:
            try:
                response.close()
            except Exception:
                pass

    def _handle_sse_event(self, event_lines):
        """Handle a single SSE event."""
        event_type = "message"
        event_data = ""
        for line in event_lines:
            if line.startswith('event: '):
                event_type = line[7:]
            elif line.startswith('data: '):
                event_data = line[6:]

        timestamp = time.strftime("%H:%M:%S")
        if event_type == "connected":
            print(f"[{timestamp}] 🔗 Connected to SSE stream")
            try:
                data = json.loads(event_data)
                client_id = data.get('client_id', 'unknown')
                print(f"[{timestamp}] 📋 Client ID: {client_id}")
            except Exception:
                pass
        elif event_type == "heartbeat":
            # Stay quiet on heartbeats to avoid log spam
            return
        else:
            try:
                data = json.loads(event_data)
                msg_type = data.get('msg_type', 'unknown')
                
                if msg_type == 'tf_file_registered':
                    self._handle_tf_file_notification(data)
                else:
                    print(f"[{timestamp}] 📨 Other message: {msg_type}")
            except json.JSONDecodeError:
                print(f"[{timestamp}] 📨 Non-JSON message: {event_data}")
            except Exception as e:
                print(f"[{timestamp}] ❌ Error parsing message: {e}")

    def _handle_tf_file_notification(self, message_data: Dict[str, Any]):
        """
        Process and display TF file notification.
        
        Args:
            message_data: TF file notification data
        """
        try:
            # Extract notification data
            tf_file_id = message_data.get('tf_file_id')
            tf_filename = message_data.get('tf_filename')
            file_size = message_data.get('file_size_bytes', 0)
            stf_filename = message_data.get('stf_filename')
            run_number = message_data.get('run_number')
            status = message_data.get('status')
            timestamp = message_data.get('timestamp')
            agent_name = message_data.get('agent_name')

            # Update statistics
            self.tf_files_received += 1
            self.total_file_size += file_size
            
            # Update run statistics
            if run_number:
                if run_number not in self.run_statistics:
                    self.run_statistics[run_number] = {
                        'tf_count': 0, 
                        'total_size': 0, 
                        'first_seen': timestamp
                    }
                self.run_statistics[run_number]['tf_count'] += 1
                self.run_statistics[run_number]['total_size'] += file_size

            # Display notification
            self._display_tf_notification(
                tf_filename, file_size, stf_filename, run_number, status, timestamp
            )

            self.logger.debug(f"Processed TF file notification: {tf_filename}")

        except Exception as e:
            self.logger.error(f"Error handling TF file notification: {e}")

    def _display_tf_notification(self, tf_filename: str, file_size: int, 
                                stf_filename: str, run_number: int, 
                                status: str, timestamp: str):
        """
        Display TF file notification in formatted terminal output.
        """
        try:
            # Parse timestamp
            ts = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            time_str = ts.strftime('%H:%M:%S')
            
            # Format file size
            if file_size > 1024 * 1024:
                size_str = f"{file_size / (1024*1024):.1f}MB"
            elif file_size > 1024:
                size_str = f"{file_size / 1024:.1f}KB"
            else:
                size_str = f"{file_size}B"

            # Color coding for status
            status_color = {
                'registered': '\033[92m',  # Green
                'processing': '\033[93m',  # Yellow
                'processed': '\033[94m',   # Blue
                'failed': '\033[91m',      # Red
                'done': '\033[95m'         # Magenta
            }.get(status.lower(), '\033[0m')  # Default no color
            
            reset_color = '\033[0m'

            # Print formatted notification
            print(f"[{time_str}] TF: {tf_filename:<25} | "
                  f"Size: {size_str:>8} | "
                  f"STF: {stf_filename:<20} | "
                  f"Run: {run_number:>4} | "
                  f"Status: {status_color}{status:<10}{reset_color}")

        except Exception as e:
            # Fallback to simple display if formatting fails
            print(f"[{timestamp}] TF: {tf_filename} | Size: {file_size} | STF: {stf_filename} | Run: {run_number} | Status: {status}")

    def display_summary(self):
        """Display summary statistics."""
        uptime = datetime.now() - self.start_time
        uptime_str = str(uptime).split('.')[0]  # Remove microseconds
        
        print("\n" + "="*80)
        print("FAST MONITORING CLIENT SUMMARY")
        print("="*80)
        print(f"Uptime: {uptime_str}")
        print(f"TF Files Received: {self.tf_files_received}")
        print(f"Total Data Size: {self.total_file_size / (1024*1024):.2f} MB")
        
        if self.run_statistics:
            print(f"Active Runs: {len(self.run_statistics)}")
            print("\nRun Statistics:")
            print("-" * 50)
            for run_num, stats in sorted(self.run_statistics.items()):
                print(f"  Run {run_num:>4}: {stats['tf_count']:>3} TF files, "
                      f"{stats['total_size'] / (1024*1024):.2f} MB")
        
        print("="*80)

    def start_monitoring(self, msg_types=None, agents=None):
        """
        Start the monitoring client with SSE stream connection.
        """
        print("\n" + "="*80)
        print("FAST MONITORING CLIENT STARTED (SSE)")
        print("="*80)
        print(f"Monitor URL: {self.monitor_base_url}")
        print(f"Started at: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        if msg_types or agents:
            filters = []
            if msg_types:
                filters.append(f"messages: {', '.join(msg_types)}")
            if agents:
                filters.append(f"agents: {', '.join(agents)}")
            print(f"🔍 Filtering enabled - {' | '.join(filters)}")
        else:
            print("📬 Receiving all messages (no filtering)")
            
        print("Press Ctrl+C to stop")
        print("="*80)
        print("TF File Notifications:")
        print("-" * 80)

        try:
            self.connect_and_receive(msg_types=msg_types, agents=agents)
        except KeyboardInterrupt:
            print("\n📡 Received interrupt signal")
        except Exception as e:
            print(f"❌ Monitoring error: {e}")
        finally:
            self.display_summary()


# Typer CLI Application
app = typer.Typer(help="Fast Monitoring Client for ePIC SWF Testbed")


@app.command()
def start(
    monitor_url: str = typer.Option("http://localhost:8002", "--monitor-url", "-m", help="Monitor base URL"),
    api_token: Optional[str] = typer.Option(None, "--api-token", "-t", help="API token for authentication"),
    message_types: Optional[str] = typer.Option(None, "--message-types", help="Filter by message types (comma-separated)"),
    agents: Optional[str] = typer.Option(None, "--agents", help="Filter by agent names (comma-separated)")
):
    """Start the fast monitoring client with SSE streaming."""
    
    # Parse comma-separated values
    msg_types = None
    if message_types:
        msg_types = [t.strip() for t in message_types.split(',')]
    
    agent_list = None
    if agents:
        agent_list = [a.strip() for a in agents.split(',')]

    try:
        # Create and start client
        client = FastMonitoringClient(monitor_base_url=monitor_url, api_token=api_token)
        client.start_monitoring(msg_types=msg_types, agents=agent_list)
    except ValueError as e:
        typer.echo(f"Configuration error: {e}", err=True)
        typer.echo("Set SWF_API_TOKEN environment variable or use --api-token", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"Error starting client: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def status():
    """Show client status and configuration."""
    typer.echo("Fast Monitoring Client Status (SSE)")
    typer.echo("=" * 40)
    typer.echo(f"Monitor URL: {os.getenv('SWF_MONITOR_URL', 'http://localhost:8002')}")
    typer.echo(f"API Token: {'Set' if os.getenv('SWF_API_TOKEN') else 'Not set'}")
    typer.echo(f"SSE Stream: /api/messages/stream/")
    typer.echo(f"Message Types: All (filter with --message-types)")
    typer.echo(f"Agents: All (filter with --agents)")


@app.command()
def version():
    """Show client version information."""
    typer.echo("Fast Monitoring Client (SSE)")
    typer.echo("Part of ePIC SWF Testbed")
    typer.echo("Uses Server-Sent Events for real-time monitoring")


if __name__ == "__main__":
    app()
