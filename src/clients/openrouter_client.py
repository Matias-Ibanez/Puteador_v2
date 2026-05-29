import time
from typing import List, Union, Optional
import json
from pprint import pformat

from openai import OpenAI

from src import config


_client: Optional[OpenAI] = None


def init_client():
    global _client
    # Prefer NVIDIA Integrate if configured
    if config.NVIDIA_API_KEY:
        try:
            _client = OpenAI(base_url=config.NVIDIA_BASE_URL, api_key=config.NVIDIA_API_KEY)
            try:
                print(f"[client] using NVIDIA Integrate base_url={config.NVIDIA_BASE_URL}")
            except Exception:
                pass
            return _client
        except Exception:
            _client = None
            return None

    # Fallback to OpenRouter
    if not config.OPENROUTER_API_KEY:
        _client = None
        return None
    try:
        _client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=config.OPENROUTER_API_KEY)
        try:
            print("[client] using OpenRouter base_url=https://openrouter.ai/api/v1")
        except Exception:
            pass
        return _client
    except Exception:
        _client = None
        return None


def get_client():
    global _client
    if _client is None:
        init_client()
    return _client


def _extract_content_from_choice(choice) -> Optional[str]:
    # Support both dict-like and object-like responses
    if choice is None:
        return None
    # object-like: choice.message.content
    msg = getattr(choice, "message", None)
    if msg:
        if isinstance(msg, dict):
            return msg.get("content")
        return getattr(msg, "content", None)
    # dict-like choice: choice.get('message', {}).get('content')
    if isinstance(choice, dict):
        return choice.get("message", {}).get("content")
    return None


def _extract_status_from_completion(completion) -> Optional[int]:
    # Try to find an HTTP/status code on the completion object or dict
    keys = ("status", "status_code", "statusCode", "http_status")
    if isinstance(completion, dict):
        for k in keys:
            v = completion.get(k)
            if isinstance(v, int):
                return v
    for k in keys:
        v = getattr(completion, k, None)
        if isinstance(v, int):
            return v
    # Some SDKs embed a response object
    resp = getattr(completion, "_response", None) or getattr(completion, "response", None)
    if resp is not None:
        code = getattr(resp, "status_code", None) or getattr(resp, "status", None)
        if isinstance(code, int):
            return code
    return None


def _status_from_exception(exc) -> Optional[int]:
    # Attempt several common attribute names
    for attr in ("status_code", "http_status", "status", "code"):
        v = getattr(exc, attr, None)
        if isinstance(v, int):
            return v
        # sometimes the attribute is an object with status_code
        if hasattr(v, "status_code"):
            sc = getattr(v, "status_code")
            if isinstance(sc, int):
                return sc

    # httpx HTTPStatusError
    try:
        import httpx

        if isinstance(exc, httpx.HTTPStatusError):
            return exc.response.status_code
    except Exception:
        pass

    # openai/openrouter errors may have a .response attribute
    resp = getattr(exc, "response", None)
    if resp is not None:
        code = getattr(resp, "status_code", None) or getattr(resp, "status", None)
        if isinstance(code, int):
            return code

    return None


def _retry_after_seconds_from_exception(exc) -> Optional[float]:
    """Best-effort extraction of retry-after seconds for rate limit errors."""
    # OpenRouter / OpenAI style: exc.body.metadata.retry_after_seconds
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        md = body.get("metadata")
        if isinstance(md, dict):
            ras = md.get("retry_after_seconds")
            if isinstance(ras, (int, float)):
                return float(ras)
            headers = md.get("headers")
            if isinstance(headers, dict):
                ra = headers.get("Retry-After") or headers.get("retry-after")
                try:
                    if ra is not None:
                        return float(ra)
                except Exception:
                    pass

    # If there's a response object with headers
    resp = getattr(exc, "response", None)
    headers = getattr(resp, "headers", None) if resp is not None else None
    if headers is not None:
        try:
            ra = headers.get("Retry-After") or headers.get("retry-after")
            if ra is not None:
                return float(ra)
        except Exception:
            pass
    return None


