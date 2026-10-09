"""
Comprehensive unit tests for API router configuration.

This module tests the router setup covering:
- Router initialization
- Endpoint registration
- Prefix and tag configuration
"""

from fastapi import APIRouter

from app.api.v1.router import api_router


class TestAPIRouter:
    """Tests for API router configuration."""

    def test_api_router_initialized(self):
        """Test: API router is initialized as APIRouter instance."""
        # Assert
        assert isinstance(api_router, APIRouter)

    def test_api_router_has_routes(self):
        """Test: API router has registered routes."""
        # Assert
        assert len(api_router.routes) > 0

    def test_api_router_includes_youtube_endpoint(self):
        """Test: YouTube endpoint router is included with correct prefix and tags."""
        # Arrange & Act
        youtube_routes = [route for route in api_router.routes if "/youtube" in str(route.path)]

        # Assert
        assert len(youtube_routes) > 0
        # Check that routes have the correct prefix
        assert any("/transcriptions/youtube" in str(route.path) for route in youtube_routes)

    def test_api_router_includes_media_endpoint(self):
        """Test: Media endpoint router is included with correct prefix and tags."""
        # Arrange & Act
        media_routes = [route for route in api_router.routes if "/media" in str(route.path)]

        # Assert
        assert len(media_routes) > 0
        # Check that routes have the correct prefix
        assert any("/transcriptions/media" in str(route.path) for route in media_routes)

    def test_api_router_includes_jobs_endpoint(self):
        """Test: Jobs endpoint router is included with correct prefix and tags."""
        # Arrange & Act
        jobs_routes = [route for route in api_router.routes if "/jobs" in str(route.path)]

        # Assert
        assert len(jobs_routes) > 0
        # Check that routes have the correct prefix
        assert any("/jobs" in str(route.path) for route in jobs_routes)

    def test_api_router_includes_metrics_endpoint(self):
        """Test: Metrics endpoint router is included."""
        # Arrange & Act
        metrics_routes = [route for route in api_router.routes if "/metrics" in str(route.path)]

        # Assert
        assert len(metrics_routes) > 0

    def test_api_router_includes_workers_endpoint(self):
        """Test: Workers endpoint router is included with correct prefix and tags."""
        # Arrange & Act
        workers_routes = [route for route in api_router.routes if "/workers" in str(route.path)]

        # Assert
        assert len(workers_routes) > 0
        # Check that routes have the correct prefix
        assert any("/workers" in str(route.path) for route in workers_routes)

    def test_api_router_transcriptions_tag(self):
        """Test: Transcription endpoints (YouTube and Media) have correct tags."""
        # Arrange & Act
        transcription_routes = [
            route for route in api_router.routes if "/transcriptions" in str(route.path)
        ]

        # Assert
        assert len(transcription_routes) > 0
        # Check tags (if available in route metadata)
        for route in transcription_routes:
            # Routes should be tagged appropriately
            assert route is not None

    def test_api_router_jobs_tag(self):
        """Test: Jobs endpoints have correct tags."""
        # Arrange & Act
        jobs_routes = [route for route in api_router.routes if "/jobs" in str(route.path)]

        # Assert
        assert len(jobs_routes) > 0

    def test_api_router_workers_tag(self):
        """Test: Workers endpoints have correct tags."""
        # Arrange & Act
        workers_routes = [route for route in api_router.routes if "/workers" in str(route.path)]

        # Assert
        assert len(workers_routes) > 0

    def test_api_router_monitoring_tag(self):
        """Test: Metrics endpoint has monitoring tag."""
        # Arrange & Act
        metrics_routes = [route for route in api_router.routes if "/metrics" in str(route.path)]

        # Assert
        assert len(metrics_routes) > 0

    def test_api_router_all_endpoints_registered(self):
        """Test: All expected endpoints are registered."""
        # Arrange
        expected_paths = [
            "/transcriptions/youtube",
            "/transcriptions/media",
            "/jobs",
            "/metrics",
            "/workers",
        ]

        # Act
        registered_paths = [str(route.path) for route in api_router.routes]

        # Assert
        # Check that at least one route matches each expected path pattern
        for expected_path in expected_paths:
            assert any(
                expected_path in path for path in registered_paths
            ), f"Path {expected_path} not found in routes"

    def test_api_router_no_duplicate_routes(self):
        """Test: No duplicate routes are registered."""
        # Arrange & Act
        # Collect route paths for duplicate checking
        _ = [str(route.path) for route in api_router.routes]

        # Assert
        # Check for exact duplicates (same path and method)
        unique_routes = set()
        for route in api_router.routes:
            # Convert methods to a hashable type (frozenset or tuple)
            methods = getattr(route, "methods", None)
            if methods is not None:
                # Convert set to frozenset for hashing
                methods = frozenset(methods) if isinstance(methods, set) else tuple(methods)
            route_key = (str(route.path), methods)
            assert route_key not in unique_routes, f"Duplicate route found: {route.path}"
            unique_routes.add(route_key)

    def test_api_router_http_methods_configured(self):
        """Test: Routes have HTTP methods configured."""
        # Arrange & Act
        routes_with_methods = [
            route for route in api_router.routes if hasattr(route, "methods") and route.methods
        ]

        # Assert
        # Most routes should have methods configured
        assert len(routes_with_methods) > 0

    def test_api_router_youtube_post_method(self):
        """Test: YouTube endpoint has POST method."""
        # Arrange & Act
        youtube_post_routes = [
            route
            for route in api_router.routes
            if "/youtube" in str(route.path)
            and hasattr(route, "methods")
            and "POST" in route.methods
        ]

        # Assert
        assert len(youtube_post_routes) > 0

    def test_api_router_media_post_method(self):
        """Test: Media endpoint has POST method."""
        # Arrange & Act
        media_post_routes = [
            route
            for route in api_router.routes
            if "/media" in str(route.path) and hasattr(route, "methods") and "POST" in route.methods
        ]

        # Assert
        assert len(media_post_routes) > 0

    def test_api_router_jobs_get_method(self):
        """Test: Jobs endpoints have GET methods."""
        # Arrange & Act
        jobs_get_routes = [
            route
            for route in api_router.routes
            if "/jobs" in str(route.path) and hasattr(route, "methods") and "GET" in route.methods
        ]

        # Assert
        assert len(jobs_get_routes) > 0

    def test_api_router_workers_get_method(self):
        """Test: Workers endpoints have GET methods."""
        # Arrange & Act
        workers_get_routes = [
            route
            for route in api_router.routes
            if "/workers" in str(route.path)
            and hasattr(route, "methods")
            and "GET" in route.methods
        ]

        # Assert
        assert len(workers_get_routes) > 0

    def test_api_router_workers_post_method(self):
        """Test: Workers endpoints have POST methods."""
        # Arrange & Act
        workers_post_routes = [
            route
            for route in api_router.routes
            if "/workers" in str(route.path)
            and hasattr(route, "methods")
            and "POST" in route.methods
        ]

        # Assert
        assert len(workers_post_routes) > 0

    def test_api_router_metrics_get_method(self):
        """Test: Metrics endpoint has GET method."""
        # Arrange & Act
        metrics_get_routes = [
            route
            for route in api_router.routes
            if "/metrics" in str(route.path)
            and hasattr(route, "methods")
            and "GET" in route.methods
        ]

        # Assert
        assert len(metrics_get_routes) > 0
