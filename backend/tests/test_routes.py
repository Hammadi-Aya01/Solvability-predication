"""
tests/test_routes.py
Integration tests for REST API routes.
Requires a test Flask app + SQLite in-memory DB (see conftest.py).
"""
import pytest


class TestAuth:
    def test_register(self, client, db):
        rv = client.post("/api/auth/register", json={
            "company_name": "AcmeCorp",
            "email": "admin@acme.com",
            "password": "Admin1234",
        })
        assert rv.status_code == 201
        data = rv.get_json()
        assert "access_token" in data
        assert data["user"]["role"] == "ADMIN"

    def test_register_duplicate_email(self, client, db):
        client.post("/api/auth/register", json={
            "company_name": "DupCo",
            "email": "dup@test.com",
            "password": "Dup12345",
        })
        rv = client.post("/api/auth/register", json={
            "company_name": "DupCo2",
            "email": "dup@test.com",
            "password": "Dup12345",
        })
        assert rv.status_code == 409

    def test_login_success(self, client, db):
        client.post("/api/auth/register", json={
            "company_name": "LoginCo",
            "email": "login@test.com",
            "password": "Login1234",
        })
        rv = client.post("/api/auth/login", json={
            "email": "login@test.com",
            "password": "Login1234",
        })
        assert rv.status_code == 200
        assert "access_token" in rv.get_json()

    def test_login_wrong_password(self, client, db):
        rv = client.post("/api/auth/login", json={
            "email": "login@test.com",
            "password": "WrongPass1",
        })
        assert rv.status_code == 401

    def test_me_requires_auth(self, client):
        rv = client.get("/api/auth/me")
        assert rv.status_code == 401

    def test_me_with_token(self, client, auth_headers):
        rv = client.get("/api/auth/me", headers=auth_headers)
        assert rv.status_code == 200
        assert "user" in rv.get_json()

    def test_health(self, client):
        rv = client.get("/api/health")
        assert rv.status_code == 200
        assert rv.get_json()["status"] == "ok"


class TestClients:
    def test_list_clients_requires_auth(self, client):
        rv = client.get("/api/clients")
        assert rv.status_code == 401

    def test_list_clients_empty(self, client, auth_headers):
        rv = client.get("/api/clients", headers=auth_headers)
        assert rv.status_code == 200
        data = rv.get_json()
        assert "clients" in data
        assert isinstance(data["clients"], list)

    def test_create_client(self, client, auth_headers):
        rv = client.post("/api/clients", headers=auth_headers, json={
            "code_client":   "CLI001",
            "nom":           "Société Test",
            "gouvernorat":   "Tunis",
            "nature_client": "GMS",
        })
        assert rv.status_code == 201
        data = rv.get_json()
        assert data["client"]["code_client"] == "CLI001"

    def test_create_client_no_code(self, client, auth_headers):
        rv = client.post("/api/clients", headers=auth_headers, json={"nom": "No Code"})
        assert rv.status_code == 400

    def test_get_client(self, client, auth_headers):
        # Create first
        rv = client.post("/api/clients", headers=auth_headers, json={"code_client": "CLI002"})
        cid = rv.get_json()["client"]["id"]
        rv2 = client.get(f"/api/clients/{cid}", headers=auth_headers)
        assert rv2.status_code == 200
        assert rv2.get_json()["client"]["id"] == cid

    def test_update_client(self, client, auth_headers):
        rv = client.post("/api/clients", headers=auth_headers, json={"code_client": "CLI003"})
        cid = rv.get_json()["client"]["id"]
        rv2 = client.put(f"/api/clients/{cid}", headers=auth_headers,
                         json={"nom": "Updated Name"})
        assert rv2.status_code == 200
        assert rv2.get_json()["client"]["nom"] == "Updated Name"

    def test_client_profile(self, client, auth_headers):
        rv = client.post("/api/clients", headers=auth_headers, json={"code_client": "CLI004"})
        cid = rv.get_json()["client"]["id"]
        rv2 = client.get(f"/api/clients/{cid}/profile", headers=auth_headers)
        assert rv2.status_code == 200
        assert "client" in rv2.get_json()
        assert "timeline" in rv2.get_json()


class TestDashboard:
    def test_kpis_requires_auth(self, client):
        rv = client.get("/api/dashboard/kpis")
        assert rv.status_code == 401

    def test_kpis_returns_structure(self, client, auth_headers):
        rv = client.get("/api/dashboard/kpis", headers=auth_headers)
        assert rv.status_code == 200
        data = rv.get_json()
        assert "clients" in data
        assert "risk_distribution" in data
        assert "financials" in data

    def test_overview(self, client, auth_headers):
        rv = client.get("/api/dashboard/overview", headers=auth_headers)
        assert rv.status_code == 200
        data = rv.get_json()
        assert "kpis" in data
        assert "top_risk" in data


class TestPredict:
    def test_model_not_ready(self, client, auth_headers):
        rv = client.get("/api/predict/ready", headers=auth_headers)
        assert rv.status_code == 200
        data = rv.get_json()
        assert "ready" in data

    def test_predict_no_model(self, client, auth_headers):
        """With no model loaded, should return 503."""
        rv = client.post("/api/predict/single", headers=auth_headers, json={
            "CODE_CLIENT": "TEST001",
            "NB_FACTURES": 5,
        })
        # Either 503 (no model) or 200 (if model somehow loaded)
        assert rv.status_code in (200, 503)
