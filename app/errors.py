from dataclasses import dataclass


@dataclass
class AppError(Exception):
    code: str
    message: str
    hint: str | None = None
    status_code: int = 500

    def __str__(self) -> str:
        return self.message


class UserInputError(AppError):
    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(
            code="user_input_invalid",
            message=message,
            hint=hint,
            status_code=400,
        )


class ResourceNotReadyError(AppError):
    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(
            code="resource_not_ready",
            message=message,
            hint=hint,
            status_code=400,
        )


class ConfigurationError(AppError):
    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(
            code="configuration_error",
            message=message,
            hint=hint,
            status_code=500,
        )


class ProviderAuthError(AppError):
    def __init__(self) -> None:
        super().__init__(
            code="provider_auth_failed",
            message="Live answer generation is currently unavailable.",
            hint="The backend API key is missing, invalid, or expired.",
            status_code=503,
        )


class ProviderUnavailableError(AppError):
    def __init__(self) -> None:
        super().__init__(
            code="provider_unavailable",
            message="The LLM provider is temporarily unavailable.",
            hint="Retry shortly or check provider connectivity and quota.",
            status_code=503,
        )


class ModelOutputError(AppError):
    def __init__(self, message: str = "The LLM returned invalid structured output.") -> None:
        super().__init__(
            code="model_output_invalid",
            message=message,
            hint="Check the prompt contract and model response format.",
            status_code=502,
        )