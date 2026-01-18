import datetime as _dt
import logging
import os
import threading
import time
from typing import Optional


def format_kv(**fields) -> str:
    """Format key/value fields for grep-friendly logs.

    Example:
        STAGE=MOODLE COURSE_ID=123 MSG="hello world"

    Notes:
    - Values with whitespace are quoted.
    - None values are omitted.
    """

    parts: list[str] = []
    for k, v in fields.items():
        if v is None:
            continue
        key = str(k).upper()
        if isinstance(v, bool):
            val = "true" if v else "false"
        else:
            val = str(v)

        if any(ch.isspace() for ch in val) or '"' in val:
            val = val.replace('"', "'")
            val = f'"{val}"'
        parts.append(f"{key}={val}")
    return " ".join(parts)


class RunContext:
    """Thread-safe shared state for a single ingestion run.

    This is used by:
    - the main ingestion logic (to update stage / counters / last entity)
    - the heartbeat thread (to log liveness even if the main thread hangs)
    """

    def __init__(self, run_id: str):
        self.run_id = run_id
        self._lock = threading.Lock()
        self._state: dict[str, object] = {
            "run_id": run_id,
            "stage": None,
            "stage_started_ts": None,
            "run_started_ts": time.time(),
            "last_checkpoint_ts": None,
            "last_course_id": None,
            "last_topic_id": None,
            "last_module_id": None,
            "last_module_type": None,
            "last_url": None,
            "counters": {},
        }

    def set_stage(self, stage: str) -> None:
        with self._lock:
            self._state["stage"] = stage
            self._state["stage_started_ts"] = time.time()

    def checkpoint(self) -> None:
        with self._lock:
            self._state["last_checkpoint_ts"] = time.time()

    def set_last(self, *, course_id=None, topic_id=None, module_id=None, module_type=None, url=None) -> None:
        with self._lock:
            if course_id is not None:
                self._state["last_course_id"] = course_id
            if topic_id is not None:
                self._state["last_topic_id"] = topic_id
            if module_id is not None:
                self._state["last_module_id"] = module_id
            if module_type is not None:
                self._state["last_module_type"] = module_type
            if url is not None:
                self._state["last_url"] = url

    def inc(self, counter: str, by: int = 1) -> None:
        with self._lock:
            counters: dict[str, int] = self._state["counters"]  # type: ignore[assignment]
            counters[counter] = int(counters.get(counter, 0)) + int(by)

    def set_counter(self, counter: str, value: int) -> None:
        with self._lock:
            counters: dict[str, int] = self._state["counters"]  # type: ignore[assignment]
            counters[counter] = int(value)

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            # Shallow copy, but make sure counters dict is copied too
            snap = dict(self._state)
            snap["counters"] = dict(self._state.get("counters", {}) or {})
            return snap


class StageTimer:
    """Context manager that logs STAGE start/end with duration."""

    def __init__(
        self,
        logger: logging.Logger,
        ctx: RunContext,
        stage: str,
        *,
        level: int = logging.INFO,
        extra_fields: Optional[dict] = None,
    ) -> None:
        self.logger = logger
        self.ctx = ctx
        self.stage = stage
        self.level = level
        self.extra_fields = extra_fields or {}
        self._t0: float | None = None

    def __enter__(self):
        self._t0 = time.time()
        self.ctx.set_stage(self.stage)
        self.ctx.checkpoint()
        self.logger.log(
            self.level,
            "CHECKPOINT %s",
            format_kv(RUN_ID=self.ctx.run_id, STAGE=self.stage, EVENT="START", **self.extra_fields),
        )
        return self

    def __exit__(self, exc_type, exc, tb):
        elapsed_s = None
        if self._t0 is not None:
            elapsed_s = round(time.time() - self._t0, 3)

        if exc is None:
            self.ctx.checkpoint()
            self.logger.log(
                self.level,
                "CHECKPOINT %s",
                format_kv(
                    RUN_ID=self.ctx.run_id,
                    STAGE=self.stage,
                    EVENT="END",
                    ELAPSED_S=elapsed_s,
                    **self.extra_fields,
                ),
            )
            return False

        # Exception path: log the exception once here; caller may also log.
        self.ctx.checkpoint()
        self.logger.exception(
            "CHECKPOINT %s",
            format_kv(
                RUN_ID=self.ctx.run_id,
                STAGE=self.stage,
                EVENT="FAILED",
                ELAPSED_S=elapsed_s,
                EXC_TYPE=getattr(exc_type, "__name__", str(exc_type)),
                **self.extra_fields,
            ),
        )
        return False


