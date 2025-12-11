import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml
from yaml import YAMLError

from cores.exceptions_core.adhd_exceptions import ADHDError
from utils.logger_util.logger import Logger


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
        elif not self.unity_project_path.exists():
            self.logger.warning(f"Unity project path does not exist: {self.unity_project_path}")
        
        # Registry storage path
        if registry_path:
            self.registry_path = Path(registry_path)
        else:
            self.registry_path = self._get_registry_path_from_config()
        
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
            path_str = cm.config.unity_module_registry_manager.path.unity_project
            if path_str:
                return Path(path_str).resolve()
        except (AttributeError, ImportError) as e:
            self.logger.debug(f"Could not read unity_project from config: {e}")
        return None
    
    def _get_registry_path_from_config(self) -> Path:
        """Get registry file path from .config file."""
        try:
            from managers.config_manager import cm
            data_dir = cm.config.unity_module_registry_manager.path.data
            return Path(data_dir) / "unity_module_registry.yaml"
        except (AttributeError, ImportError) as e:
            self.logger.warning(f"Could not read data path from config, using fallback: {e}")
            # Fallback to project/data pattern (ADHD framework convention)
            return Path("project/data/unity_module_registry_manager/unity_module_registry.yaml")
    
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
            
            self.modules = [
                UnityModule(
                    name=mod_data.get("name", ""),
                    type=mod_data.get("type", ""),
                    path=mod_data.get("path", ""),
                    has_yaml=mod_data.get("has_yaml", False),
                    version=mod_data.get("version"),
                    description=mod_data.get("description"),
                    dependencies=mod_data.get("dependencies", []),
                    assembly=mod_data.get("assembly"),
                )
                for mod_data in data.get("modules", [])
            ]
            
            self.logger.debug(f"Loaded {len(self.modules)} modules from registry")
        except (OSError, YAMLError, ValueError, KeyError) as e:
            self.logger.warning(f"Failed to load registry, starting fresh: {e}")
            self.modules = []
    
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
            except (OSError, YAMLError) as e:
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
        except OSError as e:
            raise UnityModuleRegistryError(f"Failed to save registry: {e}") from e
    
    def get_modules(self, module_type: Optional[str] = None) -> list[UnityModule]:
        """
        Get modules, optionally filtered by type.
        
        Args:
            module_type: Optional type filter (core, manager, feature, etc.)
        
        Returns:
            List of matching modules.
        
        Raises:
            ValueError: If module_type is not a valid type.
        """
        if module_type:
            valid_types = set(self.MODULE_TYPE_FOLDERS.values())
            if module_type not in valid_types:
                raise ValueError(
                    f"Invalid module type '{module_type}'. Valid types: {sorted(valid_types)}"
                )
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
        counts = dict(Counter(module.type for module in self.modules))
        modules_with_yaml = sum(1 for m in self.modules if m.has_yaml)
        
        return {
            "total_modules": len(self.modules),
            "modules_by_type": counts,
            "modules_with_yaml": modules_with_yaml,
            "modules_without_yaml": len(self.modules) - modules_with_yaml,
            "last_scan": self.last_scan.isoformat() if self.last_scan else None,
            "project_path": str(self.unity_project_path) if self.unity_project_path else None,
        }
    
    def _sanitize_mermaid_id(self, name: str) -> str:
        """Sanitize module name for valid Mermaid node IDs."""
        # Replace spaces and special chars with underscores
        sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', name)
        # Ensure doesn't start with number
        if sanitized and sanitized[0].isdigit():
            sanitized = f"m_{sanitized}"
        return sanitized or "unknown"
    
    def _get_orphaned_modules(self) -> list[UnityModule]:
        """
        Find modules that have no dependents and no dependencies.
        
        Returns:
            List of orphaned modules.
        """
        orphans = []
        for module in self.modules:
            # Has no dependencies
            has_no_deps = not module.dependencies
            # No other module depends on it
            dependents = self.find_dependents(module.name)
            has_no_dependents = len(dependents) == 0
            
            if has_no_deps and has_no_dependents:
                orphans.append(module)
        return orphans
    
    def generate_report(self) -> dict:
        """
        Generate a markdown report from the registry data.
        
        Creates a comprehensive markdown document with:
        1. Module count by type
        2. Dependency graph (Mermaid)
        3. Modules missing module.yaml
        4. Orphaned modules (no dependents/dependencies)
        
        Returns:
            Dict with success status and report_path.
        """
        # Get report output path from config (same directory as registry)
        report_path = self.registry_path.parent / "registry_report.md"
        
        # Build report content
        lines: list[str] = []
        
        # Header
        lines.append("# Unity Module Registry Report")
        lines.append("")
        lines.append(f"> Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        if self.last_scan:
            lines.append(f"> Last Scan: {self.last_scan.strftime('%Y-%m-%d %H:%M:%S')}")
        if self.unity_project_path:
            lines.append(f"> Project: `{self.unity_project_path}`")
        lines.append("")
        lines.append("---")
        lines.append("")
        
        # Section 1: Module Counts by Type
        lines.append("## Module Counts by Type")
        lines.append("")
        counts = Counter(module.type for module in self.modules)
        lines.append(f"**Total Modules:** {len(self.modules)}")
        lines.append("")
        lines.append("| Type | Count |")
        lines.append("|:-----|------:|")
        for module_type in sorted(self.MODULE_TYPE_FOLDERS.values()):
            count = counts.get(module_type, 0)
            lines.append(f"| {module_type} | {count} |")
        lines.append("")
        
        # Section 2: Dependency Graph (Mermaid)
        lines.append("## Dependency Graph")
        lines.append("")
        
        # Collect all dependency edges
        edges: list[tuple[str, str]] = []
        for module in self.modules:
            if module.dependencies:
                src_id = self._sanitize_mermaid_id(module.name)
                for dep in module.dependencies:
                    # Extract name from path if needed
                    dep_name = dep.split("/")[-1] if "/" in dep else dep
                    dst_id = self._sanitize_mermaid_id(dep_name)
                    edges.append((src_id, dst_id))
        
        if edges:
            lines.append("```mermaid")
            lines.append("graph LR")
            for src, dst in edges:
                lines.append(f"  {src} --> {dst}")
            lines.append("```")
        else:
            lines.append("*No dependencies defined between modules.*")
        lines.append("")
        
        # Section 3: Modules Missing module.yaml
        lines.append("## Modules Missing module.yaml")
        lines.append("")
        missing_yaml = [m for m in self.modules if not m.has_yaml]
        if missing_yaml:
            lines.append(f"**{len(missing_yaml)} modules** are missing `module.yaml` files:")
            lines.append("")
            for m in sorted(missing_yaml, key=lambda x: x.name):
                lines.append(f"- `{m.path}` ({m.type})")
        else:
            lines.append("✅ All modules have `module.yaml` files.")
        lines.append("")
        
        # Section 4: Orphaned Modules
        lines.append("## Orphaned Modules")
        lines.append("")
        lines.append("*Modules with no dependencies and no dependents.*")
        lines.append("")
        orphans = self._get_orphaned_modules()
        if orphans:
            lines.append(f"**{len(orphans)} orphaned modules:**")
            lines.append("")
            for m in sorted(orphans, key=lambda x: x.name):
                lines.append(f"- `{m.name}` ({m.type}) — `{m.path}`")
        else:
            lines.append("✅ No orphaned modules found.")
        lines.append("")
        
        # Write report
        try:
            report_path.parent.mkdir(parents=True, exist_ok=True)
            with open(report_path, "w") as f:
                f.write("\n".join(lines))
            
            self.logger.info(f"Report generated: {report_path}")
            return {
                "success": True,
                "report_path": str(report_path),
                "total_modules": len(self.modules),
                "missing_yaml_count": len(missing_yaml),
                "orphan_count": len(orphans),
                "dependency_edges": len(edges),
            }
        except OSError as e:
            raise UnityModuleRegistryError(f"Failed to write report: {e}") from e
