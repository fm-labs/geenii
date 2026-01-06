# Description: FastAPI routes for the Agent Protocol (AP) API.
# https://agentprotocol.ai/specification/
# https://github.com/agi-inc/agent-protocol/blob/main/schemas/openapi.yml

from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, Query

from geenii.ap.models import StepStatus, Pagination, Artifact, TaskRequestBody, Task, StepRequestBody, Step, \
    TaskListResponse, TaskStepsListResponse, TaskArtifactsListResponse, StepInput

# Create APIRouter
router = APIRouter(prefix="/ap/v1/agent", tags=["agentprotocol"])


def build_dummy_agent_task_with_steps() -> tuple[Task, list[Step]]:
    """Helper function to build a dummy agent task with steps for testing."""
    step_handlers = {
        "6bb1801a-fd80-45e8-899a-4dd723cc602e": lambda input: f"Output of step 1 based on input: {input}",
        "7cc2802b-ge91-56f9-a00b-5ee834dd703f": lambda input: f"Output of step 2 based on input: {input}",
    }

    step1 = Step(
        task_id="50da533e-3904-4401-8a07-c49adf88b5eb",
        step_id="6bb1801a-fd80-45e8-899a-4dd723cc602e",
        name="Step 1",
        input="Initial input for step 1",
        additional_input=StepInput(
            agent="default",
        ),
        status=StepStatus.created,
        is_last=False,
        artifacts=[],
        output="Output of step 1"
    )

    step2 = Step(
        task_id="50da533e-3904-4401-8a07-c49adf88b5eb",
        step_id="7cc2802b-ge91-56f9-a00b-5ee834dd703f",
        name="Step 2",
        input="Input for step 2 based on step 1 output",
        additional_input=None,
        status=StepStatus.created,
        is_last=True,
        artifacts=[],
        output=None,
        additional_output=None
    )

    task = Task(
        task_id="50da533e-3904-4401-8a07-c49adf88b5eb",
        input="Example task input",
        additional_input=None,
        artifacts=[],
    )

    steps = [step1, step2]

    return task, steps




# Task endpoints
@router.post("/tasks", response_model=Task, status_code=200)
async def create_agent_task(body: TaskRequestBody):
    """Creates a task for the agent."""
    # Placeholder implementation
    return Task(
        task_id="50da533e-3904-4401-8a07-c49adf88b5eb",
        input=body.input,
        additional_input=body.additional_input,
        artifacts=[]
    )


@router.get("/tasks", response_model=TaskListResponse, status_code=200)
async def list_agent_tasks(
    current_page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, description="Number of items per page")
):
    """List all tasks that have been created for the agent."""
    # Placeholder implementation
    return TaskListResponse(
        tasks=[],
        pagination=Pagination(
            total_items=0,
            total_pages=0,
            current_page=current_page,
            page_size=page_size
        )
    )


@router.get("/tasks/{task_id}", response_model=Task, status_code=200)
async def get_agent_task(task_id: str = "1d5a533e-3904-4401-8a07-c49adf88b981"):
    """Get details about a specified agent task."""
    # Placeholder implementation
    return Task(
        task_id=task_id,
        input="Example task",
        artifacts=[]
    )


# Step endpoints
@router.get("/tasks/{task_id}/steps", response_model=TaskStepsListResponse, status_code=200)
async def list_agent_task_steps(
    task_id: str,
    current_page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, description="Number of items per page")
):
    """List all steps for the specified task."""
    # Placeholder implementation
    return TaskStepsListResponse(
        steps=[],
        pagination=Pagination(
            total_items=0,
            total_pages=0,
            current_page=current_page,
            page_size=page_size
        )
    )


@router.post("/tasks/{task_id}/steps", response_model=Step, status_code=200)
async def execute_agent_task_step(task_id: str, body: StepRequestBody):
    """Execute a step in the specified agent task."""
    # Placeholder implementation
    return Step(
        task_id=task_id,
        step_id="6bb1801a-fd80-45e8-899a-4dd723cc602e",
        name="Example Step",
        input=body.input,
        additional_input=body.additional_input,
        status=StepStatus.created,
        is_last=False,
        artifacts=[],
        output=None
    )


@router.get("/tasks/{task_id}/steps/{step_id}", response_model=Step, status_code=200)
async def get_agent_task_step(task_id: str, step_id: str):
    """Get details about a specified task step."""
    # Placeholder implementation
    return Step(
        task_id=task_id,
        step_id=step_id,
        status=StepStatus.created,
        is_last=False,
        artifacts=[]
    )


# Artifact endpoints
@router.get("/tasks/{task_id}/artifacts", response_model=TaskArtifactsListResponse, status_code=200)
async def list_agent_task_artifacts(
    task_id: str,
    current_page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, description="Number of items per page")
):
    """List all artifacts that have been created for the given task."""
    # Placeholder implementation
    return TaskArtifactsListResponse(
        artifacts=[],
        pagination=Pagination(
            total_items=0,
            total_pages=0,
            current_page=current_page,
            page_size=page_size
        )
    )


@router.post("/tasks/{task_id}/artifacts", response_model=Artifact, status_code=200)
async def upload_agent_task_artifacts(
    task_id: str,
    file: UploadFile = File(None, description="File to upload."),
    relative_path: Optional[str] = Form(None, examples=["python/code"], description="Relative path of the artifact in the agent's workspace.")
):
    """Upload an artifact for the specified task."""
    # Placeholder implementation
    return Artifact(
        artifact_id="b225e278-8b4c-4f99-a696-8facf19f0e56",
        agent_created=False,
        file_name=file.filename or "unknown",
        relative_path=relative_path
    )


@router.get("/tasks/{task_id}/artifacts/{artifact_id}", status_code=200)
async def download_agent_task_artifact(task_id: str, artifact_id: str):
    """Download a specified artifact."""
    # Placeholder implementation
    # In a real implementation, this would return StreamingResponse with binary content
    return {"message": "Binary content would be returned here"}


# Exception handlers can be added to the main app
# Example:
# @app.exception_handler(404)
# async def not_found_handler(request, exc):
#     return JSONResponse(
#         status_code=404,
#         content={"message": "Unable to find entity with the provided id"}
#     )