import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.dirname(SCRIPT_DIR))

try:
    from .unity_module_registry_manager import UnityModuleRegistryManager
except ImportError:
    from unity_module_registry_manager import UnityModuleRegistryManager

# Refresh is rerun-safe: only rescans if unity project path is configured
from managers.config_manager import cm

unity_project_path = cm.raw_config.get("unity_module_registry", {}).get("unity_project_path")
if unity_project_path:
    registry = UnityModuleRegistryManager(unity_project_path=unity_project_path)
    registry.scan_modules()
    registry.save_registry()
