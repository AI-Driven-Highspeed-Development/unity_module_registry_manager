"""Refresh script for Unity Module Registry Manager.

Re-scans Unity project and updates the registry.
Rerun-safe: only rescans if unity project path is configured.
"""
from __future__ import annotations
import sys
from pathlib import Path

# Ensure project root is in sys.path (standard pattern for refresh scripts)
if str(Path.cwd()) not in sys.path:
    sys.path.append(str(Path.cwd()))


def main() -> None:
    """Run the refresh process."""
    from managers.config_manager import cm
    from managers.unity_module_registry_manager import UnityModuleRegistryManager

    try:
        unity_project_path = cm.config.unity_module_registry_manager.path.unity_project
    except AttributeError:
        unity_project_path = None

    if not unity_project_path:
        print("Unity project path not configured, skipping refresh.")
        return

    registry = UnityModuleRegistryManager(unity_project_path=unity_project_path)
    registry.scan_modules()
    registry.save_registry()
    print(f"Registry refreshed: {len(registry.modules)} modules found.")


if __name__ == "__main__":
    main()
