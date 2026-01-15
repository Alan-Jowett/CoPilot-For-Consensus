# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Sentry error reporter implementation (scaffold for future use)."""

from typing import Any

from copilot_config.generated.adapters.error_reporter import DriverConfig_ErrorReporter_Sentry

from .error_reporter import ErrorReporter


class SentryErrorReporter(ErrorReporter):
    """Sentry error reporter for cloud-based error tracking.

    This is a scaffold implementation for future integration with Sentry.
    To use this reporter, install the sentry-sdk package and provide a DSN.

    Example:
        reporter = SentryErrorReporter(dsn="https://...@sentry.io/...")
        reporter.report(exception, context={"user_id": "123"})
    """

    def __init__(self, dsn: str | None = None, environment: str | None = None):
        """Initialize Sentry error reporter.

        Args:
            dsn: Sentry DSN (Data Source Name) for the project
            environment: Environment name (production, staging, development).
                Defaults should be defined in the schema when using typed configs.
        """
        self.dsn = dsn
        self.environment = environment
        self._initialized = False

        if dsn:
            self._initialize_sentry()

    @classmethod
    def from_config(cls, config: DriverConfig_ErrorReporter_Sentry) -> "SentryErrorReporter":
        """Create a SentryErrorReporter from driver configuration.

        Args:
            config: Driver config with dsn and environment attributes.
                Environment default is provided by the schema.

        Returns:
            Configured SentryErrorReporter instance
        """
        return cls(dsn=config.dsn, environment=config.environment)

    def _initialize_sentry(self) -> None:
        """Initialize Sentry SDK.

        Note: This is a scaffold. Actual implementation requires:
            pip install sentry-sdk
        """
        try:
            import sentry_sdk  # type: ignore[reportMissingImports]
            sentry_sdk.init(
                dsn=self.dsn,
                environment=self.environment,
                # Additional configuration can be added here
                traces_sample_rate=1.0,
            )
            self._initialized = True
        except ImportError:
            raise ImportError(
                "sentry-sdk is not installed. "
                "Install it with: pip install sentry-sdk"
            )

    def report(self, error: Exception, context: dict[str, Any] | None = None) -> None:
        """Report an exception with optional context.

        Args:
            error: The exception to report
            context: Optional dictionary with additional context
        """
        if not self._initialized:
            raise RuntimeError("Sentry reporter not initialized with a valid DSN")

        try:
            import sentry_sdk  # type: ignore[reportMissingImports]

            # Set context if provided
            if context:
                with sentry_sdk.push_scope() as scope:
                    # Set tags for simple key-value pairs
                    for key, value in context.items():
                        scope.set_tag(key, str(value))
                    # Also set full context as a dictionary
                    scope.set_context("error_context", context)
                    sentry_sdk.capture_exception(error)
            else:
                sentry_sdk.capture_exception(error)

        except ImportError:
            raise ImportError(
                "sentry-sdk is not installed. "
                "Install it with: pip install sentry-sdk"
            )

    def capture_message(
        self,
        message: str,
        level: str = "error",
        context: dict[str, Any] | None = None
    ) -> None:
        """Capture a message without an exception.

        Args:
            message: The message to capture
            level: Severity level (debug, info, warning, error, critical)
            context: Optional dictionary with additional context
        """
        if not self._initialized:
            raise RuntimeError("Sentry reporter not initialized with a valid DSN")

        try:
            import sentry_sdk  # type: ignore[reportMissingImports]

            # Map our level names to Sentry level names
            level_map = {
                "debug": "debug",
                "info": "info",
                "warning": "warning",
                "error": "error",
                "critical": "fatal",
            }

            sentry_level = level_map.get(level.lower(), "error")

            # Set context if provided
            if context:
                with sentry_sdk.push_scope() as scope:
                    # Set tags for simple key-value pairs
                    for key, value in context.items():
                        scope.set_tag(key, str(value))
                    # Also set full context as a dictionary
                    scope.set_context("message_context", context)
                    sentry_sdk.capture_message(message, level=sentry_level)
            else:
                sentry_sdk.capture_message(message, level=sentry_level)

        except ImportError:
            raise ImportError(
                "sentry-sdk is not installed. "
                "Install it with: pip install sentry-sdk"
            )
