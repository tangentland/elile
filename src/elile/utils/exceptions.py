"""Custom exceptions for Elile."""


class ElileError(Exception):
    """Base exception for all Elile errors."""

    pass


class ModelError(ElileError):
    """Error related to model operations."""

    pass


class RateLimitError(ModelError):
    """Rate limit exceeded for model API."""

    pass


class SearchError(ElileError):
    """Error during search operations."""

    pass


class ConfigurationError(ElileError):
    """Error in configuration or settings."""

    pass