def call_model_sync(
    payload: Union[str, List[dict]],
    model: str = config.MODEL_ID,
    attempts: int = 3,
    backoff: float = 1.0,
    temperature: Optional[float] = None,
) -> Optional[str]:
    """Call OpenRouter model synchronously with simple retry/backoff.

    payload may be a plain string or a list of messages.
    Returns the text content (str) or None if client not configured.
    Raises the last exception if attempts exhausted.
    """
    client = get_client()
    if client is None:
        # No API key configured
        raise RuntimeError("No NVIDIA_API_KEY or OPENROUTER_API_KEY configured")

    if isinstance(payload, str):
        messages = [{"role": "user", "content": payload}]
    else:
        messages = payload

    last_exc = None
    for i in range(attempts):
        try:
            # log the outgoing request (minimal, no secrets)
            base_url = getattr(client, "base_url", None)
            # Best-effort: show the actual endpoint derived from base_url
            endpoint_url = None
            try:
                endpoint_url = str(base_url).rstrip("/") + "/chat/completions"
            except Exception:
                endpoint_url = "(unknown)/chat/completions"
            if model != config.MODEL_ID:
                print(f"[openrouter_client] WARNING: model override={model} (default={config.MODEL_ID})")

            print("\n" + "=" * 88)
            print(f"[openrouter_client] POST {endpoint_url} (sdk base_url={base_url})")
            print(
                f"[openrouter_client] model={model} attempt={i+1}/{attempts} "
                f"temperature={temperature if temperature is not None else getattr(config, 'MODEL_TEMPERATURE', None)}"
            )
            print("[openrouter_client] request.messages:")
            try:
                print(pformat(messages, width=120))
            except Exception:
                print("(unprintable messages)")
            print("=" * 88)

            if temperature is None:
                temperature = getattr(config, "MODEL_TEMPERATURE", None)

            create_kwargs = {"model": model, "messages": messages}
            if isinstance(temperature, (int, float)):
                create_kwargs["temperature"] = float(temperature)

            completion = client.chat.completions.create(**create_kwargs)

            # log the full response (pretty-printed when possible)
            resp_obj = getattr(completion, "_response", None) or getattr(completion, "response", None)
            status_hint = _extract_status_from_completion(completion)
            resp_status = getattr(resp_obj, "status_code", None) or getattr(resp_obj, "status", None)
            print(f"[openrouter_client] response.status (hint)={status_hint} (resp)={resp_status}")

            # Try to convert completion to a dict for printing
            completion_dict = None
            if isinstance(completion, dict):
                completion_dict = completion
            else:
                md = getattr(completion, "model_dump", None)
                if callable(md):
                    try:
                        completion_dict = md()
                    except Exception:
                        completion_dict = None
                if completion_dict is None:
                    td = getattr(completion, "to_dict", None)
                    if callable(td):
                        try:
                            completion_dict = td()
                        except Exception:
                            completion_dict = None
                if completion_dict is None:
                    try:
                        completion_dict = vars(completion)
                    except Exception:
                        completion_dict = None

            if completion_dict is not None:
                # Pretty JSON for readability; limit to avoid exploding logs
                try:
                    txt = json.dumps(completion_dict, indent=2, ensure_ascii=False)
                except Exception:
                    txt = pformat(completion_dict, width=120)
                if len(txt) > 40000:
                    print("[openrouter_client] response (truncated to 40000 chars):")
                    print(txt[:40000])
                else:
                    print("[openrouter_client] response:")
                    print(txt)
            else:
                rep = repr(completion)
                print("[openrouter_client] response repr (truncated to 8000 chars):")
                print(rep[:8000])

            print("=" * 88)

            # fallback: try to detect http status and if it's not 200 return "puto"
            status = _extract_status_from_completion(completion)
            if status is not None and status != 200:
                print(f"[openrouter_client] non-200 status detected ({status}); returning fallback 'puto'")
                return "puto"

            choice = None
            # Extract content from all choices (if provider returns multiple)
            contents = []
            if hasattr(completion, "choices") and completion.choices:
                for c in completion.choices:
                    cont = _extract_content_from_choice(c)
                    if cont and isinstance(cont, str):
                        cont = cont.strip()
                        if cont:
                            contents.append(cont)
            elif isinstance(completion, dict):
                choices = completion.get("choices") or []
                for c in choices:
                    cont = _extract_content_from_choice(c)
                    if cont and isinstance(cont, str):
                        cont = cont.strip()
                        if cont:
                            contents.append(cont)

            if not contents:
                return None
            if len(contents) == 1:
                return contents[0]

            # Multiple choices: join with a delimiter so callers can split and queue.
            return "\n\n---CHOICE---\n\n".join(contents)
        except Exception as e:
            # check exception for status
            st = _status_from_exception(e)
            if st is not None and st != 200:
                # If we're rate-limited (429), respect Retry-After and retry.
                if st == 429:
                    retry_after = _retry_after_seconds_from_exception(e)
                    # If this was the last attempt, return fallback.
                    if i >= attempts - 1:
                        try:
                            print("[openrouter_client] rate-limited on last attempt; returning fallback 'puto'")
                        except Exception:
                            pass
                        return "puto"

                    # Sleep (in this blocking function) before retrying.
                    sleep_for = float(retry_after) if retry_after is not None else (backoff * (2 ** i))
                    try:
                        print(f"[openrouter_client] rate-limited (429). retry_after={retry_after}; sleeping {sleep_for:.2f}s then retrying")
                    except Exception:
                        pass
                    time.sleep(max(0.0, sleep_for))
                    last_exc = e
                    continue

                try:
                    print("\n" + "=" * 88)
                    print(f"[openrouter_client] exception with non-200 status={st}; returning fallback 'puto'")
                    print(f"[openrouter_client] exception type={type(e)}")
                    print(f"[openrouter_client] exception repr={repr(e)[:8000]}")
                    resp = getattr(e, "response", None)
                    if resp is not None:
                        rs = getattr(resp, "status_code", None) or getattr(resp, "status", None)
                        txt = getattr(resp, "text", None)
                        print(f"[openrouter_client] exception.response.status={rs}")
                        if txt:
                            print("[openrouter_client] exception.response.text (truncated to 8000 chars):")
                            print(str(txt)[:8000])
                    body = getattr(e, "body", None)
                    if body is not None:
                        try:
                            print("[openrouter_client] exception.body:")
                            print(pformat(body, width=120))
                        except Exception:
                            pass
                    print("=" * 88)
                except Exception:
                    pass
                return "puto"

            last_exc = e
            sleep_for = backoff * (2 ** i)
            try:
                print(f"[openrouter_client] attempt={i+1} failed: {type(e)} {repr(e)[:300]}")
                print(f"[openrouter_client] retrying after {sleep_for:.2f}s")
            except Exception:
                pass
            time.sleep(sleep_for)
    raise last_exc
