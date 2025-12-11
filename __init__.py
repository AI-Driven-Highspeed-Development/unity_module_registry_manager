"""
Unity Module Registry Manager

Scans Unity project folders and maintains a registry of discovered modules.
Supports automatic detection of module types based on folder structure.

Usage:
    from managers.unity_module_registry_manager import UnityModuleRegistryManager
    
    registry = UnityModuleRegistryManager(unity_project_path="../MyUnityProject")
    modules = registry.scan_modules()
    registry.save_registry()
"""

import os
import sys

project_root = os.getcwd()
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from .unity_module_registry_manager import UnityModuleRegistryManager
except ImportError:
    from unity_module_registry_manager import UnityModuleRegistryManager
