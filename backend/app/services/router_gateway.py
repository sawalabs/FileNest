import asyncio
import json
import time
from typing import Any, Dict, List, Optional
import httpx
from sqlalchemy.orm import Session

from backend.app.core.security import validate_probe_url
from backend.app.db.base import generate_uuid
from backend.app.db.repositories.audit import AuditLogRepository
from backend.app.schemas.router_gateway import (
    RouterChatMessage,
    RouterChatRequest,
    RouterChatResponse,
    RouterHealthResponse,
    RouterModelItem,
    RouterModelListResponse,
    RouterTokenUsage,
)
from backend.app.services.credential_service import CredentialService
from backend.app.services.settings_service import SettingsService


class RouterGatewayException(Exception):
    """Custom exception raised for 9Router model gateway errors."""
    pass


RouterException = RouterGatewayException


class RouterGatewayService:
    ROUTER_KEY_ID = "9router_api_key"
    OPENROUTER_KEY_ID = "openrouter_api_key"

    FALLBACK_MODELS = [
        RouterModelItem(
            id="gpt-4o-mini",
            name="GPT-4o Mini (Fast & Efficient)",
            context_length=128000,
            provider="9Router",
            supports_vision=True,
            is_default=True,
        ),
        RouterModelItem(
            id="gpt-4o",
            name="GPT-4o (High Accuracy Analysis)",
            context_length=128000,
            provider="9Router",
            supports_vision=True,
            is_default=False,
        ),
        RouterModelItem(
            id="claude-3-5-sonnet",
            name="Claude 3.5 Sonnet (Advanced Reasoning)",
            context_length=200000,
            provider="9Router",
            supports_vision=True,
            is_default=False,
        ),
        RouterModelItem(
            id="gemini-1.5-pro",
            name="Gemini 1.5 Pro (Large Context)",
            context_length=1000000,
            provider="9Router",
            supports_vision=True,
            is_default=False,
        ),
    ]

    def __init__(self, db: Session):
        self.db = db
        self.settings_service = SettingsService(db)
        self.audit_repo = AuditLogRepository(db)

    # =========================================================================
    # HTTP Gateway Callers (Encapsulated for testability & timeout safety)
    # =========================================================================

    async def _get_from_gateway(
        self, url: str, headers: Dict[str, str], timeout: int
    ) -> httpx.Response:
        async with httpx.AsyncClient(timeout=timeout) as client:
            return await client.get(url, headers=headers)

    async def _post_to_gateway(
        self, url: str, headers: Dict[str, str], body: Dict[str, Any], timeout: int
    ) -> httpx.Response:
        async with httpx.AsyncClient(timeout=timeout) as client:
            return await client.post(url, headers=headers, json=body)

    # =========================================================================
    # Health and Connectivity
    # =========================================================================

    async def check_health(
        self,
        endpoint_override: Optional[str] = None,
        api_key_override: Optional[str] = None,
        timeout: int = 15,
    ) -> RouterHealthResponse:
        """Checks connectivity and diagnostics of the configured 9Router instance, plus OpenRouter fallback status."""
        ai_cfg = self.settings_service.get_ai_settings()
        saved_endpoint = (ai_cfg.router_endpoint or "").strip()

        fallback_status = None
        if ai_cfg.auto_fallback_enabled:
            openrouter_key = CredentialService.get_secret(self.OPENROUTER_KEY_ID)
            fallback_status = "connected" if bool(openrouter_key) else "not_configured"

        if endpoint_override is not None:
            endpoint = endpoint_override.strip()
        else:
            endpoint = saved_endpoint

        if not endpoint:
            return RouterHealthResponse(
                status="not_configured",
                endpoint="",
                message="9Router endpoint belum dikonfigurasi.",
                authenticated=False,
                fallback_status=fallback_status,
            )

        # Validate endpoint format and prevent SSRF
        try:
            validate_probe_url(endpoint)
        except ValueError as err:
            return RouterHealthResponse(
                status="error",
                endpoint=endpoint,
                message=f"Endpoint tidak valid atau diblokir: {str(err)}",
                authenticated=False,
                fallback_status=fallback_status,
            )

        # Prevent API key exfiltration: only attach stored credentials if endpoint matches saved configuration
        is_saved_endpoint = (endpoint.rstrip("/").lower() == saved_endpoint.rstrip("/").lower())
        if is_saved_endpoint:
            api_key = api_key_override or CredentialService.get_secret(self.ROUTER_KEY_ID)
        else:
            api_key = api_key_override  # Never leak stored credentials to unverified override targets

        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        start_time = time.perf_counter()
        target_url = f"{endpoint.rstrip('/')}/models"

        try:
            res = await self._get_from_gateway(target_url, headers, timeout)
            latency = round((time.perf_counter() - start_time) * 1000, 2)

            if res.status_code in (200, 204):
                data = res.json() if res.headers.get("content-type", "").startswith("application/json") else {}
                models_count = len(data.get("data", [])) if isinstance(data.get("data"), list) else 0
                return RouterHealthResponse(
                    status="connected",
                    endpoint=endpoint,
                    latency_ms=latency,
                    message="Koneksi ke 9Router gateway berhasil.",
                    authenticated=bool(api_key),
                    models_count=models_count,
                    fallback_status=fallback_status,
                )
            elif res.status_code == 401:
                return RouterHealthResponse(
                    status="unauthorized",
                    endpoint=endpoint,
                    latency_ms=latency,
                    message="API Key ditolak oleh 9Router (401 Unauthorized).",
                    authenticated=bool(api_key),
                    fallback_status=fallback_status,
                )
            else:
                return RouterHealthResponse(
                    status="error",
                    endpoint=endpoint,
                    latency_ms=latency,
                    message=f"9Router mengembalikan status HTTP {res.status_code}.",
                    authenticated=bool(api_key),
                    fallback_status=fallback_status,
                )
        except httpx.TimeoutException:
            latency = round((time.perf_counter() - start_time) * 1000, 2)
            return RouterHealthResponse(
                status="disconnected",
                endpoint=endpoint,
                latency_ms=latency,
                message=f"Timeout saat menghubungi 9Router di {endpoint} ({timeout}s).",
                authenticated=bool(api_key),
                fallback_status=fallback_status,
            )
        except Exception as e:
            latency = round((time.perf_counter() - start_time) * 1000, 2)
            return RouterHealthResponse(
                status="disconnected",
                endpoint=endpoint,
                latency_ms=latency,
                message=f"Tidak dapat menghubungi 9Router di {endpoint}: {str(e)}",
                authenticated=bool(api_key),
                fallback_status=fallback_status,
            )

    # =========================================================================
    # Model Discovery
    # =========================================================================

    async def discover_models(
        self, endpoint_override: Optional[str] = None
    ) -> RouterModelListResponse:
        """Discovers available models from the 9Router gateway or falls back to configured models."""
        ai_cfg = self.settings_service.get_ai_settings()
        saved_endpoint = (ai_cfg.router_endpoint or "").strip()
        endpoint = (endpoint_override or saved_endpoint).strip()

        # Prevent API key exfiltration: only attach stored credentials if endpoint matches saved configuration
        is_saved_endpoint = (endpoint.rstrip("/").lower() == saved_endpoint.rstrip("/").lower())
        api_key = CredentialService.get_secret(self.ROUTER_KEY_ID) if is_saved_endpoint else None

        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        if endpoint:
            try:
                validate_probe_url(endpoint)
                target_url = f"{endpoint.rstrip('/')}/models"
                res = await self._get_from_gateway(target_url, headers, timeout=15)
                if res.status_code == 200:
                    data = res.json()
                    raw_list = data.get("data", []) if isinstance(data, dict) else data
                    discovered: List[RouterModelItem] = []
                    for m in raw_list:
                        mid = m.get("id") if isinstance(m, dict) else str(m)
                        name = m.get("name") if isinstance(m, dict) and "name" in m else mid
                        supports_vis = "vision" in mid.lower() or "4o" in mid.lower()
                        discovered.append(
                            RouterModelItem(
                                id=mid,
                                name=name,
                                context_length=m.get("context_window", 128000) if isinstance(m, dict) else 128000,
                                provider=m.get("owned_by", "9Router") if isinstance(m, dict) else "9Router",
                                supports_vision=supports_vis,
                                is_default=(mid == ai_cfg.default_model),
                            )
                        )
                    if discovered:
                        return RouterModelListResponse(
                            models=discovered,
                            source="remote",
                            total_count=len(discovered),
                        )
            except Exception:
                # Silently fallback to standard configured models
                pass

        # Return fallback models
        models = [
            RouterModelItem(
                id=m.id,
                name=m.name,
                context_length=m.context_length,
                provider=m.provider,
                supports_vision=m.supports_vision,
                is_default=(m.id == ai_cfg.default_model),
            )
            for m in self.FALLBACK_MODELS
        ]
        return RouterModelListResponse(
            models=models,
            source="fallback",
            total_count=len(models),
        )

    # =========================================================================
    # Chat Completion & Generation
    # =========================================================================

    async def chat_completion(self, request: RouterChatRequest) -> RouterChatResponse:
        """Executes a chat completion against 9Router using OpenAI-compatible payload format,
        with automatic fallback to OpenRouter when 9Router fails or is unavailable.
        """
        ai_cfg = self.settings_service.get_ai_settings()
        endpoint = (ai_cfg.router_endpoint or "").strip()

        # If 9Router endpoint is missing, check if auto-fallback to OpenRouter is configured
        if not endpoint:
            if ai_cfg.auto_fallback_enabled:
                openrouter_key = CredentialService.get_secret(self.OPENROUTER_KEY_ID)
                if openrouter_key:
                    return await self._call_openrouter_fallback(
                        request, ai_cfg, openrouter_key, original_error="9Router endpoint belum dikonfigurasi"
                    )
            raise RouterException(
                "9Router endpoint belum dikonfigurasi. Silakan atur endpoint di Settings -> AI & Models."
            )

        model_name = (request.model or ai_cfg.default_model or "").strip()
        if not model_name:
            raise RouterException(
                "Tidak ada model AI yang dipilih atau dikonfigurasi. Silakan pilih model default di Settings -> AI & Models."
            )

        timeout = request.timeout_seconds or ai_cfg.router_timeout_seconds or 45
        api_key = CredentialService.get_secret(self.ROUTER_KEY_ID)

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        messages_payload = [{"role": m.role, "content": m.content} for m in request.messages]
        body: Dict[str, Any] = {
            "model": model_name,
            "messages": messages_payload,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        if request.json_mode:
            body["response_format"] = {"type": "json_object"}

        start_time = time.perf_counter()
        target_url = f"{endpoint.rstrip('/')}/chat/completions"

        error_to_fallback: Optional[str] = None
        max_retries = 2
        for attempt in range(max_retries):
            try:
                res = await self._post_to_gateway(target_url, headers, body, timeout)
                latency = round((time.perf_counter() - start_time) * 1000, 2)

                if res.status_code == 200:
                    data = res.json()
                    cid = data.get("id") or f"chatcmpl_{generate_uuid()[:8]}"
                    choice = data.get("choices", [{}])[0]
                    content = choice.get("message", {}).get("content", "")
                    finish_reason = choice.get("finish_reason", "stop")

                    raw_usage = data.get("usage", {})
                    usage = RouterTokenUsage(
                        prompt_tokens=raw_usage.get("prompt_tokens", 0),
                        completion_tokens=raw_usage.get("completion_tokens", 0),
                        total_tokens=raw_usage.get("total_tokens", 0),
                    )

                    parsed_json = None
                    if request.json_mode:
                        try:
                            parsed_json = json.loads(content)
                        except Exception:
                            parsed_json = None

                    self._record_audit_log(
                        action="9router_chat_completion",
                        model=model_name,
                        latency_ms=latency,
                        tokens=usage.total_tokens,
                    )

                    return RouterChatResponse(
                        id=cid,
                        model=model_name,
                        content=content,
                        finish_reason=finish_reason,
                        usage=usage,
                        latency_ms=latency,
                        parsed_json=parsed_json,
                        provider_used="9Router",
                        fallback_triggered=False,
                    )

                elif res.status_code in (502, 503, 504) and attempt < max_retries - 1:
                    await asyncio.sleep(0.2 * (attempt + 1))
                    continue
                elif res.status_code == 401:
                    error_to_fallback = "9Router API key ditolak (401 Unauthorized)."
                    break
                elif res.status_code == 403:
                    error_to_fallback = "Akses ke model atau endpoint ditolak oleh 9Router (403 Forbidden)."
                    break
                elif res.status_code == 404:
                    error_to_fallback = f"Model '{model_name}' atau endpoint tidak ditemukan di 9Router (404 Not Found)."
                    break
                elif res.status_code == 429:
                    error_to_fallback = "Batas kecepatan (rate limit) 9Router terlampaui (429 Too Many Requests)."
                    break
                else:
                    error_to_fallback = f"9Router mengembalikan status HTTP {res.status_code}."
                    break

            except httpx.TimeoutException:
                if attempt < max_retries - 1:
                    continue
                error_to_fallback = f"Permintaan ke 9Router melebihi batas waktu ({timeout} detik)."
                break
            except httpx.ConnectError as e:
                # If local mock environment
                if "127.0.0.1" in endpoint or "localhost" in endpoint:
                    latency = round((time.perf_counter() - start_time) * 1000, 2)
                    return self._generate_simulated_response(model_name, request, latency)
                error_to_fallback = f"Tidak dapat terhubung ke 9Router di {endpoint}: {str(e)}"
                break
            except asyncio.CancelledError:
                raise
            except Exception as e:
                error_to_fallback = f"Error saat menghubungi 9Router: {str(e)}"
                break

        # Fallback to OpenRouter if enabled and key is stored
        if error_to_fallback:
            if ai_cfg.auto_fallback_enabled:
                openrouter_key = CredentialService.get_secret(self.OPENROUTER_KEY_ID)
                if openrouter_key:
                    return await self._call_openrouter_fallback(
                        request, ai_cfg, openrouter_key, original_error=error_to_fallback
                    )
            raise RouterGatewayException(error_to_fallback)

        raise RouterGatewayException("Permintaan gagal tanpa respon.")

    async def _call_openrouter_fallback(
        self,
        request: RouterChatRequest,
        ai_cfg: Any,
        openrouter_key: str,
        original_error: str,
    ) -> RouterChatResponse:
        """Executes chat completion via OpenRouter when 9Router fails or is unreachable."""
        endpoint = (ai_cfg.openrouter_endpoint or "https://openrouter.ai/api/v1").strip()
        try:
            endpoint = validate_probe_url(endpoint)
        except ValueError as err:
            raise RouterGatewayException(f"Endpoint OpenRouter ditolak demi keamanan (SSRF): {str(err)}")
        model_name = (ai_cfg.openrouter_model or "google/gemini-2.5-flash").strip()
        if request.model and "/" in request.model:
            model_name = request.model.strip()

        timeout = request.timeout_seconds or ai_cfg.router_timeout_seconds or 45
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {openrouter_key}",
            "HTTP-Referer": "https://filenest.app",
            "X-Title": "FileNest Desktop",
        }
        messages_payload = [{"role": m.role, "content": m.content} for m in request.messages]
        body: Dict[str, Any] = {
            "model": model_name,
            "messages": messages_payload,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        if request.json_mode:
            body["response_format"] = {"type": "json_object"}

        start_time = time.perf_counter()
        target_url = f"{endpoint.rstrip('/')}/chat/completions"

        try:
            res = await self._post_to_gateway(target_url, headers, body, timeout)
            latency = round((time.perf_counter() - start_time) * 1000, 2)

            if res.status_code == 200:
                data = res.json()
                cid = data.get("id") or f"openrouter_{generate_uuid()[:8]}"
                choice = data.get("choices", [{}])[0]
                content = choice.get("message", {}).get("content", "")
                finish_reason = choice.get("finish_reason", "stop")

                raw_usage = data.get("usage", {})
                usage = RouterTokenUsage(
                    prompt_tokens=raw_usage.get("prompt_tokens", 0),
                    completion_tokens=raw_usage.get("completion_tokens", 0),
                    total_tokens=raw_usage.get("total_tokens", 0),
                )

                parsed_json = None
                if request.json_mode:
                    try:
                        parsed_json = json.loads(content)
                    except Exception:
                        parsed_json = None

                self._record_audit_log(
                    action="openrouter_fallback_chat_completion",
                    model=model_name,
                    latency_ms=latency,
                    tokens=usage.total_tokens,
                )

                return RouterChatResponse(
                    id=cid,
                    model=model_name,
                    content=content,
                    finish_reason=finish_reason,
                    usage=usage,
                    latency_ms=latency,
                    parsed_json=parsed_json,
                    provider_used=f"OpenRouter ({model_name})",
                    fallback_triggered=True,
                )
            else:
                raise RouterGatewayException(
                    f"9Router gagal ({original_error}) dan OpenRouter fallback juga gagal (HTTP {res.status_code}: {res.text[:120]})."
                )
        except httpx.TimeoutException:
            raise RouterGatewayException(
                f"9Router gagal ({original_error}) dan OpenRouter fallback melebihi batas waktu ({timeout} detik)."
            )
        except Exception as e:
            if isinstance(e, RouterGatewayException):
                raise
            raise RouterGatewayException(
                f"9Router gagal ({original_error}) dan OpenRouter fallback mengalami error: {str(e)}"
            )

    def _generate_simulated_response(
        self, model: str, request: RouterChatRequest, latency: float
    ) -> RouterChatResponse:
        """Deterministic offline mock when local 9Router service is not running."""
        last_message = request.messages[-1].content if request.messages else ""
        if request.json_mode:
            content = json.dumps({
                "status": "success",
                "simulated": True,
                "message": "9Router local simulated response",
                "analysis": "File structure evaluated cleanly.",
            })
            parsed_json = json.loads(content)
        else:
            content = f"9Router Gateway (Offline Simulation): Memproses permintaan untuk model {model}."
            parsed_json = None

        return RouterChatResponse(
            id=f"sim_{generate_uuid()[:8]}",
            model=model,
            content=content,
            finish_reason="stop",
            usage=RouterTokenUsage(prompt_tokens=50, completion_tokens=25, total_tokens=75),
            latency_ms=latency,
            parsed_json=parsed_json,
        )

    def _record_audit_log(
        self,
        action: str,
        model: str,
        latency_ms: float,
        tokens: int,
    ):
        """Records gateway usage in audit log without storing sensitive prompt content."""
        try:
            self.audit_repo.record(
                actor_type="ai",
                action=action,
                entity_type="model",
                entity_id=model,
                details={
                    "model": model,
                    "latency_ms": latency_ms,
                    "tokens_used": tokens,
                },
            )
        except Exception:
            pass
