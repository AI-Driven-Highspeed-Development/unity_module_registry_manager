import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

project_root = os.getcwd()
sys.path.insert(0, project_root)

from cores.exceptions_core import ADHDError
from utils.logger_util import Logger


@dataclass
class UnityModule:
    """Represents a discovered Unity module."""
    name: str
    type: str
    path: str
    has_yaml: bool = False
    version: Optional[str] = None
    description: Optional[str] = None
    dependencies: list[str] = field(default_factory=list)
    assembly: Optional[str] = None


class UnityModuleRegistryError(ADHDError):
    """Raised when Unity module registry operations fail."""
    pass


class UnityModuleRegistryManager:
    """
    Scans Unity project folders and maintains a registry of discovered modules.
    
    Module types are detected based on folder structure:
    - Assets/_Core/* -> core
    - Assets/_Managers/* -> manager
    - Assets/_Shared/* -> shared
    - Assets/Features/* -> feature
    - Assets/Levels/* -> level
    - Assets/ThirdParty/* -> thirdparty
    - Assets/_Extensions/* -> extension
    """
    
    # Module type detection mapping
    MODULE_TYPE_FOLDERS: dict[str, str] = {
        "_Core": "core",
        "_Managers": "manager",
        "_Shared": "shared",
        "Features": "feature",
        "Levels": "level",
        "ThirdParty": "thirdparty",
        "_Extensions": "extension",
    }
    
    def __init__(
        self,
        unity_project_path: str | Path | None = None,
        registry_path: str | Path | None = None,
        verbose: bool = False
    ):
        self.logger = Logger(name="UnityModuleRegistryManager", verbose=verbose)
        
        # Resolve Unity project path
        if unity_project_path:
            self.unity_project_path = Path(unity_project_path).resolve()
        else:
            # Try to get from config
            self.unity_project_path = self._get_unity_path_from_config()
        
        if not self.unity_project_path:
            self.logger.warning("Unity project path not configured")
            self.unity_project_path = None
        elif not self.unity_project_path.exists():
            self.logger.warning(f"Unity project path does not exist: {self.unity_project_path}")
        
        # Registry storage path
        if registry_path:
            self.registry_path = Path(registry_path)
        else:
            self.registry_path = Path(__file__).parent / "data" / "unity_module_registry.yaml"
        
        # Ensure data directory exists
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        
        # In-memory registry
        self.modules: list[UnityModule] = []
        self.last_scan: Optional[datetime] = None
        self.registry_version = "1.0.0"
        
        # Load existing registry if present
        self._load_registry()
    
    def _get_unity_path_from_config(self) -> Optional[Path]:
        """Attempt to read Unity project path from .config file."""
        try:
            from managers.config_manager import cm
            unity_config = cm.raw_config.get("unity_module_registry", {})
            path_str = unity_config.get("unity_project_path")
            if path_str:
                return Path(path_str).resolve()
        except Exception as e:
            self.logger.debug(f"Could not read unity_project_path from config: {e}")
        return None
    
    def _load_registry(self) -> None:
        """Load existing registry from YAML file."""
        if not self.registry_path.exists():
            self.logger.debug("No existing registry found")
            return
        
        try:
            with open(self.registry_path, "r") as f:
                data = yaml.safe_load(f) or {}
            
            self.registry_version = data.get("version", "1.0.0")
            
            if data.get("last_scan"):
                self.last_scan = datetime.fromisoformat(data["last_scan"])
            
            self.modules = []
            for mod_data in data.get("modules", []):
                module = UnityModule(
                    name=mod_data.get("name", ""),
                    type=mod_data.get("type", ""),
                    path=mod_data.get("path", ""),
                    has_yaml=mod_data.get("has_yaml", False),
                    version=mod_data.get("version"),
                    description=mod_data.get("description"),
                    dependencies=mod_data.get("dependencies", []),
                    assembly=mod_data.get("assembly"),
                )
                self.modules.append(module)
            
            self.logger.debug(f"Loaded {len(self.modules)} modules from registry")
        except Exception as e:
            self.logger.error(f"Failed to load registry: {e}")
    
    def scan_modules(self) -> list[UnityModule]:
        """
        Scan the Unity project for modules.
        
        Returns:
            List of discovered UnityModule objects.
        """
        if not self.unity_project_path or not self.unity_project_path.exists():
            raise UnityModuleRegistryError(
                f"Unity project path not set or does not exist: {self.unity_project_path}"
            )
        
        assets_path = self.unity_project_path / "Assets"
        if not assets_path.exists():
            raise UnityModuleRegistryError(
                f"Assets folder not found in Unity project: {assets_path}"
            )
        
        self.logger.debug(f"Scanning Unity project: {self.unity_project_path}")
        
        discovered: list[UnityModule] = []
        
        for folder_name, module_type in self.MODULE_TYPE_FOLDERS.items():
            type_folder = assets_path / folder_name
            if not type_folder.exists():
                self.logger.debug(f"Folder not found (skipping): {type_folder}")
                continue
            
            # Scan immediate subfolders as modules
            for module_folder in type_folder.iterdir():
                if not module_folder.is_dir():
                    continue
                
                # Skip hidden folders and Unity special folders
                if module_folder.name.startswith(".") or module_folder.name.startswith("~"):
                    continue
                
                module = self._scan_single_module(module_folder, module_type)
                discovered.append(module)
                self.logger.debug(f"Discovered module: {module.name} ({module.type})")
        
        self.modules = discovered
        self.last_scan = datetime.now()
        
        self.logger.info(f"Scan complete: {len(self.modules)} modules found")
        return self.modules
    
    def _scan_single_module(self, folder: Path, module_type: str) -> UnityModule:
        """Scan a single module folder and extract metadata."""
        module_yaml_path = folder / "module.yaml"
        has_yaml = module_yaml_path.exists()
        
        module = UnityModule(
            name=folder.name,
            type=module_type,
            path=str(folder.relative_to(self.unity_project_path)),
            has_yaml=has_yaml,
        )
        
        # Parse module.yaml if present
        if has_yaml:
            try:
                with open(module_yaml_path, "r") as f:
                    yaml_data = yaml.safe_load(f) or {}
                
                # Override with YAML values if present
                if yaml_data.get("name"):
                    module.name = yaml_data["name"]
                module.version = yaml_data.get("version")
                module.description = yaml_data.get("description")
                module.dependencies = yaml_data.get("dependencies", [])
                module.assembly = yaml_data.get("assembly")
            except Exception as e:
                self.logger.warning(f"Failed to parse module.yaml for {folder.name}: {e}")
        
        return module
    
    def save_registry(self) -> None:
        """Save the current registry to YAML file."""
        data = {
            "version": self.registry_version,
            "project_path": str(self.unity_project_path) if self.unity_project_path else None,
            "last_scan": self.last_scan.isoformat() if self.last_scan else None,
            "modules": [
                {
                    "name": m.name,
                    "type": m.type,
                    "path": m.path,
                    "has_yaml": m.has_yaml,
                    "version": m.version,
                    "description": m.description,
                    "dependencies": m.dependencies,
                    "assembly": m.assembly,
                }
                for m in self.modules
            ],
        }
        
        try:
            with open(self.registry_path, "w") as f:
                yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)
            self.logger.debug(f"Registry saved to {self.registry_path}")
        except Exception as e:
            raise UnityModuleRegistryError(f"Failed to save registry: {e}")
    
    def get_modules(self, module_type: Optional[str] = None) -> list[UnityModule]:
        """
        Get modules, optionally filtered by type.
        
        Args:
            module_type: Optional type filter (core, manager, feature, etc.)
        
        Returns:
            List of matching modules.
        """
        if module_type:
            return [m for m in self.modules if m.type == module_type]
        return self.modules
    
    def get_module(self, name: str) -> Optional[UnityModule]:
        """
        Get a single module by name.
        
        Args:
            name: Module name to find.
        
        Returns:
            UnityModule if found, None otherwise.
        """
        for module in self.modules:
            if module.name == name:
                return module
        return None
    
    def get_module_dependencies(self, name: str) -> list[str]:
        """
        Get dependencies for a module.
        
        Args:
            name: Module name.
        
        Returns:
            List of dependency paths.
        """
        module = self.get_module(name)
        if module:
            return module.dependencies
        return []
    
    def find_dependents(self, name: str) -> list[UnityModule]:
        """
        Find modules that depend on a given module.
        
        Args:
            name: Module name or path to search for.
        
        Returns:
            List of modules that depend on this module.
        """
        dependents = []
        for module in self.modules:
            for dep in module.dependencies:
                # Check if dependency matches by name or path
                if name in dep or dep.endswith(f"/{name}"):
                    dependents.append(module)
                    break
        return dependents
    
    def get_scan_summary(self) -> dict:
        """
        Get a summary of the current registry state.
        
        Returns:
            Dict with module counts by type and metadata.
        """
        counts: dict[str, int] = {}
        for module in self.modules:
            counts[module.type] = counts.get(module.type, 0) + 1
        
        modules_with_yaml = sum(1 for m in self.modules if m.has_yaml)
        
        return {
            "total_modules": len(self.modules),
            "modules_by_type": counts,
            "modules_with_yaml": modules_with_yaml,
            "modules_without_yaml": len(self.modules) - modules_with_yaml,
            "last_scan": self.last_scan.isoformat() if self.last_scan else None,
            "project_path": str(self.unity_project_path) if self.unity_project_path else None,
        }
