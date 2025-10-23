# Python Type Hints Guide

## Overview

All service methods MUST have return type annotations. This improves IDE support and enables static type checking with mypy.

## Standards

### Required Type Imports

```python
from typing import Dict, List, Optional, Any, Tuple, Union
```

### Return Type Patterns

**Dictionary returns:**
```python
def identify_plant(...) -> Dict[str, Any]:
    return {'success': True, 'plant_name': 'Rose'}
```

**Optional returns:**
```python
def get_cached_result(...) -> Optional[Dict[str, Any]]:
    return cache.get(key) or None
```

**Tuple returns:**
```python
def parallel_call(...) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    return (result1, result2)
```

**Variable annotations:**
```python
# For complex dictionaries, add type annotation
results: Dict[str, Any] = {
    'success': True,
    'data': [],
    'count': 0
}

# For lists
combined: List[Dict[str, Any]] = []
```

## Running Type Checks

```bash
# Activate virtual environment
cd backend
source venv/bin/activate

# Check all service files
mypy apps/plant_identification/services/plant_id_service.py \
     apps/plant_identification/services/plantnet_service.py \
     apps/plant_identification/services/combined_identification_service.py

# Check specific file
mypy apps/plant_identification/services/plant_id_service.py
```

## Common Type Patterns

### Services with External APIs

```python
from typing import Dict, Optional, Any

class APIService:
    def call_api(self, param: str) -> Dict[str, Any]:
        """Call external API and return results."""
        response = requests.get(f"{self.BASE_URL}/{param}")
        return response.json()

    def get_cached_data(self, key: str) -> Optional[Dict[str, Any]]:
        """Return cached data or None if not found."""
        return cache.get(key)
```

### Handling None from `os.cpu_count()`

```python
# WRONG - mypy error: can't multiply None
workers = os.cpu_count() * 2

# CORRECT - handle None explicitly
cpu_count = os.cpu_count() or 1
workers = cpu_count * 2
```

### Dictionary with Mixed Types

```python
# WRONG - mypy can't infer structure
results = {
    'data': [],
    'count': 0,
    'message': None
}

# CORRECT - add type annotation
results: Dict[str, Any] = {
    'data': [],
    'count': 0,
    'message': None
}
```

## Current Status

### Core Services (Type Hints Complete)

✅ **plant_id_service.py**
- `identify_plant(...) -> Dict[str, Any]`
- `_call_plant_id_api(...) -> Dict[str, Any]`
- `_format_response(...) -> Dict[str, Any]`
- `get_plant_details(...) -> Optional[Dict[str, Any]]`
- `_get_redis_connection(self) -> Optional[Redis]`

✅ **plantnet_service.py**
- `identify_plant(...) -> Optional[Dict[str, Any]]`
- `_prepare_image(...) -> bytes`
- `get_top_suggestions(...) -> List[Dict[str, Any]]`

✅ **combined_identification_service.py**
- `get_executor() -> ThreadPoolExecutor`
- `identify_plant(...) -> Dict[str, Any]`
- `_identify_parallel(...) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]`
- `_merge_suggestions(...) -> List[Dict[str, Any]]`

## Mypy Configuration

The project uses `pyproject.toml` for mypy configuration:

```toml
[tool.mypy]
python_version = "3.13"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = false  # Start permissive
check_untyped_defs = true
no_implicit_optional = true
ignore_missing_imports = true
```

## IDE Support

### VS Code

1. Install Python extension
2. Type hints will show in tooltips when hovering over methods
3. Autocomplete will suggest dictionary keys and methods

### PyCharm

1. Type hints work out of the box
2. Cmd/Ctrl + Click on method shows full signature
3. Autocomplete shows return type structure

## CI/CD Integration (Future)

Add to GitHub Actions workflow:

```yaml
- name: Type check with mypy
  run: |
    cd backend
    pip install mypy django-stubs
    mypy apps/plant_identification/services/plant_id_service.py \
         apps/plant_identification/services/plantnet_service.py \
         apps/plant_identification/services/combined_identification_service.py
```

## Troubleshooting

### "Name 'Any' is not defined"

**Problem:**
```python
def method() -> Dict[str, Any]:  # ❌ NameError
```

**Solution:**
```python
from typing import Dict, Any

def method() -> Dict[str, Any]:  # ✅
```

### "Incompatible default for argument"

**Problem:**
```python
def method(param: str = None):  # ❌ Should be Optional[str]
```

**Solution:**
```python
from typing import Optional

def method(param: Optional[str] = None):  # ✅
```

### "Need type annotation for variable"

**Problem:**
```python
results = {'data': [], 'count': 0}  # ❌ mypy can't infer
```

**Solution:**
```python
results: Dict[str, Any] = {'data': [], 'count': 0}  # ✅
```

## References

- **PEP 484 - Type Hints:** https://peps.python.org/pep-0484/
- **mypy Documentation:** https://mypy.readthedocs.io/
- **django-stubs:** https://github.com/typeddjango/django-stubs
- **Python typing Module:** https://docs.python.org/3/library/typing.html

## Future Enhancements

### TypedDict for Structured Returns

Instead of `Dict[str, Any]`, use `TypedDict` for better type safety:

```python
from typing import TypedDict, List

class PlantSuggestion(TypedDict):
    plant_name: str
    scientific_name: str
    probability: float
    common_names: List[str]

class PlantIdentificationResult(TypedDict):
    success: bool
    plant_name: str
    scientific_name: str
    confidence: float
    suggestions: List[PlantSuggestion]

# Usage
def identify_plant(...) -> PlantIdentificationResult:
    return {
        'success': True,
        'plant_name': 'Rose',
        'scientific_name': 'Rosa',
        'confidence': 0.95,
        'suggestions': []
    }
```

This provides:
- IDE autocomplete for dictionary keys
- Type checking for values
- Clear API contracts
- Better documentation
