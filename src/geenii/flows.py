import logging
import os
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

FLOW_FILE_SUFFIXES = (".yaml", ".yml", ".json", ".toml")


@dataclass
class FlowSpec:
    name: str
    filepath: str


@dataclass
class FlowRegistry:
    flows: list[FlowSpec] = field(default_factory=list)

    def register(self, flow: FlowSpec):
        self.flows.append(flow)

    def load_all_from_dir(self, dirpath: str):
        """Add all yaml, toml and json files in dirpath (if it exists)"""
        if not os.path.isdir(dirpath):
            return
        for filename in sorted(os.listdir(dirpath)):
            filepath = os.path.join(dirpath, filename)
            if os.path.isfile(filepath) and filename.lower().endswith(FLOW_FILE_SUFFIXES):
                flow = FlowSpec(name=os.path.splitext(filename)[0], filepath=filepath)
                logger.debug(f"Adding flow: {flow}")
                self.flows.append(flow)
