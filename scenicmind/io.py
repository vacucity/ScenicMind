from __future__ import annotations

import hashlib
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

USER_AGENT = "JiuzhaigouResearchDataset/0.1 (+non-commercial academic data engineering; low-frequency cached requests)"


def session() -> requests.Session:
    s = requests.Session()
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7"})
    return s


def cached_get(
    url: str,
    raw_path: Path,
    *,
    refresh: bool = False,
    pause_seconds: float = 0.12,
    timeout: int = 30,
) -> bytes:
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path = raw_path.with_suffix(raw_path.suffix + ".meta.json")
    if raw_path.exists() and not refresh:
        return raw_path.read_bytes()
    status_code = 200
    content_type = None
    try:
        response = session().get(url, timeout=timeout)
        response.raise_for_status()
        payload = response.content
        status_code = response.status_code
        content_type = response.headers.get("content-type")
    except requests.RequestException:
        # Some Windows/Python TLS stacks terminate Open-Meteo handshakes early.
        # curl is used only as a standards-compliant fallback; the same cache and
        # provenance metadata are still written.
        completed = subprocess.run(
            [
                "curl.exe",
                "--http1.1",
                "-L",
                "--fail",
                "--silent",
                "--show-error",
                "--max-time",
                str(timeout),
                url,
            ],
            check=True,
            capture_output=True,
        )
        payload = completed.stdout
        status_code = 200
    raw_path.write_bytes(payload)
    meta = {
        "url": url,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "http_status": status_code,
        "content_type": content_type,
        "sha256": hashlib.sha256(payload).hexdigest(),
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    if pause_seconds:
        time.sleep(pause_seconds)
    return payload


def read_yaml(path: Path) -> dict:
    import yaml

    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def write_parquet_and_csv(df, parquet_path: Path, csv_path: Path | None = None) -> None:
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(parquet_path, index=False)
    if csv_path is not None:
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
