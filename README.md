# Unity Module Registry Manager

Scans Unity project folders and maintains a YAML registry of discovered modules based on folder structure.

## Overview
- Discovers Unity modules by scanning predefined folder patterns in Assets/
- Detects module type from parent folder (_Core, _Managers, Features, etc.)
- Parses optional `module.yaml` for rich metadata (version, dependencies, assembly)
- Stores registry in YAML format for MCP/agent consumption

## Features
- Automatic module type detection
  - `Assets/_Core/*` → core
  - `Assets/_Managers/*` → manager
  - `Assets/_Shared/*` → shared
  - `Assets/Features/*` → feature
  - `Assets/Levels/*` → level
  - `Assets/ThirdParty/*` → thirdparty
  - `Assets/_Extensions/*` → extension
- Optional `module.yaml` parsing for rich metadata
- Dependency tracking and reverse dependency lookup
- Scan summary with module counts by type

## Quickstart

```python
from managers.unity_module_registry_manager import UnityModuleRegistryManager

# Initialize with Unity project path
registry = UnityModuleRegistryManager(unity_project_path="../MyUnityProject")

# Scan for modules
modules = registry.scan_modules()

# Save registry to YAML
registry.save_registry()

# Query modules
all_features = registry.get_modules(module_type="feature")
player = registry.get_module("PlayerFeature")
deps = registry.get_module_dependencies("PlayerFeature")
dependents = registry.find_dependents("EventSystem")

# Get summary
summary = registry.get_scan_summary()
```

## API

```python
@dataclass
class UnityModule:
    name: str
    type: str
    path: str
    has_yaml: bool = False
    version: Optional[str] = None
    description: Optional[str] = None
    dependencies: list[str] = field(default_factory=list)
    assembly: Optional[str] = None

class UnityModuleRegistryManager:
    def __init__(
        self,
        unity_project_path: str | Path | None = None,
        registry_path: str | Path | None = None,
        verbose: bool = False
    ): ...
    
    def scan_modules(self) -> list[UnityModule]: ...
    def save_registry(self) -> None: ...
    def get_modules(self, module_type: Optional[str] = None) -> list[UnityModule]: ...
    def get_module(self, name: str) -> Optional[UnityModule]: ...
    def get_module_dependencies(self, name: str) -> list[str]: ...
    def find_dependents(self, name: str) -> list[UnityModule]: ...
    def get_scan_summary(self) -> dict: ...
```

## Notes
- Registry is stored at `data/unity_module_registry.yaml` by default
- If `unity_project_path` is not provided, attempts to read from `.config` under `unity_module_registry_manager.path.unity_project`
- Module names default to folder names but can be overridden in `module.yaml`

## Requirements & prerequisites
- PyYAML (for YAML parsing)

## Troubleshooting
- "Unity project path not set": Provide path in constructor or set in `.config`
- "Assets folder not found": Ensure path points to Unity project root containing `Assets/`
- "Failed to parse module.yaml": Check YAML syntax in the module's `module.yaml`
- Empty registry after scan: Verify Unity project has modules in expected folders

## Module structure

```
managers/unity_module_registry_manager/
├─ __init__.py                        # package exports
├─ unity_module_registry_manager.py   # main implementation
├─ init.yaml                          # module metadata
├─ refresh.py                         # CLI hook for refresh
├─ data/                              # registry storage
│  └─ unity_module_registry.yaml      # generated registry
└─ README.md                          # this file
```

## See also
- Config Manager: provides `.config` path for Unity project
- Logger Utility: standardized logging
- Exceptions Core: ADHDError base class
