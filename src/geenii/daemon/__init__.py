"""
The geenii daemon: one asyncio process hosting the Process Manager, Scheduler
and Supervisor behind a single Unix socket.

    client.py – DaemonClient (sync, lightweight; safe to import from agents/CLI)
    host.py   – ProcessHost: owns the three components and their RPC methods
    server.py – DaemonServer: socket server, lifecycle, `geenii daemon` entry point

This package deliberately imports nothing eagerly, so importing the client
does not pull in the scheduler or supervisor.
"""