class Heartbeat:
    """Background heartbeat that logs liveness for a run.

    Important: this runs on a separate daemon thread so it can still emit log
    lines even if the ingestion main thread is blocked/hanging.
    """

    def __init__(
        self,
        logger: logging.Logger,
        ctx: RunContext,
        *,
        interval_seconds: Optional[int] = None,
    ) -> None:
        self.logger = logger
        self.ctx = ctx
        self.interval_seconds = interval_seconds or int(os.getenv("RUN_HEARTBEAT_SECONDS", "120"))
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name=f"heartbeat-{self.ctx.run_id}", daemon=True)
        self._thread.start()
        self.logger.info(
            "HEARTBEAT %s",
            format_kv(RUN_ID=self.ctx.run_id, EVENT="START", INTERVAL_S=self.interval_seconds),
        )

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        self.logger.info("HEARTBEAT %s", format_kv(RUN_ID=self.ctx.run_id, EVENT="STOP"))

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                snap = self.ctx.snapshot()
                counters = snap.get("counters", {}) or {}
                now = time.time()
                run_started = float(snap.get("run_started_ts") or now)
                elapsed_s = int(now - run_started)

                moodle_modules = None
                try:
                    moodle_modules = int(counters.get("moodle_modules_done"))  # type: ignore[arg-type]
                except Exception:
                    moodle_modules = None
                modules_per_min = None
                if moodle_modules is not None and elapsed_s > 0:
                    modules_per_min = round(moodle_modules / (elapsed_s / 60), 2)

                self.logger.info(
                    "HEARTBEAT %s",
                    format_kv(
                        RUN_ID=self.ctx.run_id,
                        STAGE=snap.get("stage"),
                        ELAPSED_S=elapsed_s,
                        LAST_CHECKPOINT_AGE_S=(
                            None
                            if not snap.get("last_checkpoint_ts")
                            else int(now - float(snap.get("last_checkpoint_ts") or now))
                        ),
                        LAST_COURSE_ID=snap.get("last_course_id"),
                        LAST_TOPIC_ID=snap.get("last_topic_id"),
                        LAST_MODULE_ID=snap.get("last_module_id"),
                        LAST_MODULE_TYPE=snap.get("last_module_type"),
                        LAST_URL=snap.get("last_url"),
                        MODULES_PER_MIN=modules_per_min,
                        **{f"CTR_{k}": v for k, v in counters.items()},
                    ),
                )
            except Exception:
                # Never crash ingestion because heartbeat/logging failed
                self.logger.exception("HEARTBEAT %s", format_kv(RUN_ID=self.ctx.run_id, EVENT="ERROR"))

            self._stop.wait(self.interval_seconds)


class Watchdog:
    """Logs warnings if a stage runs longer than a threshold.

    This is a best-effort hang indicator. It does NOT interrupt execution.
    """

    def __init__(
        self,
        logger: logging.Logger,
        ctx: RunContext,
        stage: str,
        *,
        threshold_seconds: int,
        repeat_seconds: int = 300,
    ) -> None:
        self.logger = logger
        self.ctx = ctx
        self.stage = stage
        self.threshold_seconds = threshold_seconds
        self.repeat_seconds = repeat_seconds
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._t0: Optional[float] = None

    def start(self) -> None:
        self._t0 = time.time()
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name=f"watchdog-{self.stage}-{self.ctx.run_id}", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    def _run(self) -> None:
        # Wait until threshold first
        if not self._t0:
            return
        if self._stop.wait(self.threshold_seconds):
            return

        while not self._stop.is_set():
            try:
                snap = self.ctx.snapshot()
                elapsed_s = int(time.time() - float(self._t0 or time.time()))
                self.logger.warning(
                    "WATCHDOG %s",
                    format_kv(
                        RUN_ID=self.ctx.run_id,
                        STAGE=self.stage,
                        THRESHOLD_S=self.threshold_seconds,
                        ELAPSED_S=elapsed_s,
                        LAST_COURSE_ID=snap.get("last_course_id"),
                        LAST_TOPIC_ID=snap.get("last_topic_id"),
                        LAST_MODULE_ID=snap.get("last_module_id"),
                        LAST_MODULE_TYPE=snap.get("last_module_type"),
                    ),
                )
            except Exception:
                self.logger.exception("WATCHDOG %s", format_kv(RUN_ID=self.ctx.run_id, STAGE=self.stage, EVENT="ERROR"))

            self._stop.wait(self.repeat_seconds)


