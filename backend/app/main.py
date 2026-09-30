from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.body_limit import RequestBodyLimitMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.v1.auth import router as auth_router
from app.api.v1.controls import mapping_router as control_mapping_router
from app.api.v1.controls import router as controls_router
from app.api.v1.crosswalks import requirement_router as crosswalk_requirement_router
from app.api.v1.crosswalks import router as crosswalks_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.documents import control_router as document_control_router
from app.api.v1.documents import requirement_router as document_requirement_router
from app.api.v1.documents import router as documents_router
from app.api.v1.evidence import control_router as evidence_control_router
from app.api.v1.evidence import requirement_router as evidence_requirement_router
from app.api.v1.evidence import router as evidence_router
from app.api.v1.exports import router as exports_router
from app.api.v1.frameworks import router as frameworks_router
from app.api.v1.health import router as health_router
from app.api.v1.inference import router as inference_router
from app.api.v1.requirements import router as requirements_router
from app.api.v1.users import router as users_router
from app.core.config import Settings
from app.core.database import DatabaseManager
from app.core.errors import safe_validation_error
from app.core.middleware import safe_request_middleware
from app.core.request_security import request_security_middleware
from app.inference.openai_compatible import OpenAICompatibleGateway
from app.inference.registry import InferenceRegistry, RegistryError, load_registry
from app.services.auth import LoginThrottle
from app.services.inference_runs import RunLimiter
from app.storage import LocalFilesystemStorage


def create_app(
    settings: Settings | None = None,
    database_manager: object | None = None,
) -> FastAPI:
    runtime_settings = settings or Settings()
    database = database_manager or DatabaseManager(runtime_settings.database_url)
    app = FastAPI(title="Compliance Control Map API", version="0.1.0")
    app.add_exception_handler(RequestValidationError, safe_validation_error)
    app.state.settings = runtime_settings
    app.state.database = database
    app.state.login_throttle = LoginThrottle()
    app.state.storage = LocalFilesystemStorage(runtime_settings.storage_root)
    app.state.inference_registry = InferenceRegistry(agents={}, skills={})
    app.state.inference_registry_error = None
    app.state.inference_limiter = RunLimiter(runtime_settings.inference_max_concurrent_runs)
    app.state.inference_gateway_factory = (
        lambda connection, secret: OpenAICompatibleGateway(connection, api_key=secret)
    )
    if runtime_settings.inference_enabled:
        try:
            app.state.inference_registry = load_registry(
                runtime_settings.inference_agent_root,
                runtime_settings.inference_skill_root,
                max_iterations=runtime_settings.inference_max_iterations,
                timeout_seconds=runtime_settings.inference_timeout_seconds,
            )
        except RegistryError as exc:
            app.state.inference_registry_error = str(exc)
    app.middleware("http")(request_security_middleware)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=runtime_settings.allowed_hosts)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=runtime_settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-CSRF-Token", "X-Request-ID"],
    )
    app.add_middleware(
        RequestBodyLimitMiddleware,
        max_body_size=runtime_settings.max_upload_bytes + 256 * 1024,
    )
    # Registered last so request IDs and safe error handling wrap every other layer.
    app.middleware("http")(safe_request_middleware)
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(frameworks_router, prefix="/api/v1")
    app.include_router(requirements_router, prefix="/api/v1")
    app.include_router(controls_router, prefix="/api/v1")
    app.include_router(control_mapping_router, prefix="/api/v1")
    app.include_router(crosswalks_router, prefix="/api/v1")
    app.include_router(crosswalk_requirement_router, prefix="/api/v1")
    app.include_router(documents_router, prefix="/api/v1")
    app.include_router(document_requirement_router, prefix="/api/v1")
    app.include_router(document_control_router, prefix="/api/v1")
    app.include_router(evidence_router, prefix="/api/v1")
    app.include_router(evidence_requirement_router, prefix="/api/v1")
    app.include_router(evidence_control_router, prefix="/api/v1")
    app.include_router(dashboard_router, prefix="/api/v1")
    app.include_router(exports_router, prefix="/api/v1")
    app.include_router(users_router, prefix="/api/v1")
    app.include_router(inference_router, prefix="/api/v1")
    return app


app = create_app()
