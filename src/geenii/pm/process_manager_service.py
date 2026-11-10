"""
Compatibility wrapper: the process manager is now served by the geenii daemon
(geenii.daemon), which also hosts the scheduler and the supervisor.

`ProcessManagerService` and this module's `main()` are kept so existing code
and `python -m geenii.pm.process_manager_service` keep working; both run the
daemon. The former unprefixed methods (start, status, ...) remain available
as aliases of pm.start, pm.status, ...
"""

from __future__ import annotations

import sys
from typing import Optional

from geenii.daemon.client import DEFAULT_SOCKET_PATH  # noqa: F401  (re-exported)
from geenii.daemon.host import ProcessHost
from geenii.daemon.server import DaemonServer
from geenii.pm.process_manager import ProcessManager


class ProcessManagerService(DaemonServer):
    """A daemon whose ProcessHost uses the given ProcessManager (and an idle scheduler)."""

    def __init__(
        self, socket_path: Optional[str] = None, pm: Optional[ProcessManager] = None
    ) -> None:
        super().__init__(ProcessHost(pm=pm), socket_path)


def main() -> None:
    from geenii.daemon.server import main as daemon_main

    args = sys.argv[1:]
    # Former usage: `python -m geenii.pm.process_manager_service [SOCKET_PATH]`
    if args and not args[0].startswith("-"):
        args = ["--socket", args[0], *args[1:]]
    daemon_main(args)


if __name__ == "__main__":
    main()