def _parse_conn_str(conn_str: str) -> dict[str, str]:
    """Parse an Azure Storage connection string into a dict.

    Example pieces:
      DefaultEndpointsProtocol=https;AccountName=...;AccountKey=...;EndpointSuffix=core.windows.net
    """

    parts: dict[str, str] = {}
    for seg in conn_str.split(";"):
        if not seg.strip() or "=" not in seg:
            continue
        k, v = seg.split("=", 1)
        parts[k] = v
    return parts


def create_run_log_sas_url(
    run_id: str,
    *,
    expiry_hours: int = 24,
    logger_name: str = "loader",
) -> Optional[str]:
    """Create (if needed) an append blob for a run log and return a read-only SAS URL.

    This is designed for places where you want to expose a link early (e.g. in the
    HTTP starter) so the log can be read while being written.
    """

    logger = logging.getLogger(logger_name)
    conn = os.getenv("RUN_LOGS_BLOB_CONNECTION_STRING") or os.getenv("AzureWebJobsStorage")
    if not conn:
        logger.warning("No storage connection string available; cannot create run log SAS URL")
        return None

    container = os.getenv("RUN_LOGS_BLOB_CONTAINER", "dataloader-logs")
    prefix = os.getenv("RUN_LOGS_BLOB_PREFIX", "runs")
    blob_name = f"{prefix}/{run_id}.log"

    try:
        from azure.storage.blob import BlobServiceClient
        from azure.storage.blob._models import ContentSettings
        from azure.storage.blob import generate_blob_sas, BlobSasPermissions
    except Exception as e:
        logger.warning("azure-storage-blob not available (%s)", e)
        return None

    parts = _parse_conn_str(conn)
    account_name = parts.get("AccountName")
    account_key = parts.get("AccountKey")
    if not account_name or not account_key:
        logger.warning("Cannot create SAS URL: AccountName/AccountKey not found in connection string")
        return None

    bsc = BlobServiceClient.from_connection_string(conn)
    container_client = bsc.get_container_client(container)
    try:
        container_client.create_container()
    except Exception:
        pass

    blob_client = container_client.get_blob_client(blob_name)
    try:
        blob_client.create_append_blob(
            content_settings=ContentSettings(content_type="text/plain; charset=utf-8")
        )
    except Exception:
        pass

    sas = generate_blob_sas(
        account_name=account_name,
        container_name=container,
        blob_name=blob_name,
        account_key=account_key,
        permission=BlobSasPermissions(read=True),
        expiry=_dt.datetime.utcnow() + _dt.timedelta(hours=expiry_hours),
        start=_dt.datetime.utcnow() - _dt.timedelta(minutes=5),
    )
    return f"{blob_client.url}?{sas}"


