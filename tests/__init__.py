"""
Radio Monitor Test Suite

This package contains all automated tests for Radio Monitor 1.0.

Test Files:
- conftest.py: Pytest fixtures and configuration
- test_database.py: Database operations, CRUD, queries, caching
- test_api.py: API endpoints, filtering, sorting, error handling
- test_notifications.py: Notification providers, triggers, rate limiting
- test_plex_failures.py: Plex failure tracking, retry logic, export

Running Tests:
    # Run all tests
    pytest

    # Run specific test file
    pytest tests/test_database.py

    # Run specific test class
    pytest tests/test_database.py::TestDatabaseCRUD

    # Run specific test
    pytest tests/test_database.py::TestDatabaseCRUD::test_create_station

    # Run only unit tests
    pytest -m unit

    # Skip slow tests
    pytest -m "not slow"

    # With coverage
    pytest --cov=radio_monitor --cov-report=html
"""
