#!/usr/bin/env python3
"""
Backend Feature Validation Test Suite
Tests all newly implemented backend features
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=== BACKEND FEATURE VALIDATION TEST SUITE ===\n")
print("Testing all newly implemented features...\n")

passed = 0
failed = 0

def test(description, fn):
    global passed, failed
    try:
        fn()
        print(f"[PASS] {description}")
        passed += 1
    except Exception as e:
        print(f"[FAIL] {description}")
        print(f"       Error: {str(e)}")
        failed += 1

# Test 1: Import Application model
def test_application_model():
    from app.models.application import Application
    from sqlalchemy import Column

    # Check required columns exist
    assert hasattr(Application, 'id'), "Missing id column"
    assert hasattr(Application, 'session_user_id'), "Missing session_user_id column"
    assert hasattr(Application, 'job_title'), "Missing job_title column"
    assert hasattr(Application, 'company_name'), "Missing company_name column"
    assert hasattr(Application, 'status'), "Missing status column"
    assert hasattr(Application, 'is_deleted'), "Missing is_deleted column"
    assert hasattr(Application, 'to_dict'), "Missing to_dict method"
    assert Application.__tablename__ == 'applications', "Wrong table name"

test("Application model imports and has required fields", test_application_model)

# Test 2: Import applications router
def test_applications_router():
    from app.routes.applications import router, VALID_STATUSES
    from fastapi import APIRouter

    assert isinstance(router, APIRouter), "Router is not an APIRouter instance"
    assert len(VALID_STATUSES) == 9, f"Wrong number of statuses: {len(VALID_STATUSES)}"

    expected_statuses = {'saved', 'applied', 'screening', 'interviewing', 'offer',
                         'accepted', 'rejected', 'withdrawn', 'no_response'}
    assert VALID_STATUSES == expected_statuses, "Wrong status values"

test("Applications router imports and has correct statuses", test_applications_router)

# Test 3: Check main.py includes applications router
def test_main_includes_applications():
    import app.main as main

    # Check that applications is imported
    source = open('app/main.py').read()
    assert 'from app.routes import' in source, "Missing route imports"
    assert 'applications' in source, "Missing applications import"
    assert 'app.include_router(applications.router' in source, "Applications router not registered"

test("main.py includes and registers applications router", test_main_includes_applications)

# Test 4: Check database.py includes application model
def test_database_includes_application():
    source = open('app/database.py').read()
    assert 'application' in source, "Missing application model import in database.py"

test("database.py imports application model", test_database_includes_application)

# Test 5: Check models/__init__.py exports Application
def test_models_exports_application():
    from app.models import Application
    assert Application is not None, "Application not exported from models package"

test("models/__init__.py exports Application", test_models_exports_application)

# Test 6: Check CoverLetter model exists
def test_cover_letter_model():
    try:
        from app.models.cover_letter import CoverLetter
        assert hasattr(CoverLetter, '__tablename__'), "CoverLetter missing __tablename__"
        print("   INFO:  CoverLetter model found (from remote merge)")
    except ImportError:
        raise Exception("CoverLetter model not found")

test("CoverLetter model exists and is importable", test_cover_letter_model)

# Test 7: Check cover_letters router exists
def test_cover_letters_router():
    try:
        from app.routes.cover_letters import router
        from fastapi import APIRouter
        assert isinstance(router, APIRouter), "Cover letters router is not an APIRouter"
        print("   INFO:  Cover letters router found (from remote merge)")
    except ImportError:
        raise Exception("Cover letters router not found")

test("cover_letters router exists and is importable", test_cover_letters_router)

# Test 8: Check auth middleware has get_user_id
def test_auth_middleware():
    try:
        from app.middleware.auth import get_user_id
        assert callable(get_user_id), "get_user_id is not callable"
        print("   INFO:  Auth middleware with get_user_id found (for JWT authentication)")
    except ImportError:
        raise Exception("Auth middleware or get_user_id not found")

test("Auth middleware has get_user_id dependency", test_auth_middleware)

# Test 9: Validate Application.to_dict() returns correct structure
def test_application_to_dict():
    from app.models.application import Application
    from datetime import datetime

    # Create mock application
    app = Application(
        id=1,
        session_user_id="user_123",
        job_title="Senior Engineer",
        company_name="Tech Corp",
        status="applied",
        created_at=datetime.now(),
        updated_at=datetime.now()
    )

    result = app.to_dict()

    assert 'id' in result, "Missing id in to_dict"
    assert 'jobTitle' in result, "Missing jobTitle in to_dict (should be camelCase)"
    assert 'companyName' in result, "Missing companyName in to_dict"
    assert 'status' in result, "Missing status in to_dict"
    assert result['jobTitle'] == 'Senior Engineer', "Wrong jobTitle value"

test("Application.to_dict() returns correct camelCase structure", test_application_to_dict)

# Test 10: Check Python syntax on all route files
def test_python_syntax():
    import py_compile

    files = [
        'app/routes/applications.py',
        'app/routes/cover_letters.py',
        'app/models/application.py',
        'app/models/cover_letter.py',
        'app/main.py',
        'app/database.py'
    ]

    for file in files:
        if os.path.exists(file):
            py_compile.compile(file, doraise=True)

test("All Python files have valid syntax", test_python_syntax)

print('\n' + '='*60)
print(f"\nPassed: {passed}")
print(f"Failed: {failed}")
print(f"\nTotal: {passed + failed} tests")

if failed > 0:
    print("\nSome tests failed. Please review the errors above.")
    sys.exit(1)
else:
    print("\nAll backend tests passed! Features are properly implemented.")
    sys.exit(0)