class RunLogger:
    """A simple per-run logger that writes both to stdout and (optionally) to an
    Azure Append Blob so you can read logs while they are being generated.

    Why Append Blob?
    - it supports efficient appends
    - the blob is readable while we keep appending

    Configuration is via environment variables (suited for Function App settings):
    - RUN_LOGS_BLOB_CONNECTION_STRING (or use Azure identity + URL/SAS later)
    - RUN_LOGS_BLOB_CONTAINER (default: "dataloader-logs")
    - RUN_LOGS_BLOB_PREFIX (default: "runs")

    If not configured, it falls back to stdout-only.
    """

    def __init__(self, run_id: str, logger_name: str = "loader") -> None:
        self.run_id = run_id
        self.logger = logging.getLogger(logger_name)
        self._blob_handler: Optional[logging.Handler] = None
        self._container: Optional[str] = None
        self._blob_name: Optional[str] = None
        self._blob_url: Optional[str] = None
        self._storage_conn: Optional[str] = None

    @staticmethod
    def new_run_id() -> str:
        # Example: 20260114T152530Z-<pid>
        ts = _dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        return f"{ts}-{os.getpid()}"

    def attach_append_blob_handler(self) -> None:
        # Allow disabling blob logging explicitly (fallback remains stdout).
        if os.getenv("RUN_LOGS_BLOB_ENABLED", "true").lower() not in {"1", "true", "yes"}:
            self.logger.info("RUN_LOGS_BLOB_ENABLED=false -> stdout-only")
            return

        # Prefer a dedicated connection string, but fall back to the Function's
        # AzureWebJobsStorage if present (common in Azure Functions).
        conn = os.getenv("RUN_LOGS_BLOB_CONNECTION_STRING") or os.getenv("AzureWebJobsStorage")
        if not conn:
            self.logger.info(
                "No blob connection string available (RUN_LOGS_BLOB_CONNECTION_STRING/AzureWebJobsStorage) -> stdout-only"
            )
            return

        container = os.getenv("RUN_LOGS_BLOB_CONTAINER", "dataloader-logs")
        prefix = os.getenv("RUN_LOGS_BLOB_PREFIX", "runs")
        blob_name = f"{prefix}/{self.run_id}.log"

        try:
            from azure.storage.blob import BlobServiceClient
            from azure.storage.blob._models import ContentSettings
        except Exception as e:
            self.logger.warning("azure-storage-blob not available (%s) -> stdout-only", e)
            return

        # Lazy-create container + append blob
        bsc = BlobServiceClient.from_connection_string(conn)
        container_client = bsc.get_container_client(container)
        try:
            container_client.create_container()
        except Exception:
            # exists
            pass

        blob_client = container_client.get_blob_client(blob_name)

        # Create as Append Blob if not existing
        try:
            blob_client.create_append_blob(
                content_settings=ContentSettings(content_type="text/plain; charset=utf-8")
            )
        except Exception:
            # already exists
            pass

        # Buffer many log records into one append operation to avoid the 50k block
        # limit on Append Blobs.
        flush_bytes = int(os.getenv("RUN_LOGS_BLOB_FLUSH_BYTES", str(256 * 1024)))
        flush_seconds = float(os.getenv("RUN_LOGS_BLOB_FLUSH_SECONDS", "2"))
        max_buffer_bytes = int(os.getenv("RUN_LOGS_BLOB_MAX_BUFFER_BYTES", str(2 * 1024 * 1024)))

        self._blob_handler = _BufferedAppendBlobLoggingHandler(
            blob_client,
            flush_bytes=flush_bytes,
            flush_seconds=flush_seconds,
            max_buffer_bytes=max_buffer_bytes,
        )
        self._blob_handler.setLevel(logging.DEBUG)
        self._blob_handler.setFormatter(
            logging.Formatter(
                "{asctime} - {levelname:<8} - {message}",
                style="{",
                datefmt="%d-%b-%y %H:%M:%S",
            )
        )
        self.logger.addHandler(self._blob_handler)

        self._container = container
        self._blob_name = blob_name
        self._storage_conn = conn
        self._blob_url = blob_client.url

        self.logger.info("Run log will be appended to blob: %s/%s", container, blob_name)

    def get_readonly_sas_url(self, expiry_hours: int = 24) -> Optional[str]:
        """Return a read-only SAS URL for the current run log blob.

        This enables downloading/reading the blob without Azure RBAC in the client.
        Requires that the storage connection string contains an AccountKey.
        """

        if not self._storage_conn or not self._container or not self._blob_name or not self._blob_url:
            return None

        try:
            from azure.storage.blob import generate_blob_sas, BlobSasPermissions
        except Exception as e:
            self.logger.warning("azure-storage-blob SAS helpers not available (%s)", e)
            return None

        parts = _parse_conn_str(self._storage_conn)
        account_name = parts.get("AccountName")
        account_key = parts.get("AccountKey")
        if not account_name or not account_key:
            self.logger.warning("Cannot create SAS URL: AccountName/AccountKey not found in connection string")
            return None

        sas = generate_blob_sas(
            account_name=account_name,
            container_name=self._container,
            blob_name=self._blob_name,
            account_key=account_key,
            permission=BlobSasPermissions(read=True),
            expiry=_dt.datetime.utcnow() + _dt.timedelta(hours=expiry_hours),
            start=_dt.datetime.utcnow() - _dt.timedelta(minutes=5),
        )
        return f"{self._blob_url}?{sas}"

    def detach(self) -> None:
        if self._blob_handler:
            try:
                self.logger.removeHandler(self._blob_handler)
                self._blob_handler.close()
            except Exception:
                pass


