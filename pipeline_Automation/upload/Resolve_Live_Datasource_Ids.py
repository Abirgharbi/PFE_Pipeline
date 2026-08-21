"""Resolve live datasource IDs for one STM32Cube series directly from KB (kb-list).

Purpose:
- Keep upload runtime synchronized with KB state even when repo config IDs are stale.
- Return canonical datasource IDs for issues/files/diagnostic/resolver for a series.

Example:
    python pipeline_Automation/upload/Resolve_Live_Datasource_Ids.py \
      --kb 793 --series WB0 --remote-user first.last@st.com \
      --api-key <secret> --client-app-name mdrf_st_github_analyzer
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from Add_Data_Source_Files import (
    DEFAULT_ENDPOINT,
    DEFAULT_SERVICE,
    find_all_datasource_ids_by_name_from_kb_list,
    resolve_api_key,
    resolve_client_app_name,
    resolve_proxies,
    run_auth_precheck,
)


def _pick_best_id(ids: list[int]) -> int | None:
    if not ids:
        return None
    positive = [x for x in ids if isinstance(x, int) and x > 0]
    if not positive:
        return None
    return max(positive)


def _resolve_ids_for_name(
    endpoint: str,
    kb_id: int,
    datasource_name: str,
    api_key: str,
    client_app_name: str,
    service_name: str,
    remote_user: str | None,
    timeout_seconds: int,
    verify_ssl: bool,
    proxies: dict[str, str] | None,
    verbose: bool,
) -> list[int]:
    def fetch_with_scope(user_value: str | None) -> list[int]:
        response = run_auth_precheck(
            endpoint=endpoint,
            api_key=api_key,
            client_app_name=client_app_name,
            service_name=service_name,
            remote_user=user_value,
            timeout_seconds=timeout_seconds,
            verify_ssl=verify_ssl,
            proxies=proxies,
            verbose=verbose,
        )
        return find_all_datasource_ids_by_name_from_kb_list(response, kb_id, datasource_name)

    merged: set[int] = set()
    for candidate in fetch_with_scope(remote_user):
        if candidate > 0:
            merged.add(candidate)

    # Retry without remote_user scope: some environments return a broader/cleaner datasource view.
    if remote_user and str(remote_user).strip():
        for candidate in fetch_with_scope(None):
            if candidate > 0:
                merged.add(candidate)

    return sorted(merged)


def resolve_live_ids(
    endpoint: str,
    kb_id: int,
    series: str,
    api_key: str,
    client_app_name: str,
    service_name: str,
    remote_user: str | None,
    timeout_seconds: int,
    verify_ssl: bool,
    use_legacy_proxy: bool,
    verbose: bool,
) -> dict[str, Any]:
    proxies = resolve_proxies(use_legacy_proxy)
    series_upper = series.upper().strip()
    canonical_names = {
        "issues": f"DB_STready_{series_upper}_Issues",
        "files": f"DB_STready_{series_upper}_Files",
        "diagnostic": f"DB_STready_{series_upper}_Diagnostic",
        "resolver": f"DB_STready_{series_upper}_Resolver",
    }

    resolved: dict[str, int | None] = {}
    for key, name in canonical_names.items():
        ids = _resolve_ids_for_name(
            endpoint=endpoint,
            kb_id=kb_id,
            datasource_name=name,
            api_key=api_key,
            client_app_name=client_app_name,
            service_name=service_name,
            remote_user=remote_user,
            timeout_seconds=timeout_seconds,
            verify_ssl=verify_ssl,
            proxies=proxies,
            verbose=verbose,
        )
        resolved[key] = _pick_best_id(ids)

    # In component-only mode, monolithic issues datasource can be named issues_<SERIES>.
    if resolved.get("issues") is None:
        alt_name = f"issues_{series_upper}"
        alt_ids = _resolve_ids_for_name(
            endpoint=endpoint,
            kb_id=kb_id,
            datasource_name=alt_name,
            api_key=api_key,
            client_app_name=client_app_name,
            service_name=service_name,
            remote_user=remote_user,
            timeout_seconds=timeout_seconds,
            verify_ssl=verify_ssl,
            proxies=proxies,
            verbose=verbose,
        )
        resolved["issues"] = _pick_best_id(alt_ids)

    return {
        "series": series_upper,
        "kb": kb_id,
        "client_app_name": client_app_name,
        "resolved_ids": resolved,
        "resolved_names": canonical_names,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resolve live datasource IDs by canonical names from kb-list")
    parser.add_argument("--kb", type=int, required=True)
    parser.add_argument("--series", required=True, help="Series code, e.g. WB0")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--service", default=DEFAULT_SERVICE)
    parser.add_argument("--remote-user", default="")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--client-app-name", default="")
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--verify-ssl", action="store_true", default=False)
    parser.add_argument("--use-legacy-proxy", action="store_true", default=False)
    parser.add_argument("--verbose", action="store_true", default=False)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    api_key = resolve_api_key(args.api_key)
    client_app_name = resolve_client_app_name(args.client_app_name)
    remote_user = args.remote_user.strip() or None

    result = resolve_live_ids(
        endpoint=args.endpoint,
        kb_id=args.kb,
        series=args.series,
        api_key=api_key,
        client_app_name=client_app_name,
        service_name=args.service,
        remote_user=remote_user,
        timeout_seconds=args.timeout,
        verify_ssl=bool(args.verify_ssl),
        use_legacy_proxy=bool(args.use_legacy_proxy),
        verbose=bool(args.verbose),
    )
    print(json.dumps(result, ensure_ascii=True))


if __name__ == "__main__":
    main()
