import abc
import json
import threading
import time
from pathlib import Path
import httpx

class HumanInTheLoopController(abc.ABC):
    """
    This class can be used to handle human-in-the-loop interactions for tool call approvals or other decision points in the agent's process.
    """
    # True if the human answers through the agent's own message stream (e.g. a web chat).
    # The agent then forwards its approval requests (UserInteractionContent messages) to the caller.
    interactive: bool = False

    @abc.abstractmethod
    def request_tool_execution(self, tool_name: str, arguments: dict, call_id: str) -> bool:
        """
        Abstract method to implement logic for approving or rejecting tool execution requests.
        :param tool_name: The name of the tool that is requested to be executed.
        :param arguments: The arguments that will be passed to the tool if approved.
        :param call_id: A unique identifier for the tool call request, which can be used to track and match with the tool call result.
        :return: A boolean indicating whether the tool execution is approved (True) or rejected (False).
        """
        ...


class NoHumanInTheLoopController(HumanInTheLoopController):
    """
    HITL handler that automatically approves all tool execution requests without any human intervention.
    """
    def request_tool_execution(self, tool_name: str, arguments: dict, call_id: str) -> bool:
        return True


class FileTicketHumanInTheLoopController(HumanInTheLoopController):
    """
    HITL handler that creates a file-based ticket for each tool execution request and waits for a human to approve it by creating an approval file.
    - When a tool execution request is received, it creates a ticket file in a specified directory
        with the tool name, arguments, and call ID.
    - It then waits for an approval file to be created with the same call ID, which indicates that a human has approved the request.
    - If the approval file is detected within a certain timeout period, it returns True to approve the tool execution; otherwise, it returns False to reject it.
    """
    def __init__(self, ticket_dir: str, approval_timeout: int = 300):
        self.approval_timeout = approval_timeout
        self.ticket_path = Path(ticket_dir).resolve()
        self.ticket_path.mkdir(parents=True, exist_ok=True)

    def request_tool_execution(self, tool_name: str, arguments: dict, call_id: str) -> bool:
        ticket_file = self.ticket_path / f"{call_id}.json"
        approval_file = self.ticket_path / f"{call_id}.approved"
        rejected_file = self.ticket_path / f"{call_id}.rejected"

        # Create the ticket file with tool execution details
        with ticket_file.open("w") as f:
            json.dump({
                "tool_name": tool_name,
                "arguments": arguments,
                "call_id": call_id,
                "timestamp": time.time(),
            }, f, indent=2)

        print(f"Created HITL ticket for tool '{tool_name}' with call ID '{call_id}'. Waiting for approval...")

        # Wait for the approval file to be created
        start_time = time.time()
        approved = False
        while time.time() - start_time < self.approval_timeout:
            if approval_file.exists():
                print(f"Approval received for call ID '{call_id}'. Approving tool execution.")
                approved = True
                break
            elif rejected_file.exists():
                print(f"Rejection received for call ID '{call_id}'. Rejecting tool execution.")
                approved = False
                break
            time.sleep(1)

        if time.time() - start_time >= self.approval_timeout:
            print(f"Approval timeout reached for call ID '{call_id}'.")

        ticket_file.unlink(missing_ok=True)
        approval_file.unlink(missing_ok=True)
        rejected_file.unlink(missing_ok=True)
        return approved


class HttpPollHumanInTheLoopController(HumanInTheLoopController):
    """
    HITL handler that polls an HTTP endpoint for approving or rejecting tool execution requests.
    - When a tool execution request is received, an HTTP POST request is sent to a specified approval endpoint with the tool name, arguments, and call ID.
    - The endpoint is expected to return a JSON response with an "approved" field
    - The handler waits for the response and returns True if approved, or False if rejected or if a timeout occurs.
    """
    def __init__(self, approval_endpoint: str, approval_timeout: int = 300):
        self.approval_endpoint = approval_endpoint
        self.approval_timeout = approval_timeout

    def request_tool_execution(self, tool_name: str, arguments: dict, call_id: str) -> bool:
        with httpx.Client() as client:
            try:
                response = client.post(self.approval_endpoint, json={
                    "tool_name": tool_name,
                    "arguments": arguments,
                    "call_id": call_id,
                }, timeout=self.approval_timeout)
                response.raise_for_status()
                data = response.json()
                approved = data.get("approved", False)
                if approved:
                    print(f"Approval received for call ID '{call_id}'. Approving tool execution.")
                else:
                    print(f"Rejection received for call ID '{call_id}'. Rejecting tool execution.")
                return approved
            except Exception as e:
                print(f"Error while requesting approval for call ID '{call_id}': {e}")
                return False


class WebHumanInTheLoopController(HumanInTheLoopController):
    """
    HITL handler for chat clients that answer approval requests out of band (e.g. via an HTTP endpoint).
    - The agent yields an approval request message (interaction_id == call_id) and then blocks in request_tool_execution.
    - `respond(call_id, choice)` unblocks it; "Allow" approves, any other choice rejects.
    - Unanswered requests are rejected after approval_timeout seconds, and all of them when `cancel()` is called.
    An answer may arrive before the agent starts waiting; it is kept until then.
    """
    interactive = True

    APPROVE_CHOICES = {"allow", "approve", "yes"}

    def __init__(self, approval_timeout: float = 300):
        self.approval_timeout = approval_timeout
        self._lock = threading.Lock()
        self._events: dict[str, threading.Event] = {}
        self._answers: dict[str, str] = {}
        self._expected: set[str] = set()
        self._cancelled = False

    def reset(self) -> None:
        """Forget all requests and the cancelled state; call before starting a new turn."""
        with self._lock:
            events = list(self._events.values())
            self._events.clear()
            self._answers.clear()
            self._expected.clear()
            self._cancelled = False
        for event in events:
            event.set()

    def expect(self, call_id: str) -> None:
        """Register a request that was sent to the client, so it can be answered (even before the agent waits)."""
        with self._lock:
            self._expected.add(call_id)
            self._events.setdefault(call_id, threading.Event())

    def is_pending(self, call_id: str) -> bool:
        with self._lock:
            return call_id in self._expected and call_id not in self._answers

    def respond(self, call_id: str, choice: str) -> bool:
        """Answer a request. Returns False if no such request is pending."""
        with self._lock:
            if call_id not in self._expected or call_id in self._answers:
                return False
            self._answers[call_id] = choice
            event = self._events[call_id]
        event.set()
        return True

    def cancel(self) -> None:
        """Reject all pending and future requests of this run."""
        with self._lock:
            self._cancelled = True
            events = list(self._events.values())
        for event in events:
            event.set()

    def request_tool_execution(self, tool_name: str, arguments: dict, call_id: str) -> bool:
        with self._lock:
            if self._cancelled:
                return False
            self._expected.add(call_id)
            event = self._events.setdefault(call_id, threading.Event())

        event.wait(self.approval_timeout)

        with self._lock:
            choice = None if self._cancelled else self._answers.get(call_id)
            # answered or timed out: no longer answerable
            self._expected.discard(call_id)
            self._events.pop(call_id, None)
            self._answers.pop(call_id, None)
        return choice is not None and choice.strip().lower() in self.APPROVE_CHOICES
