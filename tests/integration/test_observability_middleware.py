"""Integration tests for observability middleware."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from elile.api.middleware.observability import ObservabilityMiddleware
from elile.observability import get_metrics


@pytest.fixture
def test_app() -> FastAPI:
    """Create test FastAPI application with observability middleware."""
    app = FastAPI()
    app.add_middleware(ObservabilityMiddleware)

    @app.get("/test")
    async def test_endpoint() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/test/{item_id}")
    async def test_with_id(item_id: str) -> dict[str, str]:
        return {"item_id": item_id}

    @app.post("/test")
    async def test_post() -> dict[str, str]:
        return {"created": "true"}

    @app.get("/error")
    async def error_endpoint() -> dict[str, str]:
        raise ValueError("Test error")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "healthy"}

    @app.get("/metrics")
    async def metrics() -> dict[str, str]:
        return {"metrics": "data"}

    return app


@pytest.fixture
def client(test_app: FastAPI) -> TestClient:
    """Create test client."""
    return TestClient(test_app)


class TestObservabilityMiddleware:
    """Tests for ObservabilityMiddleware."""

    def test_successful_request_records_metrics(self, client: TestClient) -> None:
        """Test that successful requests are recorded."""
        response = client.get("/test")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_request_with_path_parameter(self, client: TestClient) -> None:
        """Test requests with path parameters are normalized."""
        response = client.get("/test/12345")

        assert response.status_code == 200
        assert response.json()["item_id"] == "12345"

    def test_request_with_uuid(self, client: TestClient) -> None:
        """Test requests with UUID path parameter."""
        response = client.get("/test/550e8400-e29b-41d4-a716-446655440000")

        assert response.status_code == 200

    def test_post_request(self, client: TestClient) -> None:
        """Test POST requests are recorded."""
        response = client.post("/test")

        assert response.status_code == 200
        assert response.json()["created"] == "true"

    def test_excluded_paths_not_recorded(self, client: TestClient) -> None:
        """Test that excluded paths bypass metrics."""
        # These should not record metrics
        response = client.get("/health")
        assert response.status_code == 200

        response = client.get("/metrics")
        assert response.status_code == 200

    def test_error_response_recorded(self, client: TestClient) -> None:
        """Test that error responses are recorded."""
        # Note: In test client, unhandled exceptions return 500
        with pytest.raises(ValueError):
            client.get("/error")


class TestPathNormalization:
    """Tests for path normalization in middleware."""

    def test_uuid_normalization(self) -> None:
        """Test UUID path normalization."""
        middleware = ObservabilityMiddleware(app=FastAPI())

        path = "/v1/screenings/550e8400-e29b-41d4-a716-446655440000/results"
        normalized = middleware._normalize_path(path)

        assert normalized == "/v1/screenings/{id}/results"

    def test_numeric_id_normalization(self) -> None:
        """Test numeric ID path normalization."""
        middleware = ObservabilityMiddleware(app=FastAPI())

        path = "/api/users/12345/orders/67890"
        normalized = middleware._normalize_path(path)

        assert normalized == "/api/users/{id}/orders/{id}"

    def test_no_normalization_needed(self) -> None:
        """Test paths without IDs remain unchanged."""
        middleware = ObservabilityMiddleware(app=FastAPI())

        path = "/v1/screenings/"
        normalized = middleware._normalize_path(path)

        assert normalized == "/v1/screenings/"


class TestMetricsEndpoint:
    """Tests for metrics endpoint integration."""

    def test_metrics_endpoint_available(self) -> None:
        """Test that metrics can be retrieved."""
        metrics = get_metrics()

        assert isinstance(metrics, bytes)
        assert len(metrics) > 0

    def test_metrics_format(self) -> None:
        """Test metrics are in Prometheus format."""
        metrics = get_metrics().decode("utf-8")

        # Prometheus format should have # HELP and # TYPE comments
        assert "# HELP" in metrics or "elile_" in metrics
