from __future__ import annotations

from pathlib import Path
from threading import Lock
from typing import Dict

import yaml
from pydantic import ValidationError

from app.schemas.config_schema import WorkflowConfig
from app.utils.exceptions import ConfigValidationError, WorkflowNotFoundError


_WORKFLOW_CACHE: Dict[str, WorkflowConfig] = {}
_CONFIG_DIR: Path | None = None
_LOCK = Lock()


def load_workflow_config(yaml_path: str) -> WorkflowConfig:
	path = Path(yaml_path)
	if not path.exists() or not path.is_file():
		raise ConfigValidationError(f"Workflow config path not found: {yaml_path}")

	try:
		with path.open("r", encoding="utf-8") as f:
			raw = yaml.safe_load(f) or {}
		config = WorkflowConfig.model_validate(raw)
	except (yaml.YAMLError, ValidationError) as exc:
		raise ConfigValidationError(f"Invalid workflow config '{path.name}': {exc}") from exc

	return config


def load_all_workflows(config_dir: str) -> Dict[str, WorkflowConfig]:
	global _WORKFLOW_CACHE, _CONFIG_DIR

	directory = Path(config_dir)
	if not directory.exists() or not directory.is_dir():
		raise ConfigValidationError(f"Workflow directory not found: {config_dir}")

	loaded: Dict[str, WorkflowConfig] = {}
	for yaml_path in sorted(directory.glob("*.yaml")):
		workflow = load_workflow_config(str(yaml_path))
		loaded[workflow.workflow_id] = workflow

	if not loaded:
		raise ConfigValidationError(f"No workflow YAML files found in {config_dir}")

	with _LOCK:
		_WORKFLOW_CACHE = loaded
		_CONFIG_DIR = directory

	return dict(_WORKFLOW_CACHE)


def reload_configs() -> Dict[str, WorkflowConfig]:
	if _CONFIG_DIR is None:
		raise ConfigValidationError("Configuration directory is not initialized")
	return load_all_workflows(str(_CONFIG_DIR))


def get_workflow(workflow_id: str) -> WorkflowConfig:
	workflow = _WORKFLOW_CACHE.get(workflow_id)
	if not workflow:
		raise WorkflowNotFoundError(f"Workflow '{workflow_id}' not found")
	return workflow


def get_all_workflows() -> Dict[str, WorkflowConfig]:
	return dict(_WORKFLOW_CACHE)
