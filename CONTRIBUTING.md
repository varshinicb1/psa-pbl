# Contributing Guidelines

## Autonomous Explainable Grid Digital Twin

Thank you for contributing to this defence research project. These guidelines ensure code quality, security, and consistency.

## Code of Conduct

- Research integrity first
- No shortcuts on security or testing
- Peer review required for all changes
- Document decisions and assumptions
- Share knowledge transparently

## Development Setup

### 1. Clone & Branch

```bash
git clone https://github.com/varshinicb1/psa-pbl.git
cd psa-pbl
git checkout -b feature/your-feature-name
```

### 2. Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

### 3. Install Dev Dependencies

```bash
pip install -r platform/dt-orchestrator/requirements-dev.txt
pip install pre-commit
pre-commit install
```

## Code Standards

### Style & Formatting

- **Python**: Black (line length 100)
- **Linting**: Ruff
- **Type Checking**: MyPy

```bash
# Format code
black platform/

# Lint
ruff check platform/

# Type check
mypy platform/
```

### Python Guidelines

1. **Type Hints**: All public functions require type hints
   ```python
   def calculate_deviation(voltage: float, bounds: tuple[float, float]) -> float:
       """Calculate voltage deviation from bounds."""
       return max(0.0, voltage - bounds[1], bounds[0] - voltage)
   ```

2. **Docstrings**: Google-style for public APIs
   ```python
   def run_powerflow(self, net: pp.pandapowerNet, *, algorithm: str = "nr") -> PowerFlowRunInfo:
       """
       Run AC powerflow using pandapower.
       
       Args:
           net: pandapower network object
           algorithm: Powerflow algorithm name (default: Newton-Raphson)
           
       Returns:
           PowerFlowRunInfo with results and metrics
           
       Raises:
           GridSimulationError: If powerflow execution fails
       """
   ```

3. **Logging**: Use structured logging instead of print()
   ```python
   from dt_contracts.logging_config import get_logger
   
   logger = get_logger(__name__)
   logger.info("Event description", extra_fields={"key": value})
   logger.error("Error occurred", exc_info=True)
   ```

4. **Error Handling**: Use custom exception hierarchy
   ```python
   from dt_contracts.exceptions import TickExecutionError, StateError
   
   try:
       result = risky_operation()
   except ValueError as exc:
       raise TickExecutionError(f"Operation failed: {exc}") from exc
   ```

5. **Constants**: Extract magic numbers to module or config
   ```python
   # Bad:
   if voltage > 1.05:
       flag_anomaly()
   
   # Good:
   VOLTAGE_UPPER_BOUND = 1.05
   if voltage > VOLTAGE_UPPER_BOUND:
       flag_anomaly()
   ```

## Testing Requirements

### Test Coverage

- Minimum 70% code coverage
- Unit tests for all public functions
- Integration tests for multi-module interactions
- Edge cases and error conditions

### Writing Tests

```python
import pytest
from dt_contracts.models import GridGraphSnapshot
from dt_orchestrator.pipelines.realtime_tick import RealtimeTickRunner

@pytest.mark.unit
def test_tick_runner_initialization():
    """Test RealtimeTickRunner initializes correctly."""
    runner = RealtimeTickRunner(grid_id="test-grid")
    assert runner is not None
    assert runner.adapter is not None
    assert runner.store.get_latest() is not None

@pytest.mark.integration
def test_full_tick_cycle():
    """Test complete tick execution (slow test)."""
    runner = RealtimeTickRunner()
    output = runner.run_one_tick()
    
    assert output.snapshot is not None
    assert output.metrics.get("solved") is not None
    # explanation may be None if no anomaly
```

### Running Tests

```bash
# All tests with coverage
pytest platform/ --cov=platform --cov-report=html

# Specific test file
pytest platform/dt-orchestrator/tests/test_api.py -v

# Only unit tests (fast)
pytest platform/ -m unit -v

# With logging output
pytest platform/ -v --log-cli-level=INFO
```

## Commit Guidelines

### Message Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `refactor`: Code refactor (no behavior change)
- `test`: Add/update tests
- `docs`: Documentation
- `style`: Code formatting
- `perf`: Performance improvement
- `security`: Security fix

**Example**:
```
feat(api): add graceful WebSocket shutdown

- Implement lifespan context manager for cleanup
- Cancel background tasks on shutdown
- Close client connections with proper timeout

Fixes #42
Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
```

## Pull Request Process

1. **Before Submitting**:
   - [ ] Tests pass: `pytest platform/ --cov=platform`
   - [ ] Code formatted: `black platform/`
   - [ ] Lint passes: `ruff check platform/`
   - [ ] Types check: `mypy platform/`
   - [ ] Pre-commit passes: `pre-commit run --all-files`

2. **PR Description**: Include:
   - What changes were made
   - Why the changes were needed
   - How to test the changes
   - Any security/performance implications

3. **Approval**: 
   - Requires code review from 1+ maintainers
   - CI pipeline must pass
   - No merge conflicts

## Performance Considerations

- Simulation tick must complete in target time (default 1.0s)
- WebSocket messages kept under 1MB (typically <100KB)
- No blocking operations in async code
- Cache topology hash to avoid recomputation

## Security Guidelines

1. **Never commit secrets**: Use environment variables
2. **Validate inputs**: Use Pydantic models
3. **Error messages**: Don't expose internal paths or system details
4. **Dependencies**: Review before adding new packages
5. **Logging**: Don't log sensitive data (credentials, keys)

## Documentation

- Update README if adding features
- Document API changes in docstrings
- Add examples for non-obvious functionality
- Keep DEPLOYMENT.md in sync with changes

## Debugging

### Enable Debug Logging

```bash
export DT_LOG_LEVEL=DEBUG
python platform/dt-orchestrator/demo_run.py
```

### Use Python Debugger

```python
import pdb; pdb.set_trace()  # Breakpoint
```

### Inspect Snapshots

```python
import json
from dt_contracts.models import GridGraphSnapshot

snapshot: GridGraphSnapshot = ...
print(json.dumps(snapshot.model_dump(), indent=2, default=str))
```

## Release Process

1. Update version in `__init__.py`
2. Update CHANGELOG.md
3. Create release tag: `git tag v1.0.0`
4. Push tag: `git push origin v1.0.0`
5. Create GitHub release with notes

## Questions?

- Check existing documentation in `platform/`
- Review issue discussions for context
- Email research team with questions

---

**Thank you for contributing to advancing grid research!**
