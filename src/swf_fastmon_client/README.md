# SWF Fast Monitoring Client

**`swf-fastmon-client`** for the ePIC streaming workflow testbed.

Client application that receives information about Time Frames (TFs) from the `swf-fastmon-agent` to monitor the ePIC data acquisition.

The client is designed to be executed anywhere, with minimal infrastructure requirements, allowing users to 
monitor the ePIC data acquisition remotely.

**Note: it will become a standalone application in the near future, but for now it is a part of the `swf-fastmon-agent` repository.**

## Architecture Overview

The client is designed to receive metadata from the `swf-fastmon-agent` and display it in a user-friendly format/web interface. 

* It uses ActiveMQ to receive TFs metadata via SSE protocol.
* Uses Typer for command-line interface.
* It can be extended to provide a web interface for monitoring (like a Grafana dashboard).
