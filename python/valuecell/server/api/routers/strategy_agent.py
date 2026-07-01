"""
StrategyAgent router for handling strategy creation via streaming responses.
"""

import os

# New imports for delete endpoint
from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from sqlalchemy.orm import Session

from valuecell.agents.common.trading.models import (
    ExchangeConfig,
    StrategyStatus,
    StrategyStatusContent,
    StrategyType,
    TradingMode,
    UserRequest,
)
from valuecell.agents.common.trading.execution.ccxt_trading import create_ccxt_gateway
from valuecell.config.loader import get_config_loader
from valuecell.core.types import CommonResponseEvent, UserInput, UserInputMetadata
from valuecell.server.api.schemas.base import ErrorResponse, StatusCode, SuccessResponse

# Note: Strategy type is now part of TradingConfig in the request body.
from valuecell.server.db.connection import get_db
from valuecell.server.db.repositories import get_strategy_repository
from valuecell.server.services.strategy_autoresume import (
    backfill_exchange_credentials,
    resume_strategy,
)
from valuecell.utils.uuid import generate_conversation_id

def create_strategy_agent_router() -> APIRouter:
    """Create and configure the StrategyAgent router."""

    router = APIRouter(prefix="/strategies", tags=["strategies"])
    orchestrator = None

    def get_orchestrator():
        nonlocal orchestrator
        if orchestrator is None:
            from valuecell.core.coordinate.orchestrator import AgentOrchestrator

            orchestrator = AgentOrchestrator()
        return orchestrator

    @router.on_event("startup")
    async def _startup_auto_resume() -> None:
        """Schedule strategy auto-resume on FastAPI startup."""
        if os.getenv("VALUECELL_AUTO_RESUME_STRATEGIES") != "1":
            logger.info("Skipping strategy auto-resume")
            return
        try:
            from valuecell.server.services.strategy_autoresume import auto_resume_strategies

            await auto_resume_strategies(get_orchestrator())
        except Exception:
            logger.warning("Failed to schedule strategy auto-resume startup task")

    @router.post("/create")
    async def create_strategy_agent(
        request: UserRequest,
        db: Session = Depends(get_db),
    ):
        """
        Create a strategy through StrategyAgent and return final JSON result.

        This endpoint accepts a structured request body, maps it to StrategyAgent's
        UserRequest JSON, and returns an aggregated JSON response (non-SSE).
        """
        try:
            # Helper: dump request config without sensitive credentials
            def _safe_config_dump(req: UserRequest) -> dict:
                return req.model_dump(
                    exclude={
                        "exchange_config": {
                            "api_key",
                            "secret_key",
                            "passphrase",
                            "wallet_address",
                            "private_key",
                        }
                    }
                )

            # Assign initial_capital value to initial_free_cash.
            # Only used for paper tradings, the system would use account portfolio data for LIVE tradings.
            request.trading_config.initial_free_cash = (
                request.trading_config.initial_capital
            )
            if (
                request.exchange_config.trading_mode == TradingMode.VIRTUAL
                and request.exchange_config.exchange_id not in {None, ""}
            ):
                logger.warning(
                    "Virtual trading requested on non-default exchange_id '{}'. Ensure this is intended.",
                    request.exchange_config.exchange_id,
                )
                request.exchange_config.exchange_id = None
            # Ensure we only serialize the core UserRequest fields, excluding conversation_id
            user_request = UserRequest(
                llm_model_config=request.llm_model_config,
                exchange_config=request.exchange_config,
                trading_config=request.trading_config,
            )

            # If same provider + model_id comes with a new api_key, override previous key
            try:
                provider = user_request.llm_model_config.provider
                model_id = user_request.llm_model_config.model_id
                new_api_key = user_request.llm_model_config.api_key
                if provider and model_id and new_api_key:
                    loader = get_config_loader()
                    provider_cfg_raw = loader.load_provider_config(provider) or {}
                    api_key_env = provider_cfg_raw.get("connection", {}).get(
                        "api_key_env"
                    )
                    # Update environment and clear loader cache so subsequent reads use new key
                    if api_key_env:
                        os.environ[api_key_env] = new_api_key
                        loader.clear_cache()
            except Exception:
                # Best-effort override; continue even if config update fails
                pass

            # Prepare repository with injected session (used below and for prompt resolution)
            repo = get_strategy_repository(db_session=db)

            # If a prompt_id (previously template_id) is provided but prompt_text is empty,
            # attempt to resolve it from the prompts table and populate trading_config.prompt_text.
            try:
                prompt_id = user_request.trading_config.template_id
                if prompt_id and not user_request.trading_config.prompt_text:
                    try:
                        prompt_item = repo.get_prompt_by_id(prompt_id)
                        if prompt_item is not None:
                            # prompt_item may be an ORM object or dict-like; use attribute or key access
                            content = prompt_item.content
                            if content:
                                user_request.trading_config.prompt_text = content
                                logger.info(
                                    "Resolved prompt_id={} to prompt_text for strategy creation",
                                    prompt_id,
                                )
                    except Exception:
                        logger.exception(
                            "Failed to load prompt for prompt_id={}; continuing without resolved prompt",
                            prompt_id,
                        )
            except Exception:
                # Defensive: any unexpected error here should not block strategy creation
                logger.exception(
                    "Unexpected error while resolving prompt_id before strategy creation"
                )

            query = user_request.model_dump_json()

            # Use enum directly for comparison; derive human-readable label for metadata
            strategy_type_enum = (
                user_request.trading_config.strategy_type or StrategyType.PROMPT
            )

            if strategy_type_enum == StrategyType.PROMPT:
                agent_name = "PromptBasedStrategyAgent"
            elif strategy_type_enum == StrategyType.GRID:
                agent_name = "GridStrategyAgent"
            else:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Unsupported strategy_type: '{strategy_type_enum}'. "
                        "Use 'PromptBasedStrategy' or 'GridStrategy'"
                    ),
                )

            # Build UserInput for orchestrator
            user_input_meta = UserInputMetadata(
                user_id="default_user",
                conversation_id=generate_conversation_id(),
            )
            user_input = UserInput(
                query=query,
                target_agent_name=agent_name,
                meta=user_input_meta,
            )

            # Prepare repository with injected session
            repo = get_strategy_repository(db_session=db)

            # Directly use process_user_input instead of stream_query_agent
            try:
                async for chunk_obj in get_orchestrator().process_user_input(user_input):
                    event = chunk_obj.event
                    data = chunk_obj.data

                    if event == CommonResponseEvent.COMPONENT_GENERATOR:
                        content = data.payload.content
                        status_content = StrategyStatusContent.model_validate_json(
                            content
                        )

                        # Persist strategy to database via repository (best-effort)
                        try:
                            name = (
                                request.trading_config.strategy_name
                                or f"Strategy-{status_content.strategy_id[:8]}"
                            )
                            metadata = {
                                "agent_name": agent_name,
                                "strategy_type": strategy_type_enum,
                                "model_provider": request.llm_model_config.provider,
                                "model_id": request.llm_model_config.model_id,
                                "exchange_id": request.exchange_config.exchange_id,
                                "trading_mode": request.exchange_config.trading_mode.value,
                            }
                            status = status_content.status
                            if status == StrategyStatus.STOPPED:
                                metadata["stop_reason"] = (
                                    status_content.stop_reason.value
                                )
                                metadata["stop_reason_detail"] = (
                                    status_content.stop_reason_detail
                                )
                                return ErrorResponse.create(
                                    code=StatusCode.INTERNAL_ERROR,
                                    msg=status_content.stop_reason_detail,
                                )
                            repo.upsert_strategy(
                                strategy_id=status_content.strategy_id,
                                name=name,
                                description=None,
                                user_id=user_input_meta.user_id,
                                status=status.value,
                                config=_safe_config_dump(request),
                                metadata=metadata,
                            )
                        except Exception:
                            # Do not fail the API due to persistence error
                            pass

                        # Unified success response with strategy_id
                        return SuccessResponse.create(
                            data={"strategy_id": status_content.strategy_id}
                        )

                # No status event received; do NOT persist or fallback, return error only
                return ErrorResponse.create(
                    code=StatusCode.INTERNAL_ERROR,
                    msg="No status event from orchestrator",
                )
            except Exception:
                # Orchestrator failed; do NOT persist or fallback, return generic error only
                return ErrorResponse.create(
                    code=StatusCode.INTERNAL_ERROR, msg="Internal error"
                )

        except Exception:
            # As a last resort, log without sensitive details and return generic error.
            logger.exception("Failed to create strategy in API endpoint")
            return ErrorResponse.create(
                code=StatusCode.INTERNAL_ERROR, msg="Internal error"
            )

    @router.post("/test-connection")
    async def test_exchange_connection(request: ExchangeConfig):
        """Test connection to the exchange with provided credentials."""
        gateway = None
        try:
            if request.trading_mode == TradingMode.VIRTUAL:
                return SuccessResponse.create(msg="Success!")

            gateway = await create_ccxt_gateway(
                exchange_id=request.exchange_id,
                api_key=request.api_key or "",
                secret_key=request.secret_key or "",
                passphrase=request.passphrase,
                wallet_address=request.wallet_address,
                private_key=request.private_key,
                market_type="spot",
            )

            is_connected = await gateway.test_connection()
            if is_connected:
                return SuccessResponse.create(msg="Success!")

            raise HTTPException(
                status_code=400,
                detail="Connection failed: exchange returned unsuccessful result",
            )
        except Exception as e:
            logger.warning(
                "Connection test failed for {exchange_id}: {error}",
                exchange_id=request.exchange_id,
                error=str(e),
            )
            raise HTTPException(
                status_code=400,
                detail=f"Connection test failed: {str(e)}",
            )
        finally:
            if gateway is not None:
                await gateway.close()

    @router.delete("/delete")
    async def delete_strategy_agent(
        id: str = Query(..., description="Strategy ID"),
        cascade: bool = Query(
            True, description="Delete related records (holdings/details/portfolio)"
        ),
        db: Session = Depends(get_db),
    ):
        """Delete a strategy created by StrategyAgent.

        - Validates the strategy exists.
        - Ensures the strategy is stopped before deletion (idempotent stop).
        - Optionally cascades deletion to holdings, portfolio snapshots, and details.
        - Returns a success response when completed.
        """
        try:
            repo = get_strategy_repository(db_session=db)
            strategy = repo.get_strategy_by_strategy_id(id)
            if not strategy:
                raise HTTPException(status_code=404, detail="Strategy not found")

            # Stop strategy before deletion (best-effort, idempotent)
            try:
                current_status = getattr(strategy, "status", None)
                if current_status != "stopped":
                    repo.upsert_strategy(strategy_id=id, status="stopped")
            except Exception:
                # Do not fail deletion due to stop failure; proceed to deletion
                pass

            ok = repo.delete_strategy(id, cascade=cascade)
            if not ok:
                raise HTTPException(status_code=500, detail="Failed to delete strategy")

            return SuccessResponse.create(
                data={"strategy_id": id},
                msg=f"Strategy '{id}' stopped (if running) and deleted successfully",
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error deleting strategy: {str(e)}"
            )

    @router.post("/restart")
    async def restart_strategy_agent(
        id: str = Query(..., description="Strategy ID"),
        db: Session = Depends(get_db),
    ):
        """Restart a stopped strategy using its stored configuration."""
        try:
            repo = get_strategy_repository(db_session=db)
            strategy = repo.get_strategy_by_strategy_id(id)
            if not strategy:
                raise HTTPException(status_code=404, detail="Strategy not found")

            if strategy.status == StrategyStatus.RUNNING.value:
                return SuccessResponse.create(
                    data={"strategy_id": id},
                    msg=f"Strategy '{id}' is already running",
                )

            metadata = strategy.strategy_metadata or {}
            resume_metadata = dict(metadata)
            resume_metadata.pop("stop_reason", None)
            resume_metadata.pop("stop_reason_detail", None)

            # Persisted configs are sanitized and do not contain exchange
            # credentials. Reconstruct missing live-trading secrets from the
            # current environment before dispatching the runtime.
            strategy.config = backfill_exchange_credentials(strategy.config or {})
            strategy.strategy_metadata = resume_metadata

            resumed = await resume_strategy(get_orchestrator(), strategy)
            if not resumed:
                failure_metadata = {
                    **resume_metadata,
                    "stop_reason": "error",
                    "stop_reason_detail": (
                        "Strategy restart failed. Check exchange credentials and "
                        "backend logs for details."
                    ),
                }
                repo.upsert_strategy(
                    strategy_id=id,
                    status=StrategyStatus.STOPPED.value,
                    metadata=failure_metadata,
                )
                raise HTTPException(
                    status_code=500,
                    detail=failure_metadata["stop_reason_detail"],
                )

            repo.upsert_strategy(
                strategy_id=id,
                status=StrategyStatus.RUNNING.value,
                metadata=resume_metadata,
            )

            return SuccessResponse.create(
                data={"strategy_id": id},
                msg=f"Strategy '{id}' restarted successfully",
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error restarting strategy: {str(e)}"
            )

    return router
