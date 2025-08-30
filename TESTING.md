# Testing Documentation

## Overview

Comprehensive testing suite for the Matchcaller TUI application covering API integration, data models, UI components, and visual regression detection.

## Test Structure

```
tests/
├── test_api.py           # TournamentAPI class tests
├── test_data_models.py   # MatchRow and data parsing tests  
├── test_demo_mode.py     # CLI argument and demo mode tests
├── test_snapshots.py     # Visual regression tests
├── test_ui.py           # Textual TUI component tests
├── test_app_empty.py    # Helper app for empty state testing
└── __init__.py
```

## Test Categories

### Unit Tests (14 tests)
**File:** `tests/test_api.py`  
**Marker:** `@pytest.mark.unit`

- TournamentAPI initialization with tokens, event IDs, and slugs
- GraphQL query construction and execution
- HTTP error handling and fallback to mock data
- API response parsing for various data structures
- Event ID resolution from start.gg slugs
- Edge cases with missing or malformed data

### Integration Tests (29 tests)  
**Files:** `tests/test_data_models.py`, `tests/test_demo_mode.py`  
**Marker:** `@pytest.mark.integration`

**Data Models:**
- MatchRow object creation from API responses
- Status icon logic for match states (Ready, In Progress, Waiting)
- Time calculations for match readiness
- Station and stream information handling
- Mock data structure validation

**Demo Mode:**
- CLI argument parsing for all combinations
- Automatic demo mode fallback when credentials missing
- Real mode activation with proper tokens
- Exception handling during startup
- Logging verification for different modes

### UI Tests (14 tests)
**File:** `tests/test_ui.py`  
**Marker:** `@pytest.mark.ui`

- Textual app initialization with parameters
- Widget creation (DataTable, Labels, Headers)
- Mock data loading and display updates
- Table population and sorting verification
- Key binding functionality (R for refresh, Q for quit)
- Info bar statistics display
- Periodic update mechanisms
- API error handling in UI context

### Snapshot Tests (7 tests)
**File:** `tests/test_snapshots.py`  
**Marker:** `@pytest.mark.ui`

- Visual regression detection via SVG screenshots
- Multiple terminal size compatibility (80x24, 120x30, 160x40, 50x15)
- Raspberry Pi console display validation
- Empty tournament state rendering
- Demo mode visual consistency

## Running Tests

### Basic Usage
```bash
# All tests
make test
python run_tests.py

# Specific categories  
make test-unit
make test-integration
make test-ui

# With coverage
make test-coverage
python run_tests.py --coverage

# Fast tests only
make test-fast
python run_tests.py --fast
```

### Snapshot Testing
```bash
# Update visual baselines
make test-snapshots
python run_tests.py --snapshots

# View snapshot differences
pytest tests/test_snapshots.py --snapshot-update
```

### Advanced Options
```bash
# Specific test patterns
python run_tests.py --pattern api

# Specific test files
python run_tests.py --file test_ui.py

# Install dependencies first
python run_tests.py --install-deps
```

## Test Configuration

### Dependencies
- `pytest>=7.0.0` - Test framework
- `pytest-asyncio>=0.21.0` - Async test support
- `pytest-textual-snapshot>=0.4.0` - Visual regression testing
- `pytest-cov>=4.0.0` - Coverage reporting
- `pytest-mock>=3.10.0` - Mocking utilities  
- `aioresponses>=0.7.4` - HTTP response mocking

### Configuration Files
- `pytest.ini` - Pytest configuration with markers and async mode
- `requirements.txt` - Test dependencies
- `run_tests.py` - Custom test runner script
- `Makefile` - Convenient test commands

## Test Data

### Mock Data
**Location:** `matchcaller/matchcaller.py:MOCK_TOURNAMENT_DATA`

Provides consistent test data with:
- 4 tournament sets with different states
- Variety of match states (Waiting, Ready, In Progress)
- Realistic timestamps and player names
- Station and stream assignments

### Test Helpers
**File:** `tests/test_app_empty.py`

Custom TournamentDisplay subclass for testing empty tournament states.

## Async Testing Patterns

All async tests use `@pytest.mark.asyncio` decorator:

```python
@pytest.mark.asyncio
async def test_api_call(self):
    api = TournamentAPI(token="test")
    result = await api.fetch_sets()
    assert result is not None
```

### Textual UI Testing
```python
async def test_ui_behavior(self):
    app = TournamentDisplay()
    
    async with app.run_test() as pilot:
        await pilot.pause(1.0)  # Wait for initialization
        
        # Test interactions
        await pilot.press("r")  # Trigger refresh
        
        # Assert UI state
        table = app.query_one(DataTable)
        assert len(table.rows) > 0
```

## Coverage

Coverage reports are generated in multiple formats:
- **Terminal output** - Summary during test run
- **HTML report** - Detailed coverage in `htmlcov/index.html`
- **XML report** - Machine-readable coverage data

Current target coverage areas:
- API integration logic
- Data parsing and transformation
- UI component behavior
- Error handling paths

## Continuous Integration

Tests are designed to run in CI environments:
- No external dependencies required
- Deterministic mock data
- Configurable timeout values
- Comprehensive error reporting

## Debugging Tests

### Common Issues

**Async/await errors:**
- Ensure `@pytest.mark.asyncio` on async test methods
- Don't await Textual `@work` decorated methods

**UI test timing:**
- Use appropriate `await pilot.pause()` durations
- Wait for data loading before assertions

**Snapshot failures:**
- Run with `--snapshot-update` to regenerate baselines
- Check terminal size consistency

### Logging
Test execution details logged to `/tmp/tournament_debug.log` during UI tests.

### Verbose Output
```bash
python -m pytest tests/ -v -s  # Verbose with stdout
python -m pytest tests/ --tb=long  # Detailed tracebacks
```

## Adding New Tests

### Test Naming
- Files: `test_*.py`
- Functions: `test_*`
- Classes: `Test*`

### Markers
Use appropriate pytest markers:
```python
@pytest.mark.unit      # Unit tests
@pytest.mark.integration  # Integration tests  
@pytest.mark.ui        # UI tests
@pytest.mark.slow      # Tests taking >1 second
```

### Async Tests
```python
@pytest.mark.asyncio
async def test_async_functionality(self):
    # Test implementation
    pass
```