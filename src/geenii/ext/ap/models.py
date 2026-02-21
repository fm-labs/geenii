from enum import Enum
from typing import Optional, List

from pydantic import BaseModel, Field


class StepStatus(str, Enum):
    created = "created"
    running = "running"
    completed = "completed"


class Pagination(BaseModel):
    total_items: int = Field(..., examples=[42], description="Total number of items.")
    total_pages: int = Field(..., examples=[97], description="Total number of pages.")
    current_page: int = Field(..., examples=[1], description="Current page number.")
    page_size: int = Field(..., examples=[25], description="Number of items per page.")


class TaskInput(BaseModel):
    """Input parameters for the task. Any value is allowed."""
    model_config = {
        "extra": "allow",
        "json_schema_extra": {
            "example": {
                "debug": False,
                "mode": "benchmarks"
            }
        }
    }


class StepInput(BaseModel):
    """Input parameters for the task step. Any value is allowed."""
    model_config = {
        "extra": "allow",
        "json_schema_extra": {
            "example": {
                "file_to_refactor": "models.py"
            }
        }
    }


class StepOutput(BaseModel):
    """Output that the task step has produced. Any value is allowed."""
    model_config = {
        "extra": "allow",
        "json_schema_extra": {
            "example": {
                "tokens": 7894,
                "estimated_cost": "0,24$"
            }
        }
    }


class Artifact(BaseModel):
    """An Artifact either created by or submitted to the agent."""
    artifact_id: str = Field(..., examples=["b225e278-8b4c-4f99-a696-8facf19f0e56"], description="ID of the artifact.")
    agent_created: bool = Field(..., examples=[False], description="Whether the artifact has been created by the agent.")
    file_name: str = Field(..., examples=["main.py"], description="Filename of the artifact.")
    relative_path: Optional[str] = Field(None, examples=["python/code/"], description="Relative path of the artifact in the agent's workspace.")


class TaskRequestBody(BaseModel):
    """Body of the task request."""
    input: Optional[str] = Field(None, examples=["Write 'Washington' to the file 'output.txt'."], description="Input prompt for the task.")
    additional_input: Optional[TaskInput] = None


class Task(TaskRequestBody):
    """Definition of an agent task."""
    task_id: str = Field(..., examples=["50da533e-3904-4401-8a07-c49adf88b5eb"], description="The ID of the task.")
    artifacts: List[Artifact] = Field(default_factory=list, examples=[["7a49f31c-f9c6-4346-a22c-e32bc5af4d8e", "ab7b4091-2560-4692-a4fe-d831ea3ca7d6"]], description="A list of artifacts that the task has produced.")


class StepRequestBody(BaseModel):
    """Body of the task request."""
    input: Optional[str] = Field(None, examples=["Write the words you receive to the file 'output.txt'."], description="Input prompt for the step.")
    additional_input: Optional[StepInput] = None


class Step(StepRequestBody):
    """Definition of a task step."""
    task_id: str = Field(..., description="The ID of the task this step belongs to.")
    step_id: str = Field(..., examples=["6bb1801a-fd80-45e8-899a-4dd723cc602e"], description="The ID of the task step.")
    name: Optional[str] = Field(None, examples=["Write to file"], description="The name of the task step.")
    status: StepStatus = Field(..., examples=["created"], description="The status of the task step.")
    output: Optional[str] = Field(None, examples=["I am going to use the write_to_file command and write Washington to a file called output.txt <write_to_file('output.txt', 'Washington')"], description="Output of the task step.")
    additional_output: Optional[StepOutput] = None
    artifacts: List[Artifact] = Field(default_factory=list, description="A list of artifacts that the step has produced.")
    is_last: bool = Field(False, examples=[True], description="Whether this is the last step in the task.")


class TaskListResponse(BaseModel):
    tasks: List[Task]
    pagination: Pagination


class TaskStepsListResponse(BaseModel):
    steps: List[Step]
    pagination: Pagination


class TaskArtifactsListResponse(BaseModel):
    artifacts: List[Artifact]
    pagination: Pagination


class NotFoundResponse(BaseModel):
    message: str = Field(..., examples=["Unable to find entity with the provided id"], description="Message stating the entity was not found")
