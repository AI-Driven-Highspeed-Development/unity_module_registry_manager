"""Unity Module Registry Manager

Scans Unity project folders and maintains a registry of discovered modules.
Supports automatic detection of module types based on folder structure.

Usage:
    from managers.unity_module_registry_manager import UnityModuleRegistryManager
    
    registry = UnityModuleRegistryManager(unity_project_path="../MyUnityProject")
    modules = registry.scan_modules()
    registry.save_registry()
"""

# Add path handling to work from the new nested directory structure
import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.getcwd()  # Use current working directory as project root
sys.path.insert(0, project_root)

from managers.unity_module_registry_manager.unity_module_registry_manager import (
    UnityModule,
    UnityModuleRegistryError,
    UnityModuleRegistryManager,
)

__all__ = [
    "UnityModule",
    "UnityModuleRegistryError",
    "UnityModuleRegistryManager",
]
