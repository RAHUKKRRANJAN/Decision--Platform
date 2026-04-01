from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.utils.exceptions import ConfigValidationError, WorkflowNotFoundError
from config.loader import get_all_workflows, get_workflow, reload_configs


router = APIRouter(prefix="/config", tags=["config"])


@router.get("/workflows")
async def list_workflows():
	workflows = get_all_workflows().values()
	return [
		{
			"workflow_id": wf.workflow_id,
			"workflow_name": wf.workflow_name,
			"version": wf.version,
			"stage_count": len(wf.stages),
		}
		for wf in workflows
	]


@router.get("/workflows/{workflow_id}")
async def get_workflow_details(workflow_id: str):
	try:
		wf = get_workflow(workflow_id)
	except WorkflowNotFoundError as exc:
		raise HTTPException(status_code=404, detail=str(exc)) from exc
	return wf.model_dump()


@router.post("/reload")
async def reload_workflow_configs():
	try:
		refreshed = reload_configs()
	except ConfigValidationError as exc:
		raise HTTPException(status_code=400, detail=str(exc)) from exc

	return {
		"reloaded": [
			{"workflow_id": wf.workflow_id, "version": wf.version}
			for wf in refreshed.values()
		]
	}
