"""
Diagnostic utility for MindVault AI Backend Gemini API integration.
Tests model availability and live generation without exposing API keys or secrets.
"""

import os
import sys
import time
import argparse
from typing import Optional, List
from dotenv import load_dotenv

# Ensure backend root is on Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def mask_key(key: Optional[str]) -> str:
    """Safely masks an API key, showing only whether it exists and its length."""
    if not key:
        return "<NOT_SET>"
    if len(key) <= 8:
        return f"[SET, length={len(key)}]"
    return f"{key[:4]}...{key[-4:]} (length={len(key)})"


def run_diagnostics(test_model: Optional[str] = None, list_all: bool = False, timeout_sec: float = 15.0):
    load_dotenv()

    api_key = os.getenv("GEMINI_API_KEY", "")
    configured_model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

    print("=" * 60)
    print("MindVault AI — Gemini API Live Diagnostics")
    print("=" * 60)
    print(f"Configured Model (GEMINI_MODEL): {configured_model}")
    print(f"API Key Status:                 {mask_key(api_key)}")
    print(f"Request Timeout:                {timeout_sec}s")
    print("=" * 60)

    if not api_key:
        print("[ERROR] GEMINI_API_KEY is not set in backend/.env.")
        return 1

    try:
        from google import genai
        from google.genai import types
        from google.genai import errors as genai_errors
    except ImportError as e:
        print(f"[ERROR] google-genai SDK is not installed or import failed: {e}")
        return 1

    timeout_ms = int(timeout_sec * 1000)
    client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=timeout_ms))

    # 1. Query available models
    print("\n[1/2] Querying available models from Gemini API...")
    available_models: List[str] = []
    try:
        models_pager = client.models.list()
        for m in models_pager:
            name = m.name or ""
            # Strip 'models/' prefix if present for clean comparison
            short_name = name.replace("models/", "")
            available_models.append(short_name)
        print(f"[OK] Successfully queried model registry. Found {len(available_models)} total models.")
    except Exception as e:
        print(f"[ERROR] Failed to query client.models.list(): {e}")
        return 1

    if list_all:
        print("\nAll Available Models:")
        for name in sorted(available_models):
            print(f"  - {name}")

    # 2. Test candidate models
    print("\n[2/2] Testing live generation requests (prompt: 'Respond with exactly: OK')...")
    
    # Priority list of models to test
    candidates_to_test = []
    if test_model:
        candidates_to_test.append(test_model)
    else:
        # Include configured model first, followed by known stable text generation models
        standard_models = [
            configured_model,
            "gemini-3.5-flash",
            "gemini-3.5-flash-lite",
            "gemini-3.8-flash",
            "gemini-4-argon",
            "gemini-2.5-flash",
            "gemini-1.5-flash",
        ]
        seen = set()
        for m in standard_models:
            if m not in seen:
                seen.add(m)
                candidates_to_test.append(m)

    results = []

    for model_name in candidates_to_test:
        in_registry = model_name in available_models
        print(f"\n--- Testing model: '{model_name}' (In registry: {in_registry}) ---")
        start_time = time.time()
        try:
            config = types.GenerateContentConfig(
                http_options=types.HttpOptions(timeout=timeout_ms)
            )
            response = client.models.generate_content(
                model=model_name,
                contents="Respond with exactly the single word: OK",
                config=config,
            )
            elapsed = time.time() - start_time
            text_output = (response.text or "").strip()
            print(f"  -> SUCCESS ({elapsed:.2f}s): {text_output[:80]}")
            results.append({"model": model_name, "status": "SUCCESS", "elapsed": elapsed, "output": text_output})
        except genai_errors.ClientError as e:
            elapsed = time.time() - start_time
            code = getattr(e, "code", 400)
            status_desc = getattr(e, "status", "CLIENT_ERROR")
            print(f"  -> CLIENT ERROR {code} ({status_desc}) ({elapsed:.2f}s): {str(e)[:150]}")
            results.append({"model": model_name, "status": f"CLIENT_ERROR_{code}", "elapsed": elapsed, "error": str(e)[:150]})
        except genai_errors.ServerError as e:
            elapsed = time.time() - start_time
            code = getattr(e, "code", 500)
            status_desc = getattr(e, "status", "SERVER_ERROR")
            print(f"  -> SERVER ERROR {code} ({status_desc}) ({elapsed:.2f}s): {str(e)[:150]}")
            results.append({"model": model_name, "status": f"SERVER_ERROR_{code}", "elapsed": elapsed, "error": str(e)[:150]})
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"  -> ERROR ({type(e).__name__}) ({elapsed:.2f}s): {str(e)[:150]}")
            results.append({"model": model_name, "status": type(e).__name__, "elapsed": elapsed, "error": str(e)[:150]})

    print("\n" + "=" * 60)
    print("Diagnostics Summary Table")
    print("=" * 60)
    working_models = []
    for r in results:
        status_str = r["status"]
        elapsed_str = f"{r['elapsed']:.2f}s"
        print(f"  * {r['model']:<25} | {status_str:<18} | {elapsed_str}")
        if status_str == "SUCCESS":
            working_models.append(r["model"])

    print("=" * 60)
    if working_models:
        print(f"[RECOMMENDATION] Working model(s) verified: {', '.join(working_models)}")
        if configured_model not in working_models:
            print(f"[ACTION RECOMMENDED] Set GEMINI_MODEL={working_models[0]} in backend/.env to resolve live failures.")
    else:
        print("[WARNING] No tested models succeeded live. Check API quota, rate limits, or network connectivity.")

    return 0 if working_models else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MindVault AI Gemini API Diagnostics")
    parser.add_argument("--model", type=str, default=None, help="Test a specific model ID")
    parser.add_argument("--list-all", action="store_true", help="Print all models available in registry")
    parser.add_argument("--timeout", type=float, default=15.0, help="Per-request timeout in seconds (default: 15.0)")
    args = parser.parse_args()

    sys.exit(run_diagnostics(test_model=args.model, list_all=args.list_all, timeout_sec=args.timeout))
