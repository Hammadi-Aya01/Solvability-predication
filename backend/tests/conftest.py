"""
tests/conftest.py
Pytest configuration and shared fixtures.
"""
import pytest
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


@pytest.fixture(scope="session")
def app():
    """Create a Flask test application."""
    from app import create_app
    application = create_app("testing")
    return application


@pytest.fixture(scope="session")
def db(app):
    """Create all tables for the test session."""
    from extensions import db as _db
    with app.app_context():
        _db.create_all()
        yield _db
        _db.drop_all()


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture
def auth_headers(client, db, app):
    """Register + login a test user, return JWT Authorization header."""
    import uuid
    uid = uuid.uuid4().hex[:8]
    with app.app_context():
        rv = client.post("/api/auth/register", json={
            "company_name": f"TestCo_{uid}",
            "email":        f"test_{uid}@testco.com",
            "password":     "Test1234!",
        })
        data = rv.get_json()
        token = data.get("access_token")
        return {"Authorization": f"Bearer {token}"}