class _AppendBlobLoggingHandler(logging.Handler):
    """Logging handler that appends each formatted log record as one append block."""

    def __init__(self, blob_client) -> None:
        super().__init__()
        self._blob_client = blob_client
        self._lock = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            data = (msg + "\n").encode("utf-8")
            with self._lock:
                # Append blobs support append_block
                self._blob_client.append_block(data)
        except Exception:
            # Never crash ingestion because logging failed
            self.handleError(record)


class _BufferedAppendBlobLoggingHandler(logging.Handler):
    """AppendBlob handler that batches many log records into fewer append blocks.

    Why:
    - Append blobs have a hard limit of 50,000 committed blocks.
    - Our previous handler appended *one block per log record*, which can hit the limit
      during long runs.

    Strategy:
    - buffer formatted log lines in memory
    - flush when either:
        * buffer size exceeds `flush_bytes`, or
        * `flush_seconds` elapsed since last flush
    - on close(): flush remaining
    - on Azure errors: disable itself (stop writing further) but never crash ingestion

    Notes:
    - Append blocks max size is ~4MB. Defaults keep buffer well below that.
    """

    def __init__(
        self,
        blob_client,
        *,
        flush_bytes: int = 256 * 1024,
        flush_seconds: float = 2.0,
        max_buffer_bytes: int = 2 * 1024 * 1024,
    ) -> None:
        super().__init__()
        self._blob_client = blob_client
        self._flush_bytes = max(4 * 1024, int(flush_bytes))
        self._flush_seconds = max(0.2, float(flush_seconds))
        self._max_buffer_bytes = max(self._flush_bytes, int(max_buffer_bytes))

        self._lock = threading.Lock()
        self._buf = bytearray()
        self._last_flush_ts = time.time()
        self._disabled = False

    def emit(self, record: logging.LogRecord) -> None:
        if self._disabled:
            return

        try:
            msg = self.format(record)
            data = (msg + "\n").encode("utf-8")
        except Exception:
            # If formatting fails, fall back to default error handling
            self.handleError(record)
            return

        try:
            with self._lock:
                # If buffer would become unreasonably large, flush first.
                if len(self._buf) + len(data) > self._max_buffer_bytes:
                    self._flush_locked()

                # If a single line is huge, write it alone.
                if len(data) > self._max_buffer_bytes:
                    self._append_bytes_locked(data)
                    return

                self._buf.extend(data)
                now = time.time()
                if len(self._buf) >= self._flush_bytes or (now - self._last_flush_ts) >= self._flush_seconds:
                    self._flush_locked(now=now)
        except Exception:
            # Never crash ingestion because logging failed
            self.handleError(record)

    def flush(self) -> None:
        if self._disabled:
            return
        try:
            with self._lock:
                self._flush_locked()
        except Exception:
            # Never crash ingestion
            return

    def close(self) -> None:
        try:
            self.flush()
        finally:
            super().close()

    def _flush_locked(self, *, now: float | None = None) -> None:
        if self._disabled:
            return
        if not self._buf:
            return

        payload = bytes(self._buf)
        self._buf.clear()
        self._append_bytes_locked(payload)
        self._last_flush_ts = now or time.time()

    def _append_bytes_locked(self, payload: bytes) -> None:
        if self._disabled:
            return
        try:
            self._blob_client.append_block(payload)
        except Exception:
            # Disable further blob writes to prevent repeated failures.
            self._disabled = True
