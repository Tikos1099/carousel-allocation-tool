
from __future__ import annotations

import json
import os
import re
import shutil
import uuid

from dotenv import load_dotenv
load_dotenv(".env.local")   # charge les variables locales pour le backend Python
from dataclasses import dataclass, field
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import numpy as np
import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, validator

from allocator import CarouselCapacity, allocate_round_robin, allocate_round_robin_with_rules
from app_heatmap import _build_heatmap_sheets
from app_mapping import _apply_cat_term_mapping, _guess_col
from app_readjust import _build_extra_terms_and_defaults
from io_excel import write_heatmap_excel, write_summary_csv, write_summary_txt, write_timeline_excel
from baglist_expr import eval_expression as eval_baglist_expression


class ColumnMapping(BaseModel):
    departure_time: str = Field(..., description="Raw column for DepartureTime")
    flight_number: str = Field(..., description="Raw column for FlightNumber")
    category: str = Field(..., description="Raw column for Category")
    positions: str = Field(..., description="Raw column for Positions")
    terminal: Optional[str] = Field(None, description="Raw column for Terminal")
    makeup_opening: Optional[str] = Field(None, description="Raw column for MakeupOpening")
    makeup_closing: Optional[str] = Field(None, description="Raw column for MakeupClosing")
    keep_extra_cols: List[str] = Field(default_factory=list)


class CategoryTerminalMapping(BaseModel):
    categories: Dict[str, str] = Field(default_factory=dict)
    terminals: Dict[str, str] = Field(default_factory=dict)


class MakeupConfig(BaseModel):
    mode: Literal["columns", "compute"] = "columns"
    wide_open_min: int = 120
    wide_close_min: int = 60
    narrow_open_min: int = 90
    narrow_close_min: int = 45

    @validator("wide_open_min", "wide_close_min", "narrow_open_min", "narrow_close_min")
    def _non_negative(cls, v: int) -> int:
        return max(0, int(v))


class CarouselCap(BaseModel):
    wide: int = 0
    narrow: int = 0

    @validator("wide", "narrow")
    def _non_negative(cls, v: int) -> int:
        return max(0, int(v))


class CarouselsConfig(BaseModel):
    mode: Literal["manual", "file"] = "manual"
    manual: Dict[str, CarouselCap] = Field(default_factory=dict)
    by_terminal: Dict[str, Dict[str, CarouselCap]] = Field(default_factory=dict)


class RulesConfig(BaseModel):
    apply_readjustment: bool = True
    rule_multi: bool = True
    rule_narrow_wide: bool = False
    rule_extras: bool = True
    wide_can_use_narrow: bool = True
    max_carousels_narrow: int = 3
    max_carousels_wide: int = 2
    rule_order: List[Literal["multi", "narrow_wide", "extras"]] = Field(default_factory=list)

    @validator("max_carousels_narrow", "max_carousels_wide")
    def _positive(cls, v: int) -> int:
        return max(1, int(v))


class ExtrasConfig(BaseModel):
    by_terminal: Dict[str, CarouselCap] = Field(default_factory=dict)


class ColorsConfig(BaseModel):
    color_mode: Literal["category", "terminal", "flight"] = "category"
    wide_color: str = "#D32F2F"
    narrow_color: str = "#FFEBEE"
    split_color: str = "#FFC107"
    narrow_wide_color: str = "#00B894"


class RunConfig(BaseModel):
    columns: ColumnMapping
    mapping: CategoryTerminalMapping
    makeup: MakeupConfig = MakeupConfig()
    time_step_minutes: int = 5
    carousels: CarouselsConfig
    rules: RulesConfig = RulesConfig()
    extras: ExtrasConfig = ExtrasConfig()
    colors: ColorsConfig = ColorsConfig()

    @validator("time_step_minutes")
    def _time_step_positive(cls, v: int) -> int:
        v = int(v)
        if v <= 0:
            raise ValueError("time_step_minutes must be > 0")
        return v


class SessionStatePayload(BaseModel):
    current_step: Optional[int] = None
    wizard_state: Dict[str, object] = Field(default_factory=dict)


@dataclass
class JobRecord:
    job_id: str
    status: Literal["queued", "running", "done", "error"]
    created_at: str
    finished_at: Optional[str] = None
    scenario_name: Optional[str] = None
    storage_size_bytes: int = 0
    kpis: Dict[str, object] = field(default_factory=dict)
    analytics: Dict[str, object] = field(default_factory=dict)
    warnings: List[Dict[str, object]] = field(default_factory=list)
    downloads: Dict[str, str] = field(default_factory=dict)
    tables: Dict[str, object] = field(default_factory=dict)
    error: Optional[str] = None
    job_dir: Optional[Path] = None


@dataclass
class SessionRecord:
    session_id: str
    wizard_state: Dict[str, object] = field(default_factory=dict)
    current_step: int = 1
    last_job_id: Optional[str] = None
    file_path: Optional[str] = None
    file_meta: Dict[str, object] = field(default_factory=dict)
    updated_at: str = ""


class BaglistJoinConfig(BaseModel):
    left_key: Optional[str] = None
    right_key: Optional[str] = None
    strategy: Literal["first", "error"] = "first"

    class Config:
        extra = "ignore"


class BaglistColumnConfig(BaseModel):
    output_column: str
    type: Literal["copy", "const", "lookup", "formula", "format"]
    source: Optional[Literal["bags", "allocation", "transfers"]] = "bags"
    field: Optional[str] = None
    value: Optional[object] = None
    expression: Optional[str] = None
    join: Optional[BaglistJoinConfig] = None
    default: Optional[object] = None
    format: Optional[str] = None
    cast: Optional[Literal["datetime", "date", "time", "number", "int", "text", "bool", "minutes"]] = None

    class Config:
        extra = "ignore"


class BaglistConfig(BaseModel):
    columns: List[BaglistColumnConfig]

    class Config:
        extra = "ignore"


@dataclass
class BaglistJobRecord:
    job_id: str
    status: Literal["queued", "running", "done", "error"]
    created_at: str
    finished_at: Optional[str] = None
    kpis: Dict[str, object] = field(default_factory=dict)
    warnings: List[Dict[str, object]] = field(default_factory=list)
    preview_rows: List[Dict[str, object]] = field(default_factory=list)
    downloads: Dict[str, str] = field(default_factory=dict)
    error: Optional[str] = None
    job_dir: Optional[Path] = None


@dataclass
class CustomKPI:
    kpi_id: str
    name: str
    metric: str          # e.g. "assigned_pct", "unassigned_count", …
    display_type: str    # "percentage" | "counter" | "text"
    description: str = ""
    alert_enabled: bool = False
    alert_operator: str = "lt"   # "lt" | "gt"
    alert_threshold: float = 0.0
    created_at: str = ""


class CustomKPIPayload(BaseModel):
    name: str
    metric: str
    display_type: str
    description: str = ""
    alert_enabled: bool = False
    alert_operator: str = "lt"
    alert_threshold: float = 0.0

    class Config:
        extra = "ignore"


ROOT_DIR = Path(__file__).resolve().parent
STORAGE_DIR = ROOT_DIR / "storage"
JOBS_DIR = STORAGE_DIR / "jobs"
SESSIONS_DIR = STORAGE_DIR / "sessions"
FRONTEND_DIR = ROOT_DIR / "frontend"
CUSTOM_KPI_FILE = STORAGE_DIR / "custom_kpis.json"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
JOBS_DIR.mkdir(parents=True, exist_ok=True)
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

# ── Supabase client ────────────────────────────────────────────────────────
_supabase_client = None

def _get_supabase():
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client
    url = (os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL", "")).strip()
    # Priorité : service_role key → anon key (RLS désactivé = anon key suffit)
    key = os.getenv("SUPABASE_KEY", "").strip()
    if not key or key.startswith("<"):
        key = os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "").strip()
    if url and key:
        try:
            from supabase import create_client
            _supabase_client = create_client(url, key)
        except Exception:
            pass
    return _supabase_client

app = FastAPI(title="Carousel Allocation API", version="1.0")

ALLOWED_ORIGINS = [
    "https://carousel-allocation-tool.vercel.app",
    "http://localhost:3000",
]
ALLOWED_ORIGIN_REGEX = r"https://.*\.vercel\.app"

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=ALLOWED_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

JOB_STORE: Dict[str, JobRecord] = {}
SESSION_STORE: Dict[str, SessionRecord] = {}
BAGLIST_JOB_STORE: Dict[str, BaglistJobRecord] = {}
CUSTOM_KPI_STORE: Dict[str, CustomKPI] = {}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Disk persistence helpers ────────────────────────────────────────────────

def _job_to_dict(record: JobRecord) -> dict:
    return {
        "job_id": record.job_id,
        "scenario_name": record.scenario_name,
        "status": record.status,
        "created_at": record.created_at,
        "finished_at": record.finished_at,
        "storage_size_bytes": record.storage_size_bytes,
        "kpis": record.kpis,
        "analytics": record.analytics,
        "warnings": record.warnings,
        "downloads": record.downloads,
        "tables": record.tables,
        "error": record.error,
    }


def _compute_job_storage_size(job_dir: Optional[Path]) -> int:
    if not job_dir or not job_dir.exists():
        return 0
    return sum(f.stat().st_size for f in job_dir.iterdir() if f.is_file())


def _save_job_to_supabase(record: JobRecord) -> None:
    sb = _get_supabase()
    if not sb:
        return
    try:
        size = _compute_job_storage_size(record.job_dir)
        record.storage_size_bytes = size
        sb.table("jobs").upsert({
            "job_id": record.job_id,
            "scenario_name": record.scenario_name,
            "status": record.status,
            "created_at": record.created_at,
            "finished_at": record.finished_at,
            "kpis": record.kpis,
            "analytics": record.analytics,
            "warnings": record.warnings,
            "downloads": record.downloads,
            "tables_data": record.tables,
            "error": record.error,
            "storage_size_bytes": size,
        }).execute()
    except Exception:
        pass


def _load_jobs_from_supabase() -> None:
    sb = _get_supabase()
    if not sb:
        return
    try:
        response = sb.table("jobs").select("*").execute()
        for row in response.data:
            job_id = row["job_id"]
            job_dir = JOBS_DIR / job_id
            record = JobRecord(
                job_id=job_id,
                scenario_name=row.get("scenario_name"),
                status=row.get("status", "done"),
                created_at=row.get("created_at", ""),
                finished_at=row.get("finished_at"),
                kpis=row.get("kpis") or {},
                analytics=row.get("analytics") or {},
                warnings=row.get("warnings") or [],
                downloads=row.get("downloads") or {},
                tables=row.get("tables_data") or {},
                error=row.get("error"),
                storage_size_bytes=row.get("storage_size_bytes") or 0,
                job_dir=job_dir if job_dir.exists() else None,
            )
            JOB_STORE[record.job_id] = record
    except Exception:
        pass


def _save_job_to_disk(record: JobRecord) -> None:
    if not record.job_dir:
        return
    try:
        meta_path = record.job_dir / "job.json"
        with open(meta_path, "w", encoding="utf-8") as fh:
            json.dump(_job_to_dict(record), fh, ensure_ascii=False, default=str)
    except Exception:
        pass
    _save_job_to_supabase(record)


def _load_jobs_from_disk() -> None:
    for job_dir in sorted(JOBS_DIR.iterdir()):
        if not job_dir.is_dir():
            continue
        meta_path = job_dir / "job.json"
        if not meta_path.exists():
            continue
        try:
            with open(meta_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            record = JobRecord(
                job_id=data["job_id"],
                scenario_name=data.get("scenario_name"),
                status=data.get("status", "done"),
                created_at=data.get("created_at", ""),
                finished_at=data.get("finished_at"),
                storage_size_bytes=data.get("storage_size_bytes", 0),
                kpis=data.get("kpis", {}),
                analytics=data.get("analytics", {}),
                warnings=data.get("warnings", []),
                downloads=data.get("downloads", {}),
                tables=data.get("tables", {}),
                error=data.get("error"),
                job_dir=job_dir,
            )
            JOB_STORE[record.job_id] = record
        except Exception:
            pass


def _save_session_to_disk(record: SessionRecord) -> None:
    try:
        session_path = SESSIONS_DIR / f"{record.session_id}.json"
        data = {
            "session_id": record.session_id,
            "wizard_state": record.wizard_state,
            "current_step": record.current_step,
            "last_job_id": record.last_job_id,
            "file_meta": record.file_meta,
            "updated_at": record.updated_at,
        }
        with open(session_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, default=str)
    except Exception:
        pass


def _load_sessions_from_disk() -> None:
    for session_file in SESSIONS_DIR.glob("*.json"):
        try:
            with open(session_file, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            record = SessionRecord(
                session_id=data["session_id"],
                wizard_state=data.get("wizard_state", {}),
                current_step=data.get("current_step", 1),
                last_job_id=data.get("last_job_id"),
                file_meta=data.get("file_meta", {}),
                updated_at=data.get("updated_at", ""),
            )
            SESSION_STORE[record.session_id] = record
        except Exception:
            pass


def _save_custom_kpis_to_disk() -> None:
    try:
        data = [
            {
                "kpi_id": k.kpi_id,
                "name": k.name,
                "metric": k.metric,
                "display_type": k.display_type,
                "description": k.description,
                "alert_enabled": k.alert_enabled,
                "alert_operator": k.alert_operator,
                "alert_threshold": k.alert_threshold,
                "created_at": k.created_at,
            }
            for k in CUSTOM_KPI_STORE.values()
        ]
        with open(CUSTOM_KPI_FILE, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False)
    except Exception:
        pass


def _load_custom_kpis_from_disk() -> None:
    if not CUSTOM_KPI_FILE.exists():
        return
    try:
        with open(CUSTOM_KPI_FILE, "r", encoding="utf-8") as fh:
            items = json.load(fh)
        for item in items:
            kpi = CustomKPI(
                kpi_id=item["kpi_id"],
                name=item["name"],
                metric=item["metric"],
                display_type=item.get("display_type", "counter"),
                description=item.get("description", ""),
                alert_enabled=item.get("alert_enabled", False),
                alert_operator=item.get("alert_operator", "lt"),
                alert_threshold=float(item.get("alert_threshold", 0.0)),
                created_at=item.get("created_at", ""),
            )
            CUSTOM_KPI_STORE[kpi.kpi_id] = kpi
    except Exception:
        pass


def _migrate_jobs_to_supabase() -> None:
    """Push all jobs loaded from disk into Supabase (runs once on startup)."""
    sb = _get_supabase()
    if not sb:
        return
    try:
        existing = {row["job_id"] for row in sb.table("jobs").select("job_id").execute().data}
        for record in list(JOB_STORE.values()):
            if record.job_id not in existing and record.status == "done":
                _save_job_to_supabase(record)
    except Exception:
        pass


_load_jobs_from_disk()
_migrate_jobs_to_supabase()       # pousse les jobs du disque vers Supabase si absents
_load_jobs_from_supabase()        # Supabase override (a scenario_name, storage_size_bytes)
_load_sessions_from_disk()
_load_custom_kpis_from_disk()


def _get_session_id(request: Request) -> str:
    session_id = request.headers.get("x-session-id")
    if session_id:
        return session_id
    return str(uuid.uuid4())


def _ensure_session(session_id: str) -> SessionRecord:
    record = SESSION_STORE.get(session_id)
    if not record:
        record = SessionRecord(session_id=session_id, updated_at=_utc_now())
        SESSION_STORE[session_id] = record
    return record


def _touch_session(record: SessionRecord) -> None:
    record.updated_at = _utc_now()


def _save_session_file(session_id: str, upload: UploadFile) -> Path:
    session_dir = SESSIONS_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    filename = Path(upload.filename or "input.xlsx").name
    dest_path = session_dir / filename
    with dest_path.open("wb") as out_file:
        shutil.copyfileobj(upload.file, out_file)
    upload.file.seek(0)
    record = _ensure_session(session_id)
    record.file_path = str(dest_path)
    record.file_meta = {"name": filename, "size": dest_path.stat().st_size}
    _touch_session(record)
    return dest_path


def _get_session_file_path(record: SessionRecord) -> Optional[Path]:
    if not record.file_path:
        return None
    path = Path(record.file_path)
    if not path.exists():
        return None
    return path


def _read_excel_path(path: Path, *, nrows: Optional[int] = None) -> pd.DataFrame:
    try:
        filename = path.name.lower()
        if filename.endswith(".csv"):
            content = path.read_bytes()
            return _read_csv_auto(content, nrows=nrows)
        if filename.endswith(".xls"):
            try:
                return pd.read_excel(path, engine="xlrd", nrows=nrows)
            except Exception as exc:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Unable to read .xls file. "
                        "Please convert to .xlsx or install xlrd. "
                        f"Details: {exc}"
                    ),
                )
        return pd.read_excel(path, engine="openpyxl", nrows=nrows)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Unable to read Excel file: {exc}")

def _clean_mapping_value(value: object) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.lower() in ("default", "none", "null", "nan"):
        return None
    return text


def _normalize_mapping_value(value: object, *, kind: Literal["category", "terminal"]) -> str:
    if value is None:
        return "IGNORER"
    text = str(value).strip()
    if not text:
        return "IGNORER"
    lower = text.lower()
    if lower in ("ignore", "ignorer", "ignored", "none", "null", "nan"):
        return "IGNORER"
    if kind == "category":
        if lower in ("wide", "w", "wide body", "widebody", "wb"):
            return "Wide"
        if lower in ("narrow", "n", "narrow body", "narrowbody", "nb"):
            return "Narrow"
    if kind == "terminal":
        return text.strip().upper()
    return text


def _normalize_mapping_values(
    mapping: Dict[object, object] | None,
    *,
    kind: Literal["category", "terminal"],
) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for key, value in (mapping or {}).items():
        key_text = str(key).strip()
        if not key_text:
            continue
        if kind == "terminal":
            key_text = key_text.upper()
        out[key_text] = _normalize_mapping_value(value, kind=kind)
    return out


def _parse_columns_payload(payload: Dict[str, object]) -> ColumnMapping:
    if "columns" in payload:
        return ColumnMapping.parse_obj(payload.get("columns") or {})

    mapping = None
    if "mapping" in payload and isinstance(payload.get("mapping"), dict):
        mapping = payload.get("mapping") or {}
    else:
        keys = {"DepartureTime", "FlightNumber", "Category", "Positions"}
        if any(k in payload for k in keys):
            mapping = payload

    if not isinstance(mapping, dict):
        raise HTTPException(status_code=400, detail="Missing columns mapping for inspect")

    return ColumnMapping(
        departure_time=_clean_mapping_value(mapping.get("DepartureTime")),
        flight_number=_clean_mapping_value(mapping.get("FlightNumber")),
        category=_clean_mapping_value(mapping.get("Category")),
        positions=_clean_mapping_value(mapping.get("Positions")),
        terminal=_clean_mapping_value(mapping.get("Terminal")),
        makeup_opening=_clean_mapping_value(mapping.get("MakeupOpening")),
        makeup_closing=_clean_mapping_value(mapping.get("MakeupClosing")),
    )


def _parse_makeup_config_v1(payload: Dict[str, object]) -> MakeupConfig:
    mode_raw = str(payload.get("makeup_time_mode") or "").strip().lower()
    mode = "columns"
    if mode_raw in ("offsets", "compute"):
        mode = "compute"

    offsets = payload.get("offsets_minutes") or {}
    wide_offsets = offsets.get("Wide") or offsets.get("wide") or {}
    narrow_offsets = offsets.get("Narrow") or offsets.get("narrow") or {}

    defaults = MakeupConfig()
    return MakeupConfig(
        mode=mode,
        wide_open_min=int(wide_offsets.get("open", defaults.wide_open_min) or 0),
        wide_close_min=int(wide_offsets.get("close", defaults.wide_close_min) or 0),
        narrow_open_min=int(narrow_offsets.get("open", defaults.narrow_open_min) or 0),
        narrow_close_min=int(narrow_offsets.get("close", defaults.narrow_close_min) or 0),
    )


def _parse_carousels_config_v1(payload: Dict[str, object]) -> CarouselsConfig:
    mode_raw = str(payload.get("carousels_mode") or "").strip().lower()
    if mode_raw in ("by_terminal_file", "by_terminal", "file"):
        mode = "file"
    elif mode_raw in ("manual", "global"):
        mode = "manual"
    else:
        mode = "file" if payload.get("carousels_by_terminal") else "manual"

    by_terminal: Dict[str, Dict[str, CarouselCap]] = {}
    raw_by_terminal = payload.get("carousels_by_terminal") or {}
    if isinstance(raw_by_terminal, dict):
        for term, items in raw_by_terminal.items():
            caps: Dict[str, CarouselCap] = {}
            if isinstance(items, dict):
                for name, cap in items.items():
                    if not isinstance(cap, dict):
                        continue
                    caps[str(name)] = CarouselCap(
                        wide=int(cap.get("wide", 0) or 0),
                        narrow=int(cap.get("narrow", 0) or 0),
                    )
            elif isinstance(items, list):
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    name = item.get("name") or item.get("carouselName") or item.get("carousel")
                    if not name:
                        continue
                    caps[str(name)] = CarouselCap(
                        wide=int(item.get("wide", item.get("wideCapacity", 0)) or 0),
                        narrow=int(item.get("narrow", item.get("narrowCapacity", 0)) or 0),
                    )
            if caps:
                by_terminal[str(term)] = caps

    return CarouselsConfig(mode=mode, by_terminal=by_terminal)


def _parse_rules_config_v1(payload: Dict[str, object]) -> RulesConfig:
    rules_raw = payload.get("rules") or {}
    max_map = rules_raw.get("max_carousels_per_flight") or {}

    max_wide = int(max_map.get("Wide", max_map.get("wide", 1)) or 1)
    max_narrow = int(max_map.get("Narrow", max_map.get("narrow", 1)) or 1)

    wide_can_use_narrow = bool(rules_raw.get("wide_can_use_narrow", True))
    narrow_can_use_wide = bool(rules_raw.get("narrow_can_use_wide", False))
    rule_multi = bool(rules_raw.get("rule_multi", max_wide > 1 or max_narrow > 1))
    rule_narrow_wide = bool(rules_raw.get("rule_narrow_wide", narrow_can_use_wide))
    rule_extras = bool(rules_raw.get("rule_extras", False))
    apply_readjustment = bool(rules_raw.get("apply_readjustment", True))
    rule_order_raw = rules_raw.get("rule_order") or []
    rule_order = [str(x) for x in rule_order_raw if str(x) in ("multi", "narrow_wide", "extras")]

    return RulesConfig(
        apply_readjustment=apply_readjustment,
        rule_multi=rule_multi,
        rule_narrow_wide=rule_narrow_wide,
        rule_extras=rule_extras,
        max_carousels_narrow=max_narrow,
        max_carousels_wide=max_wide,
        wide_can_use_narrow=wide_can_use_narrow,
        rule_order=rule_order,
    )


def _parse_config_v1(payload: Dict[str, object]) -> RunConfig:
    columns = _parse_columns_payload(payload)
    mapping = CategoryTerminalMapping(
        categories=_normalize_mapping_values(payload.get("category_mapping") or {}, kind="category"),
        terminals=_normalize_mapping_values(payload.get("terminal_mapping") or {}, kind="terminal"),
    )
    makeup = _parse_makeup_config_v1(payload)
    carousels = _parse_carousels_config_v1(payload)
    rules = _parse_rules_config_v1(payload)
    extras_payload = payload.get("extras_by_terminal")
    if extras_payload is None and isinstance(payload.get("extras"), dict):
        extras_payload = payload.get("extras", {}).get("by_terminal")
    extras_by_terminal: Dict[str, CarouselCap] = {}
    if isinstance(extras_payload, dict):
        for term, cap in extras_payload.items():
            if not isinstance(cap, dict):
                continue
            extras_by_terminal[str(term)] = CarouselCap(
                wide=int(cap.get("wide", 0) or 0),
                narrow=int(cap.get("narrow", 0) or 0),
            )
    time_step = int(payload.get("time_step_minutes", 5) or 5)
    return RunConfig(
        columns=columns,
        mapping=mapping,
        makeup=makeup,
        time_step_minutes=time_step,
        carousels=carousels,
        rules=rules,
        extras=ExtrasConfig(by_terminal=extras_by_terminal),
    )

def _parse_config(payload: str) -> RunConfig:
    try:
        raw = json.loads(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid config JSON: {exc}")

    if isinstance(raw, dict) and ("columns" in raw or "carousels" in raw):
        try:
            return RunConfig.parse_obj(raw)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid config JSON: {exc}")

    if not isinstance(raw, dict):
        raise HTTPException(status_code=400, detail="Invalid config JSON: expected object")
    try:
        return _parse_config_v1(raw)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid config JSON: {exc}")


def _read_csv_auto(content: bytes, *, nrows: Optional[int] = None) -> pd.DataFrame:
    try:
        return pd.read_csv(BytesIO(content), sep=None, engine="python", nrows=nrows)
    except Exception:
        for sep in (";", ",", "\t", "|"):
            try:
                return pd.read_csv(BytesIO(content), sep=sep, nrows=nrows)
            except Exception:
                continue
        raise


def _read_excel(upload: UploadFile, *, nrows: Optional[int] = None) -> pd.DataFrame:
    try:
        content = upload.file.read()
        upload.file.seek(0)
        filename = (upload.filename or "").lower()
        content_type = (upload.content_type or "").lower()
        is_csv = filename.endswith(".csv") or content_type in ("text/csv", "application/csv")
        if is_csv:
            return _read_csv_auto(content, nrows=nrows)
        if filename.endswith(".xls"):
            try:
                return pd.read_excel(BytesIO(content), engine="xlrd", nrows=nrows)
            except Exception as exc:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Unable to read .xls file. "
                        "Please convert to .xlsx or install xlrd. "
                        f"Details: {exc}"
                    ),
                )
        return pd.read_excel(BytesIO(content), engine="openpyxl", nrows=nrows)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Unable to read Excel file: {exc}")


def _read_carousels_file(upload: UploadFile) -> pd.DataFrame:
    try:
        content = upload.file.read()
        upload.file.seek(0)
        filename = (upload.filename or "").lower()
        content_type = (upload.content_type or "").lower()
        is_csv = filename.endswith(".csv") or content_type in ("text/csv", "application/csv")
        if is_csv:
            return _read_csv_auto(content)
        if filename.endswith(".xls"):
            try:
                return pd.read_excel(BytesIO(content), engine="xlrd")
            except Exception as exc:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Unable to read .xls file. "
                        "Please convert to .xlsx or install xlrd. "
                        f"Details: {exc}"
                    ),
                )
        return pd.read_excel(BytesIO(content), engine="openpyxl")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Unable to read carousels file: {exc}")


def _parse_baglist_config(payload: str) -> BaglistConfig:
    try:
        raw = json.loads(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid config JSON: {exc}")
    if isinstance(raw, list):
        raw = {"columns": raw}
    if not isinstance(raw, dict):
        raise HTTPException(status_code=400, detail="Invalid config JSON: expected object")
    try:
        return BaglistConfig.parse_obj(raw)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid config JSON: {exc}")


def _normalize_key_value(value: object) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return ""
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    if isinstance(value, float):
        if float(value).is_integer():
            return str(int(value))
        return str(value)
    text = str(value).strip()
    return text


def _normalize_key_series(series: pd.Series) -> pd.Series:
    return series.map(_normalize_key_value)


_BAGLIST_FORMATS = {
    "datetime": "dd/mm/yy hh:mm",
    "date": "dd/mm/yy",
    "time": "hh:mm",
    "number": "0.00",
    "int": "0",
    "minutes": "0",
    "text": "@",
    "bool": "0",
    "boolean": "0",
}


def _coerce_series(series: pd.Series, cast: str) -> pd.Series:
    cast_key = cast.lower()
    if cast_key in ("datetime", "date", "time"):
        dt = pd.to_datetime(series, errors="coerce")
        if cast_key == "date":
            return dt.dt.normalize()
        return dt
    if cast_key in ("number", "numeric", "float"):
        return pd.to_numeric(series, errors="coerce")
    if cast_key in ("int", "integer"):
        return pd.to_numeric(series, errors="coerce")
    if cast_key in ("text", "string"):
        return series.fillna("").astype(str)
    if cast_key in ("bool", "boolean"):
        return series.fillna(False).astype(bool)
    if cast_key == "minutes":
        dt = pd.to_datetime(series, errors="coerce")
        return dt.dt.hour * 60 + dt.dt.minute + dt.dt.second / 60
    return series


def _apply_cast_and_format(
    series: pd.Series,
    cast: Optional[str],
    fmt: Optional[str],
) -> tuple[pd.Series, Optional[str]]:
    excel_format = None
    fmt_key = None
    if fmt:
        fmt_key = fmt.strip().lower()
        if fmt_key in _BAGLIST_FORMATS:
            excel_format = _BAGLIST_FORMATS[fmt_key]
            if not cast:
                cast = fmt_key
        else:
            excel_format = fmt
    if cast:
        series = _coerce_series(series, cast)
    return series, excel_format


def _prepare_lookup_index(
    source_name: str,
    source_df: Optional[pd.DataFrame],
    right_key: str,
    strategy: str,
) -> tuple[Optional[pd.DataFrame], int, List[str]]:
    if source_df is None:
        return None, 0, []
    if right_key not in source_df.columns:
        raise HTTPException(
            status_code=400,
            detail=f"Missing right_key '{right_key}' in {source_name} file.",
        )
    right_norm = _normalize_key_series(source_df[right_key])
    valid_mask = right_norm != ""
    dup_mask = right_norm[valid_mask].duplicated(keep=False)
    dup_keys = sorted(set(right_norm[valid_mask][dup_mask].tolist()))
    dup_count = len(dup_keys)
    if dup_count and strategy == "error":
        raise HTTPException(
            status_code=400,
            detail=f"Duplicate keys in {source_name} for '{right_key}': {dup_count}",
        )
    dedup = source_df.loc[valid_mask].copy()
    dedup["_baglist_key"] = right_norm[valid_mask].values
    dedup = dedup.drop_duplicates(subset=["_baglist_key"], keep="first").set_index("_baglist_key")
    return dedup, dup_count, dup_keys


def _apply_baglist_template(
    bags_df: pd.DataFrame,
    allocation_df: Optional[pd.DataFrame],
    transfers_df: Optional[pd.DataFrame],
    cfg: BaglistConfig,
) -> tuple[pd.DataFrame, pd.DataFrame, Dict[str, object], Dict[str, Optional[str]]]:
    warnings_frames: List[pd.DataFrame] = []
    column_formats: Dict[str, Optional[str]] = {}
    output_df = pd.DataFrame(index=bags_df.index)
    work_df = bags_df.copy()

    lookup_cache: Dict[tuple[str, str, str], tuple[Optional[pd.DataFrame], int, List[str]]] = {}
    join_cache: Dict[tuple[str, str, str], tuple[pd.Series, pd.Series, pd.Series]] = {}

    missing_counts = {"allocation": 0, "transfers": 0}
    not_found_counts = {"allocation": 0, "transfers": 0}
    duplicates_counts = {"allocation": 0, "transfers": 0}
    counted_joins: set[tuple[str, str, str]] = set()

    def _get_source_df(source: str) -> Optional[pd.DataFrame]:
        if source == "allocation":
            return allocation_df
        if source == "transfers":
            return transfers_df
        return None

    for col in cfg.columns:
        output_name = col.output_column
        if not output_name:
            continue

        if col.type == "copy":
            source_field = col.field or output_name
            if source_field not in work_df.columns:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown field '{source_field}' for copy column '{output_name}'.",
                )
            series = work_df[source_field]

        elif col.type == "const":
            series = pd.Series([col.value] * len(work_df), index=work_df.index)

        elif col.type == "lookup":
            source = col.source or "allocation"
            if source not in ("allocation", "transfers"):
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported lookup source '{source}' for '{output_name}'.",
                )
            join_cfg = col.join or BaglistJoinConfig()
            left_key = join_cfg.left_key or ("DepFlightId" if source == "allocation" else "ArrFlightId")
            right_key = join_cfg.right_key or left_key
            if left_key not in work_df.columns:
                raise HTTPException(
                    status_code=400,
                    detail=f"Missing left_key '{left_key}' in bags file for '{output_name}'.",
                )
            strategy = join_cfg.strategy or "first"
            lookup_key = (source, right_key, strategy)
            if lookup_key not in lookup_cache:
                lookup_cache[lookup_key] = _prepare_lookup_index(
                    source,
                    _get_source_df(source),
                    right_key,
                    strategy,
                )
            right_index, dup_count, dup_keys = lookup_cache[lookup_key]
            if dup_count:
                duplicates_counts[source] = max(duplicates_counts[source], dup_count)
                warnings_frames.append(pd.DataFrame({
                    "warning_type": "duplicate_key",
                    "source": source,
                    "output_column": output_name,
                    "left_key": right_key,
                    "left_value": dup_keys,
                    "row_index": [""] * len(dup_keys),
                }))

            if col.field is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"Missing field for lookup column '{output_name}'.",
                )
            if right_index is not None and col.field not in right_index.columns:
                raise HTTPException(
                    status_code=400,
                    detail=f"Field '{col.field}' not found in {source} file for '{output_name}'.",
                )

            join_key = (source, left_key, right_key)
            if join_key in join_cache:
                left_norm, missing_mask, not_found_mask = join_cache[join_key]
            else:
                left_norm = _normalize_key_series(work_df[left_key])
                missing_mask = left_norm == ""
                if right_index is None:
                    not_found_mask = ~missing_mask
                else:
                    not_found_mask = ~missing_mask & ~left_norm.isin(right_index.index)
                join_cache[join_key] = (left_norm, missing_mask, not_found_mask)
                if join_key not in counted_joins:
                    missing_counts[source] += int(missing_mask.sum())
                    not_found_counts[source] += int(not_found_mask.sum())
                    counted_joins.add(join_key)

            default_value = col.default if col.default is not None else ""
            if right_index is None:
                series = pd.Series([default_value] * len(work_df), index=work_df.index)
            else:
                series = left_norm.map(right_index[col.field])
                series = series.where(~(missing_mask | not_found_mask), default_value)

            if missing_mask.any():
                warnings_frames.append(pd.DataFrame({
                    "warning_type": "missing_key",
                    "source": source,
                    "output_column": output_name,
                    "left_key": left_key,
                    "left_value": left_norm[missing_mask].values,
                    "row_index": work_df.index[missing_mask].astype(str).values,
                }))
            if not_found_mask.any():
                warnings_frames.append(pd.DataFrame({
                    "warning_type": "not_found",
                    "source": source,
                    "output_column": output_name,
                    "left_key": left_key,
                    "left_value": left_norm[not_found_mask].values,
                    "row_index": work_df.index[not_found_mask].astype(str).values,
                }))

        elif col.type == "formula":
            if not col.expression:
                raise HTTPException(status_code=400, detail=f"Missing expression for '{output_name}'.")
            try:
                series = eval_baglist_expression(col.expression, work_df)
            except Exception as exc:
                raise HTTPException(status_code=400, detail=f"Formula error for '{output_name}': {exc}")

        elif col.type == "format":
            source_field = col.field or output_name
            if source_field not in work_df.columns:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown field '{source_field}' for format column '{output_name}'.",
                )
            series = work_df[source_field]

        else:
            raise HTTPException(status_code=400, detail=f"Unsupported column type '{col.type}'.")

        series = pd.Series(series, index=work_df.index)
        series, excel_format = _apply_cast_and_format(series, col.cast, col.format)
        output_df[output_name] = series
        work_df[output_name] = series
        if excel_format:
            column_formats[output_name] = excel_format

    warnings_df = pd.concat(warnings_frames, ignore_index=True) if warnings_frames else pd.DataFrame(
        columns=["warning_type", "source", "output_column", "left_key", "left_value", "row_index"]
    )

    kpis = {
        "rows_in": int(len(bags_df)),
        "rows_out": int(len(output_df)),
        "warnings_count": int(len(warnings_df)),
        "missing_depflightid": int(missing_counts["allocation"]),
        "missing_arrflightid": int(missing_counts["transfers"]),
        "allocation_not_found": int(not_found_counts["allocation"]),
        "transfers_not_found": int(not_found_counts["transfers"]),
        "allocation_duplicates": int(duplicates_counts["allocation"]),
        "transfers_duplicates": int(duplicates_counts["transfers"]),
    }

    return output_df, warnings_df, kpis, column_formats


def _write_baglist_excel(path: Path, df: pd.DataFrame, column_formats: Dict[str, Optional[str]]) -> None:
    with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="baglist")
        workbook = writer.book
        worksheet = writer.sheets["baglist"]
        for idx, col_name in enumerate(df.columns):
            fmt = column_formats.get(col_name)
            if not fmt:
                continue
            fmt_obj = workbook.add_format({"num_format": fmt})
            worksheet.set_column(idx, idx, None, fmt_obj)


def _apply_column_mapping(df: pd.DataFrame, mapping: ColumnMapping) -> tuple[pd.DataFrame, List[str]]:
    def _normalize_col_name(value: object) -> str:
        return " ".join(str(value or "").strip().lower().split())

    def _resolve_column(target: Optional[str]) -> Optional[str]:
        if not target:
            return None
        if target in df.columns:
            return target
        norm_target = _normalize_col_name(target)
        if not norm_target:
            return None
        norm_map = {_normalize_col_name(col): col for col in df.columns}
        return norm_map.get(norm_target)

    rename_map: Dict[str, str] = {}
    dep_col = _resolve_column(mapping.departure_time)
    if dep_col:
        rename_map[dep_col] = "DepartureTime"
    flight_col = _resolve_column(mapping.flight_number)
    if flight_col:
        rename_map[flight_col] = "FlightNumber"
    cat_col = _resolve_column(mapping.category)
    if cat_col:
        rename_map[cat_col] = "Category"
    pos_col = _resolve_column(mapping.positions)
    if pos_col:
        rename_map[pos_col] = "Positions"
    term_col = _resolve_column(mapping.terminal)
    if term_col:
        rename_map[term_col] = "Terminal"
    open_col = _resolve_column(mapping.makeup_opening)
    if open_col:
        rename_map[open_col] = "MakeupOpening"
    close_col = _resolve_column(mapping.makeup_closing)
    if close_col:
        rename_map[close_col] = "MakeupClosing"

    df_mapped = df.rename(columns=rename_map).copy()

    required = ["DepartureTime", "FlightNumber", "Category", "Positions"]
    missing = [c for c in required if c not in df_mapped.columns]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing required columns after mapping: {missing}")

    keep_extra_cols = [c for c in (mapping.keep_extra_cols or []) if c in df_mapped.columns]
    return df_mapped, keep_extra_cols


def _apply_makeup(df: pd.DataFrame, makeup: MakeupConfig) -> tuple[pd.DataFrame, List[Dict[str, object]]]:
    warnings: List[Dict[str, object]] = []
    df_ready = df.copy()

    if makeup.mode == "columns":
        if "MakeupOpening" not in df_ready.columns or "MakeupClosing" not in df_ready.columns:
            raise HTTPException(status_code=400, detail="MakeupOpening/MakeupClosing columns are required")
    else:
        def compute_open_close(row: pd.Series) -> pd.Series:
            dep = pd.Timestamp(row["DepartureTime"])
            cat = str(row["Category"]).strip().lower()
            if cat == "wide":
                return pd.Series([
                    dep - pd.Timedelta(minutes=makeup.wide_open_min),
                    dep - pd.Timedelta(minutes=makeup.wide_close_min),
                ])
            if cat == "narrow":
                return pd.Series([
                    dep - pd.Timedelta(minutes=makeup.narrow_open_min),
                    dep - pd.Timedelta(minutes=makeup.narrow_close_min),
                ])
            return pd.Series([pd.NaT, pd.NaT])

        oc = df_ready.apply(compute_open_close, axis=1)
        df_ready["MakeupOpening"] = oc[0]
        df_ready["MakeupClosing"] = oc[1]

    open_ts = pd.to_datetime(df_ready["MakeupOpening"], errors="coerce")
    close_ts = pd.to_datetime(df_ready["MakeupClosing"], errors="coerce")
    bad_times = df_ready[open_ts.isna() | close_ts.isna() | (open_ts >= close_ts)]
    if len(bad_times) > 0:
        warnings.append({
            "Type": "Makeup invalide",
            "Message": "MakeupOpening >= MakeupClosing ou valeurs manquantes",
            "Count": int(len(bad_times)),
        })

    return df_ready, warnings


def _build_caps_manual(config: CarouselsConfig) -> Dict[str, CarouselCapacity]:
    caps_manual: Dict[str, CarouselCapacity] = {}
    for name, cap in (config.manual or {}).items():
        caps_manual[str(name)] = CarouselCapacity(int(cap.wide), int(cap.narrow))
    return caps_manual


def _build_caps_by_terminal(config: CarouselsConfig) -> Dict[str, Dict[str, CarouselCapacity]]:
    caps_by_terminal: Dict[str, Dict[str, CarouselCapacity]] = {}
    for term, items in (config.by_terminal or {}).items():
        caps_by_terminal[str(term)] = {
            str(name): CarouselCapacity(int(cap.wide), int(cap.narrow))
            for name, cap in (items or {}).items()
        }
    return caps_by_terminal


def _normalize_rule_order(rules: RulesConfig) -> List[str]:
    enabled: List[str] = []
    if rules.apply_readjustment:
        if rules.rule_multi:
            enabled.append("multi")
        if rules.rule_narrow_wide:
            enabled.append("narrow_wide")
        if rules.rule_extras:
            enabled.append("extras")
    if not enabled:
        return []

    order = [r for r in (rules.rule_order or []) if r in enabled]
    for r in ["multi", "narrow_wide", "extras"]:
        if r in enabled and r not in order:
            order.append(r)
    return order


def _build_extra_caps(
    config: ExtrasConfig,
    carousels_mode: str,
    df_ready: pd.DataFrame,
    caps_by_terminal: Dict[str, Dict[str, CarouselCapacity]],
    caps_manual: Dict[str, CarouselCapacity],
) -> Dict[str, CarouselCapacity]:
    extra_caps_by_terminal = {
        str(term): CarouselCapacity(int(cap.wide), int(cap.narrow))
        for term, cap in (config.by_terminal or {}).items()
    }

    if extra_caps_by_terminal:
        if carousels_mode == "file" and "ALL" in extra_caps_by_terminal:
            all_cap = extra_caps_by_terminal["ALL"]
            terminals = sorted([str(x).strip() for x in df_ready.get("Terminal", []).dropna().unique().tolist()])
            for term in terminals:
                extra_caps_by_terminal.setdefault(term, all_cap)
        return extra_caps_by_terminal

    if not (carousels_mode == "file" and caps_by_terminal) and not caps_manual:
        return {}

    extra_terms, extra_defaults = _build_extra_terms_and_defaults(
        df_ready,
        carousels_mode,
        caps_by_terminal,
        caps_manual,
    )
    for term in extra_terms:
        wide_def, nar_def = extra_defaults.get(term, (8, 4))
        extra_caps_by_terminal[term] = CarouselCapacity(int(wide_def), int(nar_def))
    return extra_caps_by_terminal

def _run_allocation_pipeline(df_ready: pd.DataFrame, config: RunConfig) -> dict:
    warnings_rows: List[Dict[str, object]] = []

    color_mode = config.colors.color_mode
    if color_mode not in ("category", "terminal", "flight"):
        color_mode = "category"

    if color_mode == "terminal" and "Terminal" not in df_ready.columns:
        warnings_rows.append({
            "Type": "Mode couleur",
            "Message": "Mode terminal demande mais colonne Terminal absente. Fallback par vol.",
            "Count": 1,
        })
        color_mode = "flight"

    allow_wide_use_narrow = bool(config.rules.wide_can_use_narrow)
    start_time = pd.to_datetime(df_ready["MakeupOpening"]).min()
    end_time = pd.to_datetime(df_ready["DepartureTime"]).max()

    carousels_mode = config.carousels.mode
    caps_by_terminal = _build_caps_by_terminal(config.carousels)
    caps_manual = _build_caps_manual(config.carousels)
    car_warnings: List[Dict[str, object]] = []

    if carousels_mode == "file":
        if "Terminal" not in df_ready.columns:
            raise HTTPException(status_code=400, detail="Terminal column is required for carousels mode 'file'.")
        if not caps_by_terminal:
            raise HTTPException(status_code=400, detail="caps_by_terminal is required for carousels mode 'file'.")

        missing_terms = sorted(set(df_ready["Terminal"].unique()) - set(caps_by_terminal.keys()))
        if missing_terms:
            car_warnings.append({
                "Type": "Terminal non configure",
                "Message": "Terminal absent du fichier carrousels",
                "Count": int(len(missing_terms)),
            })

        flights_out_list = []
        timelines = []
        for term, df_term in df_ready.groupby("Terminal"):
            if term not in caps_by_terminal:
                tmp = df_term.copy()
                tmp["AssignedCarousel"] = "UNASSIGNED"
                tmp["UnassignedReason"] = "TERMINAL_NOT_CONFIGURED"
                flights_out_list.append(tmp)
                continue

            flights_out_term, timeline_term = allocate_round_robin(
                flights=df_term,
                carousel_caps=caps_by_terminal[term],
                time_step_minutes=int(config.time_step_minutes),
                start_time=pd.Timestamp(start_time),
                end_time=pd.Timestamp(end_time),
                allow_wide_use_narrow=allow_wide_use_narrow,
            )
            timeline_term = timeline_term.rename(columns={c: f"{term}-{c}" for c in timeline_term.columns})
            flights_out_list.append(flights_out_term)
            timelines.append(timeline_term)

        flights_out = pd.concat(flights_out_list, ignore_index=True) if flights_out_list else df_ready.copy()
        if timelines:
            timeline_df = pd.concat(timelines, axis=1).sort_index(axis=1)
        else:
            timeline_df = pd.DataFrame(
                index=pd.date_range(start=start_time, end=end_time, freq=f"{int(config.time_step_minutes)}min")
            )
    else:
        if not caps_manual:
            raise HTTPException(status_code=400, detail="caps_manual is required for carousels mode 'manual'.")
        flights_out, timeline_df = allocate_round_robin(
            flights=df_ready,
            carousel_caps=caps_manual,
            time_step_minutes=int(config.time_step_minutes),
            start_time=pd.Timestamp(start_time),
            end_time=pd.Timestamp(end_time),
            allow_wide_use_narrow=allow_wide_use_narrow,
        )

    warnings_rows.extend(car_warnings)

    apply_readjustment = bool(config.rules.apply_readjustment)
    rule_order = _normalize_rule_order(config.rules)
    extra_caps_by_terminal = _build_extra_caps(
        config.extras,
        carousels_mode,
        df_ready,
        caps_by_terminal,
        caps_manual,
    )

    flights_readjusted_list: List[pd.DataFrame] = []
    timelines_readjusted: List[pd.DataFrame] = []
    extra_columns: List[str] = []
    extra_summary_rows: List[Dict[str, object]] = []
    extra_warnings: List[Dict[str, object]] = []
    processed_terms: set[str] = set()

    if not apply_readjustment or not rule_order:
        flights_readjusted = flights_out.copy()
        flights_readjusted["OriginalCategory"] = flights_readjusted["Category"].astype(str).str.strip()
        flights_readjusted["FinalCategory"] = flights_readjusted["OriginalCategory"]
        flights_readjusted["CategoryChanged"] = "NO"
        flights_readjusted["Category"] = flights_readjusted["FinalCategory"]
        flights_readjusted["AssignedCarousels"] = (
            flights_readjusted["AssignedCarousel"].fillna("UNASSIGNED").astype(str)
        )
        flights_readjusted["SplitCount"] = flights_readjusted["AssignedCarousels"].apply(
            lambda v: 0 if str(v).upper() == "UNASSIGNED" else 1
        )
        timeline_readjusted = timeline_df.copy()
    elif carousels_mode == "file":
        for term, df_term in flights_out.groupby("Terminal"):
            processed_terms.add(term)
            caps_term = caps_by_terminal.get(term)
            if caps_term is None:
                tmp = df_term.copy()
                tmp["OriginalCategory"] = tmp["Category"].astype(str).str.strip()
                tmp["FinalCategory"] = tmp["OriginalCategory"]
                tmp["CategoryChanged"] = "NO"
                tmp["Category"] = tmp["FinalCategory"]
                tmp["AssignedCarousels"] = "UNASSIGNED"
                tmp["SplitCount"] = 0
                tmp["AssignedCarousel"] = "UNASSIGNED"
                flights_readjusted_list.append(tmp)
                extra_summary_rows.append({
                    "Terminal": term,
                    "Nb extra makeups": 0,
                    "Liste": "",
                })
                continue

            extra_cap = None
            if config.rules.rule_extras and extra_caps_by_terminal:
                extra_cap = extra_caps_by_terminal.get(term)

            readj_term, timeline_term, extras_used, impossible_df = allocate_round_robin_with_rules(
                flights=df_term,
                carousel_caps=caps_term,
                time_step_minutes=int(config.time_step_minutes),
                start_time=pd.Timestamp(start_time),
                end_time=pd.Timestamp(end_time),
                max_carousels_per_flight_narrow=int(config.rules.max_carousels_narrow),
                max_carousels_per_flight_wide=int(config.rules.max_carousels_wide),
                rule_order=rule_order,
                extra_capacity=extra_cap,
                allow_wide_use_narrow=allow_wide_use_narrow,
            )

            if timeline_term is not None and len(timeline_term.columns) > 0:
                timeline_term = timeline_term.reindex(timeline_df.index, fill_value="")
                timeline_term = timeline_term.rename(columns={
                    c: f"{term}-{c}" for c in timeline_term.columns
                })
                timelines_readjusted.append(timeline_term)

            flights_readjusted_list.append(readj_term)
            cols = [f"{term}-{c}" for c in extras_used]
            extra_columns.extend(cols)
            extra_summary_rows.append({
                "Terminal": term,
                "Nb extra makeups": int(len(extras_used)),
                "Liste": ", ".join(cols),
            })

            if config.rules.rule_extras and extra_cap is None:
                remaining = readj_term[readj_term["AssignedCarousel"] == "UNASSIGNED"]
                if len(remaining) > 0:
                    extra_warnings.append({
                        "Type": "Extra sizing",
                        "Message": f"Terminal sans capacite extra configuree: {term}",
                        "Count": int(len(remaining)),
                    })

            if config.rules.rule_extras and impossible_df is not None and len(impossible_df) > 0:
                extra_warnings.append({
                    "Type": "Extra sizing",
                    "Message": f"Vols impossibles pour extra ({term})",
                    "Count": int(len(impossible_df)),
                })

        flights_readjusted = (
            pd.concat(flights_readjusted_list, ignore_index=True)
            if flights_readjusted_list
            else flights_out.copy()
        )
        if timelines_readjusted:
            timeline_readjusted = pd.concat(timelines_readjusted, axis=1).sort_index(axis=1)
        else:
            timeline_readjusted = pd.DataFrame(index=timeline_df.index)
    else:
        extra_cap = None
        if config.rules.rule_extras and extra_caps_by_terminal:
            extra_cap = extra_caps_by_terminal.get("ALL")
        flights_readjusted, timeline_readjusted, extras_used, impossible_df = allocate_round_robin_with_rules(
            flights=flights_out,
            carousel_caps=caps_manual,
            time_step_minutes=int(config.time_step_minutes),
            start_time=pd.Timestamp(start_time),
            end_time=pd.Timestamp(end_time),
            max_carousels_per_flight_narrow=int(config.rules.max_carousels_narrow),
            max_carousels_per_flight_wide=int(config.rules.max_carousels_wide),
            rule_order=rule_order,
            extra_capacity=extra_cap,
            allow_wide_use_narrow=allow_wide_use_narrow,
        )
        timeline_readjusted = timeline_readjusted.reindex(timeline_df.index, fill_value="")
        extra_columns = extras_used
        extra_summary_rows.append({
            "Terminal": "ALL",
            "Nb extra makeups": int(len(extras_used)),
            "Liste": ", ".join(extras_used),
        })

        if config.rules.rule_extras and extra_cap is None:
            remaining = flights_readjusted[flights_readjusted["AssignedCarousel"] == "UNASSIGNED"]
            if len(remaining) > 0:
                extra_warnings.append({
                    "Type": "Extra sizing",
                    "Message": "Terminal sans capacite extra configuree: ALL",
                    "Count": int(len(remaining)),
                })

        if config.rules.rule_extras and impossible_df is not None and len(impossible_df) > 0:
            extra_warnings.append({
                "Type": "Extra sizing",
                "Message": "Vols impossibles pour extra (ALL)",
                "Count": int(len(impossible_df)),
            })
        processed_terms.add("ALL")

    if extra_caps_by_terminal:
        for term in extra_caps_by_terminal.keys():
            if term not in processed_terms:
                extra_summary_rows.append({
                    "Terminal": term,
                    "Nb extra makeups": 0,
                    "Liste": "",
                })

    if extra_summary_rows:
        extra_summary_df = pd.DataFrame(extra_summary_rows)
        extra_makeups_df = extra_summary_df[["Terminal", "Nb extra makeups"]].rename(
            columns={"Nb extra makeups": "ExtraMakeupsNeeded"}
        )
    else:
        extra_summary_df = pd.DataFrame(columns=["Terminal", "Nb extra makeups", "Liste"])
        extra_makeups_df = pd.DataFrame(columns=["Terminal", "ExtraMakeupsNeeded"])

    warnings_rows.extend(extra_warnings)

    unassigned_df = flights_readjusted[flights_readjusted["AssignedCarousel"] == "UNASSIGNED"].copy()
    warnings_rows.append({
        "Type": "UNASSIGNED",
        "Message": "Vols non assignes",
        "Count": int(len(unassigned_df)),
    })

    results = {
        "flights_out": flights_out,
        "flights_readjusted": flights_readjusted,
        "timeline_df": timeline_df,
        "timeline_readjusted": timeline_readjusted,
        "warnings_rows": warnings_rows,
        "unassigned_df": unassigned_df,
        "color_mode": color_mode,
        "wide_color": config.colors.wide_color,
        "narrow_color": config.colors.narrow_color,
        "split_color": config.colors.split_color,
        "narrow_wide_color": config.colors.narrow_wide_color,
        "extra_columns": extra_columns,
        "extra_summary_df": extra_summary_df,
        "extra_makeups_df": extra_makeups_df,
    }
    return results

def _compute_kpis(flights_readjusted: pd.DataFrame, unassigned_df: pd.DataFrame) -> Dict[str, object]:
    display_df = flights_readjusted.copy()
    total = int(len(display_df))
    unassigned_count = int(len(unassigned_df))
    assigned_pct = 0 if total == 0 else int(round(100 * (total - unassigned_count) / total))

    split_count = 0
    if total:
        split_mask = pd.Series([False] * total, index=display_df.index)
        if "SplitCount" in display_df.columns:
            split_mask |= display_df["SplitCount"].fillna(0).astype(int) > 1
        if "AssignedCarousels" in display_df.columns:
            split_mask |= display_df["AssignedCarousels"].astype(str).str.contains(r"\+")
        split_count = int(split_mask.sum())
    split_pct = 0 if total == 0 else int(round(100 * split_count / total))

    changed_mask = display_df.get("CategoryChanged", pd.Series([""] * total)).astype(str).str.upper() == "YES"
    narrow_wide_count = int(changed_mask.sum()) if total else 0
    narrow_wide_pct = 0 if total == 0 else int(round(100 * narrow_wide_count / total))

    return {
        "total_flights": total,
        "assigned_pct": assigned_pct,
        "unassigned_count": unassigned_count,
        "split_count": split_count,
        "split_pct": split_pct,
        "narrow_wide_count": narrow_wide_count,
        "narrow_wide_pct": narrow_wide_pct,
    }


def _compute_analytics(flights_readjusted: pd.DataFrame) -> Dict[str, object]:
    if flights_readjusted is None or len(flights_readjusted) == 0:
        return {
            "terminal_distribution": [],
            "category_breakdown": [],
            "peak_hours": [],
        }

    df = flights_readjusted.copy()

    # Terminal distribution
    term_series = df.get("Terminal", pd.Series([], dtype=object)).fillna("").astype(str).str.strip()
    term_series = term_series.replace("", "Unknown")
    term_counts = term_series.value_counts()
    terminal_distribution = [
        {"terminal": str(term), "count": int(count)} for term, count in term_counts.items()
    ]

    # Category breakdown (assigned vs unassigned)
    def _normalize_cat(value: str) -> str:
        text = str(value or "").strip().lower()
        if not text:
            return "Other"
        if "wide" in text or text in ("w", "wb", "widebody", "wide body"):
            return "Wide"
        if "narrow" in text or text in ("n", "nb", "narrowbody", "narrow body"):
            return "Narrow"
        return "Other"

    cat_series = df.get("Category", pd.Series([], dtype=object)).apply(_normalize_cat)
    assigned_mask = (
        df.get("AssignedCarousel", pd.Series([], dtype=object))
        .fillna("")
        .astype(str)
        .str.upper()
        .ne("UNASSIGNED")
    )

    category_breakdown: List[Dict[str, object]] = []
    for cat in ["Wide", "Narrow", "Other"]:
        subset_idx = cat_series[cat_series == cat].index
        if len(subset_idx) == 0:
            continue
        assigned_count = int(assigned_mask.loc[subset_idx].sum())
        unassigned_count = int(len(subset_idx) - assigned_count)
        category_breakdown.append(
            {"category": cat, "assigned": assigned_count, "unassigned": unassigned_count}
        )

    # Peak hours distribution
    dt_series = pd.Series([], dtype="datetime64[ns]")
    if "DepartureTime" in df.columns:
        dt_series = pd.to_datetime(df["DepartureTime"], errors="coerce")
    elif "STD" in df.columns:
        dt_series = pd.to_datetime(df["STD"], errors="coerce")

    peak_hours: List[Dict[str, object]] = []
    if not dt_series.empty:
        hour_counts = dt_series.dropna().dt.hour.value_counts().sort_index()
        peak_hours = [
            {"hour": f"{int(hour):02d}:00", "flights": int(count)}
            for hour, count in hour_counts.items()
        ]

    # Carousel breakdown
    carousel_col = df.get("AssignedCarousel", pd.Series([], dtype=object)).fillna("").astype(str)
    term_col = df.get("Terminal", pd.Series([], dtype=object)).fillna("").astype(str).str.strip().replace("", "Unknown")
    assigned_mask = carousel_col.str.upper() != "UNASSIGNED"
    if assigned_mask.any():
        grp = df[assigned_mask].copy()
        grp["_term"] = term_col[assigned_mask].values
        grp["_carousel"] = carousel_col[assigned_mask].values
        counts = grp.groupby(["_term", "_carousel"]).size().reset_index(name="count")
        carousel_breakdown: List[Dict[str, object]] = [
            {"carousel": str(r["_carousel"]), "terminal": str(r["_term"]), "count": int(r["count"])}
            for _, r in counts.sort_values("count", ascending=False).iterrows()
        ]
    else:
        carousel_breakdown = []

    return {
        "terminal_distribution": terminal_distribution,
        "category_breakdown": category_breakdown,
        "peak_hours": peak_hours,
        "carousel_breakdown": carousel_breakdown,
    }

def _df_to_records(df: Optional[pd.DataFrame], limit: Optional[int] = None) -> List[Dict[str, object]]:
    if df is None:
        return []
    out = df.copy()
    if limit is not None:
        out = out.head(int(limit))
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = out[col].dt.strftime("%Y-%m-%d %H:%M:%S")
    return out.fillna("").to_dict(orient="records")


def _write_outputs(
    job_dir: Path,
    results: dict,
    keep_extra_cols: List[str],
    extra_caps_by_terminal: Dict[str, CarouselCapacity],
    carousels_mode: str,
    caps_manual: Dict[str, CarouselCapacity],
    caps_by_terminal: Dict[str, Dict[str, CarouselCapacity]],
) -> Dict[str, str]:
    flights_out = results["flights_out"]
    flights_readjusted = results["flights_readjusted"]
    timeline_df = results["timeline_df"]
    timeline_readjusted = results["timeline_readjusted"]
    extra_columns = results.get("extra_columns", [])
    extra_summary_df = results.get("extra_summary_df")

    txt_path = job_dir / "summary.txt"
    csv_path = job_dir / "summary.csv"
    txt_readjusted_path = job_dir / "summary_readjusted.txt"
    csv_readjusted_path = job_dir / "summary_readjusted.csv"
    timeline_path = job_dir / "timeline.xlsx"
    timeline_readjusted_path = job_dir / "timeline_readjusted.xlsx"
    heatmap_occ_path = job_dir / "heatmap_positions_occupied.xlsx"
    heatmap_free_path = job_dir / "heatmap_positions_free.xlsx"
    extra_csv_path = job_dir / "extra_makeups_needed.csv"
    warnings_csv_path = job_dir / "warnings.csv"
    unassigned_csv_path = job_dir / "unassigned_reasons.csv"

    write_summary_txt(str(txt_path), flights_out, extra_cols=keep_extra_cols)
    write_summary_csv(str(csv_path), flights_out)

    export_readjusted = flights_readjusted.drop(columns=["AssignmentSegments"], errors="ignore")
    export_readjusted.sort_values("DepartureTime").to_csv(
        csv_readjusted_path,
        index=False,
        encoding="utf-8",
    )
    export_readjusted.sort_values("DepartureTime").to_csv(
        txt_readjusted_path,
        index=False,
        encoding="utf-8",
        sep="|",
    )

    write_timeline_excel(
        str(timeline_path),
        timeline_df,
        flights_out,
        color_mode=results["color_mode"],
        wide_color=results["wide_color"],
        narrow_color=results["narrow_color"],
        split_color=results["split_color"],
        narrow_wide_color=results["narrow_wide_color"],
    )
    write_timeline_excel(
        str(timeline_readjusted_path),
        timeline_readjusted,
        flights_readjusted,
        color_mode=results["color_mode"],
        wide_color=results["wide_color"],
        narrow_color=results["narrow_color"],
        split_color=results["split_color"],
        narrow_wide_color=results["narrow_wide_color"],
        extra_columns=extra_columns,
        extra_summary=extra_summary_df,
    )

    heatmap_occ_sheets, heatmap_free_sheets = _build_heatmap_sheets(
        flights_readjusted,
        timeline_readjusted.index,
        list(timeline_readjusted.columns),
        carousels_mode=carousels_mode,
        caps_manual=caps_manual,
        caps_by_terminal=caps_by_terminal,
        extra_caps_by_terminal=extra_caps_by_terminal,
    )
    write_heatmap_excel(str(heatmap_occ_path), heatmap_occ_sheets, mode="occupied")
    write_heatmap_excel(str(heatmap_free_path), heatmap_free_sheets, mode="free")

    extra_makeups_df = results.get("extra_makeups_df")
    if extra_makeups_df is not None:
        extra_makeups_df.to_csv(extra_csv_path, index=False, encoding="utf-8")
    else:
        pd.DataFrame(columns=["Terminal", "ExtraMakeupsNeeded"]).to_csv(extra_csv_path, index=False, encoding="utf-8")

    warnings_df = pd.DataFrame(results.get("warnings_rows", []))
    warnings_df.to_csv(warnings_csv_path, index=False, encoding="utf-8")

    unassigned_df = results.get("unassigned_df")
    if unassigned_df is not None and len(unassigned_df) > 0:
        unassigned_df.to_csv(unassigned_csv_path, index=False, encoding="utf-8")
    else:
        pd.DataFrame().to_csv(unassigned_csv_path, index=False, encoding="utf-8")

    downloads = {
        "summary_csv": csv_path.name,
        "summary_txt": txt_path.name,
        "summary_readjusted_csv": csv_readjusted_path.name,
        "summary_readjusted_txt": txt_readjusted_path.name,
        "timeline_xlsx": timeline_path.name,
        "timeline_readjusted_xlsx": timeline_readjusted_path.name,
        "heatmap_occupied_xlsx": heatmap_occ_path.name,
        "heatmap_free_xlsx": heatmap_free_path.name,
        "extra_makeups_needed_csv": extra_csv_path.name,
        "warnings_csv": warnings_csv_path.name,
        "unassigned_reasons_csv": unassigned_csv_path.name,
    }
    return downloads

@app.get("/")
def root() -> RedirectResponse:
    if FRONTEND_DIR.exists():
        return RedirectResponse(url="/app")
    return RedirectResponse(url="/docs")


@app.post("/api/preview")
def preview(
    request: Request,
    response: Response,
    file: Optional[UploadFile] = File(None),
):
    session_id = _get_session_id(request)
    record = _ensure_session(session_id)
    response.headers["X-Session-Id"] = session_id

    if file is not None:
        path = _save_session_file(session_id, file)
        df = _read_excel_path(path, nrows=10)
    else:
        path = _get_session_file_path(record)
        if not path:
            raise HTTPException(status_code=400, detail="Missing file for preview")
        df = _read_excel_path(path, nrows=10)
    cols = list(df.columns)

    suggestions = {
        "DepartureTime": _guess_col(cols, ["std", "departure time", "heure de depart", "dep time"]),
        "FlightNumber": _guess_col(cols, ["flight number", "flight no", "flt", "numero de vol", "num vol"]),
        "Category": _guess_col(cols, ["category", "categorie", "cat", "type"]),
        "Positions": _guess_col(cols, ["positions", "position", "pos", "nb position", "nbr position"]),
        "Terminal": _guess_col(cols, ["terminal", "term", "tml"]),
        "MakeupOpening": _guess_col(cols, ["make up opening", "make-up opening", "makeup opening", "opening"]),
        "MakeupClosing": _guess_col(cols, ["make up closing", "make-up closing", "makeup closing", "closing"]),
    }

    preview_rows = df.head(10).fillna("").to_dict(orient="records")
    return {
        "columns": cols,
        "preview": preview_rows,
        "suggested_mapping": suggestions,
        "file_meta": record.file_meta,
    }


@app.post("/api/inspect")
def inspect(
    request: Request,
    response: Response,
    file: Optional[UploadFile] = File(None),
    config_json: Optional[str] = Form(None),
    config: Optional[str] = Form(None),
):
    session_id = _get_session_id(request)
    record = _ensure_session(session_id)
    response.headers["X-Session-Id"] = session_id
    payload_raw = config_json or config
    if not payload_raw:
        raise HTTPException(status_code=400, detail="Missing config_json for inspect")
    try:
        payload = json.loads(payload_raw)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid config JSON: {exc}")

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid config JSON: expected object")

    columns_cfg = _parse_columns_payload(payload)

    if file is not None:
        path = _save_session_file(session_id, file)
        df_raw = _read_excel_path(path)
    else:
        path = _get_session_file_path(record)
        if not path:
            raise HTTPException(status_code=400, detail="Missing file for inspect")
        df_raw = _read_excel_path(path)
    df_mapped, _ = _apply_column_mapping(df_raw, columns_cfg)

    categories = sorted([str(x).strip() for x in df_mapped.get("Category", pd.Series([])).dropna().unique().tolist()])
    terminals = sorted([str(x).strip() for x in df_mapped.get("Terminal", pd.Series([])).dropna().unique().tolist()])
    return {
        "categories": categories,
        "terminals": terminals,
    }


@app.get("/api/session/state")
def get_session_state(request: Request, response: Response):
    session_id = _get_session_id(request)
    record = _ensure_session(session_id)
    response.headers["X-Session-Id"] = session_id
    return {
        "current_step": record.current_step,
        "wizard_state": record.wizard_state,
        "last_job_id": record.last_job_id,
        "file_meta": record.file_meta,
        "updated_at": record.updated_at,
    }


@app.post("/api/session/state")
def set_session_state(
    payload: SessionStatePayload,
    request: Request,
    response: Response,
):
    session_id = _get_session_id(request)
    record = _ensure_session(session_id)
    response.headers["X-Session-Id"] = session_id

    if payload.current_step is not None:
        record.current_step = int(payload.current_step)
    if payload.wizard_state is not None:
        record.wizard_state = payload.wizard_state
    _touch_session(record)
    _save_session_to_disk(record)
    return {
        "current_step": record.current_step,
        "wizard_state": record.wizard_state,
        "last_job_id": record.last_job_id,
        "file_meta": record.file_meta,
        "updated_at": record.updated_at,
    }


@app.post("/api/carousels/validate")
def validate_carousels(file: UploadFile = File(...)):
    df = _read_carousels_file(file)
    cols = list(df.columns)
    if not cols:
        return {"valid": False, "carousels": [], "errors": ["Fichier vide ou colonnes manquantes."]}

    term_col = _guess_col(cols, ["terminal", "term"])
    name_col = _guess_col(cols, ["carousel", "carrousel", "makeup", "make-up", "name"])
    wide_col = _guess_col(cols, ["wide", "uld"])
    narrow_col = _guess_col(cols, ["narrow", "cart"])

    missing = []
    if not term_col:
        missing.append("Terminal")
    if not name_col:
        missing.append("CarouselName")
    if not wide_col:
        missing.append("WideCapacity")
    if not narrow_col:
        missing.append("NarrowCapacity")

    if missing:
        return {
            "valid": False,
            "carousels": [],
            "errors": [f"Colonnes manquantes: {', '.join(missing)}"],
        }

    carousels: List[Dict[str, object]] = []
    for _, row in df.iterrows():
        term = str(row.get(term_col, "")).strip()
        name = str(row.get(name_col, "")).strip()
        if not term or not name:
            continue
        try:
            wide = int(row.get(wide_col, 0) or 0)
        except Exception:
            wide = 0
        try:
            narrow = int(row.get(narrow_col, 0) or 0)
        except Exception:
            narrow = 0
        carousels.append({
            "terminal": term,
            "carouselName": name,
            "wideCapacity": wide,
            "narrowCapacity": narrow,
        })

    if not carousels:
        return {
            "valid": False,
            "carousels": [],
            "errors": ["Aucun carousel valide detecte dans le fichier."],
        }

    return {"valid": True, "carousels": carousels, "errors": []}


def _compute_input_analytics(df: pd.DataFrame) -> dict:
    result: dict = {
        "total_flights": len(df),
        "date_range": {"min": "", "max": ""},
        "by_hour": [],
        "by_category": [],
        "by_terminal": [],
    }
    try:
        dt = pd.to_datetime(df["DepartureTime"], errors="coerce")
        valid = dt.dropna()
        if len(valid):
            result["date_range"] = {"min": str(valid.min()), "max": str(valid.max())}
        by_hour = dt.dt.hour.value_counts().sort_index()
        result["by_hour"] = [{"hour": int(h), "count": int(c)} for h, c in by_hour.items()]
    except Exception:
        pass
    try:
        if "Category" in df.columns:
            by_cat = df["Category"].value_counts()
            result["by_category"] = [{"category": str(k), "count": int(v)} for k, v in by_cat.items()]
    except Exception:
        pass
    try:
        if "Terminal" in df.columns:
            by_term = df["Terminal"].value_counts()
            result["by_terminal"] = [{"terminal": str(k), "count": int(v)} for k, v in by_term.items()]
    except Exception:
        pass
    return result


@app.post("/api/run")
def run(
    request: Request,
    response: Response,
    file: Optional[UploadFile] = File(None),
    config_json: Optional[str] = Form(None),
    config: Optional[str] = Form(None),
    scenario_name: Optional[str] = Form(None),
):
    session_id = _get_session_id(request)
    record_session = _ensure_session(session_id)
    response.headers["X-Session-Id"] = session_id
    payload = config_json or config
    if not payload:
        raise HTTPException(status_code=400, detail="Missing config_json")
    cfg = _parse_config(payload)
    job_id = str(uuid.uuid4())
    job_dir = JOBS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    record = JobRecord(job_id=job_id, status="running", created_at=_utc_now(), job_dir=job_dir,
                       scenario_name=scenario_name.strip() if scenario_name and scenario_name.strip() else None)
    JOB_STORE[job_id] = record

    try:
        if file is not None:
            path = _save_session_file(session_id, file)
            df_raw = _read_excel_path(path)
        else:
            path = _get_session_file_path(record_session)
            if not path:
                raise HTTPException(status_code=400, detail="Missing file for run")
            df_raw = _read_excel_path(path)
        df_mapped, keep_extra_cols = _apply_column_mapping(df_raw, cfg.columns)
        df_std, mapping_warnings = _apply_cat_term_mapping(df_mapped, cfg.mapping.categories, cfg.mapping.terminals)
        df_ready, makeup_warnings = _apply_makeup(df_std, cfg.makeup)

        # ── Données d'entrée ──────────────────────────────────────────────
        input_analytics: dict = {}
        try:
            df_std.to_csv(job_dir / "input_data.csv", index=False)
            input_analytics = _compute_input_analytics(df_std)
        except Exception:
            pass

        results = _run_allocation_pipeline(df_ready, cfg)
        results["warnings_rows"] = mapping_warnings + makeup_warnings + results.get("warnings_rows", [])

        caps_manual = _build_caps_manual(cfg.carousels)
        caps_by_terminal = _build_caps_by_terminal(cfg.carousels)
        extra_caps_by_terminal = _build_extra_caps(
            cfg.extras,
            cfg.carousels.mode,
            df_ready,
            caps_by_terminal,
            caps_manual,
        )

        downloads = _write_outputs(
            job_dir,
            results,
            keep_extra_cols,
            extra_caps_by_terminal,
            cfg.carousels.mode,
            caps_manual,
            caps_by_terminal,
        )

        kpis = _compute_kpis(results["flights_readjusted"], results["unassigned_df"])
        analytics = _compute_analytics(results["flights_readjusted"])
        if input_analytics:
            analytics["input"] = input_analytics
        warnings_rows = results.get("warnings_rows", [])
        tables = {
            "flights_preview": _df_to_records(results.get("flights_readjusted")),
            "unassigned": _df_to_records(results.get("unassigned_df")),
            "extras_needed": _df_to_records(results.get("extra_makeups_df")),
        }

        record.status = "done"
        record.finished_at = _utc_now()
        record.kpis = kpis
        record.analytics = analytics
        record.warnings = warnings_rows
        record.tables = tables
        record.downloads = {
            key: f"/api/jobs/{job_id}/download/{name}" for key, name in downloads.items()
        }
        if (job_dir / "input_data.csv").exists():
            record.downloads["input_data_csv"] = f"/api/jobs/{job_id}/download/input_data.csv"
        record_session.last_job_id = job_id
        _touch_session(record_session)
        _save_job_to_disk(record)
        _save_session_to_disk(record_session)

        return {
            "job_id": job_id,
            "status": record.status,
            "created_at": record.created_at,
            "finished_at": record.finished_at,
            "kpis": record.kpis,
            "analytics": record.analytics,
            "warnings": record.warnings,
            "downloads": record.downloads,
            "tables": record.tables,
        }
    except HTTPException:
        record.status = "error"
        record.finished_at = _utc_now()
        raise
    except Exception as exc:
        record.status = "error"
        record.finished_at = _utc_now()
        record.error = str(exc)
        raise HTTPException(status_code=500, detail=f"Allocation failed: {exc}")


# ── Custom KPI endpoints ────────────────────────────────────────────────────

@app.get("/api/kpis")
def list_custom_kpis():
    kpis = sorted(CUSTOM_KPI_STORE.values(), key=lambda k: k.created_at)
    return [
        {
            "kpi_id": k.kpi_id,
            "name": k.name,
            "metric": k.metric,
            "display_type": k.display_type,
            "description": k.description,
            "alert_enabled": k.alert_enabled,
            "alert_operator": k.alert_operator,
            "alert_threshold": k.alert_threshold,
            "created_at": k.created_at,
        }
        for k in kpis
    ]


@app.post("/api/kpis")
def create_custom_kpi(payload: CustomKPIPayload):
    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="Le nom du KPI est requis.")
    if not payload.metric.strip():
        raise HTTPException(status_code=400, detail="La metrique est requise.")
    kpi_id = str(uuid.uuid4())
    kpi = CustomKPI(
        kpi_id=kpi_id,
        name=payload.name.strip(),
        metric=payload.metric,
        display_type=payload.display_type,
        description=payload.description.strip(),
        alert_enabled=payload.alert_enabled,
        alert_operator=payload.alert_operator,
        alert_threshold=payload.alert_threshold,
        created_at=_utc_now(),
    )
    CUSTOM_KPI_STORE[kpi_id] = kpi
    _save_custom_kpis_to_disk()
    return {
        "kpi_id": kpi.kpi_id,
        "name": kpi.name,
        "metric": kpi.metric,
        "display_type": kpi.display_type,
        "description": kpi.description,
        "alert_enabled": kpi.alert_enabled,
        "alert_operator": kpi.alert_operator,
        "alert_threshold": kpi.alert_threshold,
        "created_at": kpi.created_at,
    }


@app.delete("/api/kpis/{kpi_id}")
def delete_custom_kpi(kpi_id: str):
    if kpi_id not in CUSTOM_KPI_STORE:
        raise HTTPException(status_code=404, detail="KPI non trouve.")
    del CUSTOM_KPI_STORE[kpi_id]
    _save_custom_kpis_to_disk()
    return {"ok": True}


# ── Admin / migration endpoints ─────────────────────────────────────────────

@app.post("/api/admin/migrate")
def admin_migrate():
    """Force-push all in-memory jobs to Supabase. Call once after setting SUPABASE_KEY."""
    sb = _get_supabase()
    if not sb:
        return {"ok": False, "detail": "Supabase not configured (SUPABASE_URL / SUPABASE_KEY manquants)"}
    pushed = 0
    errors = 0
    for record in list(JOB_STORE.values()):
        if record.status == "done":
            try:
                _save_job_to_supabase(record)
                pushed += 1
            except Exception:
                errors += 1
    return {"ok": True, "pushed": pushed, "errors": errors}


# ── Job list / detail endpoints ─────────────────────────────────────────────

@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: str):
    record = JOB_STORE.get(job_id)
    if not record:
        raise HTTPException(status_code=404, detail="Job non trouve.")
    # Remove from Supabase
    sb = _get_supabase()
    if sb:
        try:
            sb.table("jobs").delete().eq("job_id", job_id).execute()
        except Exception:
            pass
    # Remove files from disk
    if record.job_dir and record.job_dir.exists():
        try:
            import shutil
            shutil.rmtree(record.job_dir)
        except Exception:
            pass
    # Remove from memory
    del JOB_STORE[job_id]
    return {"ok": True}


@app.get("/api/jobs")
def list_jobs(limit: int = 100):
    done_jobs = [r for r in JOB_STORE.values() if r.status == "done"]
    done_jobs.sort(key=lambda r: r.created_at or "", reverse=True)
    done_jobs = done_jobs[:limit]
    return [
        {
            "job_id": r.job_id,
            "scenario_name": r.scenario_name,
            "status": r.status,
            "created_at": r.created_at,
            "finished_at": r.finished_at,
            "storage_size_bytes": r.storage_size_bytes,
            "kpis": r.kpis,
            "analytics": r.analytics,
        }
        for r in done_jobs
    ]


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    record = JOB_STORE.get(job_id)
    if not record:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "job_id": record.job_id,
        "scenario_name": record.scenario_name,
        "status": record.status,
        "created_at": record.created_at,
        "finished_at": record.finished_at,
        "storage_size_bytes": record.storage_size_bytes,
        "kpis": record.kpis,
        "analytics": record.analytics,
        "warnings": record.warnings,
        "downloads": record.downloads,
        "tables": record.tables,
        "error": record.error,
    }


@app.get("/api/jobs/{job_id}/download/{filename}")
def download(job_id: str, filename: str):
    record = JOB_STORE.get(job_id)
    if not record or not record.job_dir:
        raise HTTPException(status_code=404, detail="Job not found")

    safe_name = Path(filename).name
    file_path = record.job_dir / safe_name
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(path=file_path, filename=safe_name)


@app.get("/api/jobs/{job_id}/preview/{filename}")
def preview_result(job_id: str, filename: str, limit: int = 50, offset: int = 0):
    record = JOB_STORE.get(job_id)
    if not record or not record.job_dir:
        raise HTTPException(status_code=404, detail="Job not found")

    safe_name = Path(filename).name
    file_path = record.job_dir / safe_name
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    if not safe_name.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Preview is only available for CSV files")

    df = pd.read_csv(file_path)
    total_rows = len(df)
    if offset > 0:
        df = df.iloc[int(offset):]
    if limit > 0:
        df = df.head(int(limit))
    return {
        "columns": df.columns.tolist(),
        "rows": df.fillna("").to_dict(orient="records"),
        "total_rows": total_rows,
        "offset": offset,
        "limit": limit,
    }


@app.post("/api/baglist/preview")
def baglist_preview(
    bags_file: UploadFile = File(...),
    allocation_file: Optional[UploadFile] = File(None),
    transfers_file: Optional[UploadFile] = File(None),
):
    bags_df = _read_excel(bags_file, nrows=10)
    allocation_df = _read_excel(allocation_file, nrows=10) if allocation_file else None
    transfers_df = _read_excel(transfers_file, nrows=10) if transfers_file else None

    return {
        "bags": {
            "columns": bags_df.columns.tolist(),
            "preview": bags_df.fillna("").head(10).to_dict(orient="records"),
        },
        "allocation": {
            "columns": allocation_df.columns.tolist() if allocation_df is not None else [],
            "preview": allocation_df.fillna("").head(10).to_dict(orient="records") if allocation_df is not None else [],
        },
        "transfers": {
            "columns": transfers_df.columns.tolist() if transfers_df is not None else [],
            "preview": transfers_df.fillna("").head(10).to_dict(orient="records") if transfers_df is not None else [],
        },
    }


@app.post("/api/baglist/run")
def baglist_run(
    bags_file: UploadFile = File(...),
    allocation_file: Optional[UploadFile] = File(None),
    transfers_file: Optional[UploadFile] = File(None),
    config_json: Optional[str] = Form(None),
):
    if not config_json:
        raise HTTPException(status_code=400, detail="Missing config_json")
    cfg = _parse_baglist_config(config_json)

    job_id = str(uuid.uuid4())
    job_dir = JOBS_DIR / job_id / "baglist"
    job_dir.mkdir(parents=True, exist_ok=True)
    record = BaglistJobRecord(job_id=job_id, status="running", created_at=_utc_now(), job_dir=job_dir)
    BAGLIST_JOB_STORE[job_id] = record

    try:
        bags_df = _read_excel(bags_file)
        allocation_df = _read_excel(allocation_file) if allocation_file else None
        transfers_df = _read_excel(transfers_file) if transfers_file else None

        output_df, warnings_df, kpis, column_formats = _apply_baglist_template(
            bags_df,
            allocation_df,
            transfers_df,
            cfg,
        )

        baglist_path = job_dir / "baglist.xlsx"
        warnings_path = job_dir / "baglist_warnings.csv"
        _write_baglist_excel(baglist_path, output_df, column_formats)
        warnings_df.to_csv(warnings_path, index=False, encoding="utf-8")

        preview_rows = _df_to_records(output_df, limit=50)
        warnings_sample = warnings_df.head(50).fillna("").to_dict(orient="records")

        record.status = "done"
        record.finished_at = _utc_now()
        record.kpis = kpis
        record.preview_rows = preview_rows
        record.warnings = warnings_sample
        record.downloads = {
            "baglist_xlsx": f"/api/baglist/jobs/{job_id}/download/{baglist_path.name}",
            "warnings_csv": f"/api/baglist/jobs/{job_id}/download/{warnings_path.name}",
        }

        return {
            "job_id": job_id,
            "kpis": kpis,
            "warnings_sample": warnings_sample,
            "preview_rows": preview_rows,
            "downloads": record.downloads,
        }
    except HTTPException:
        record.status = "error"
        record.finished_at = _utc_now()
        raise
    except Exception as exc:
        record.status = "error"
        record.finished_at = _utc_now()
        record.error = str(exc)
        raise HTTPException(status_code=500, detail=f"Baglist generation failed: {exc}")


@app.get("/api/baglist/jobs/{job_id}")
def baglist_get_job(job_id: str):
    record = BAGLIST_JOB_STORE.get(job_id)
    if not record:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "job_id": record.job_id,
        "status": record.status,
        "created_at": record.created_at,
        "finished_at": record.finished_at,
        "kpis": record.kpis,
        "warnings_sample": record.warnings,
        "preview_rows": record.preview_rows,
        "downloads": record.downloads,
        "error": record.error,
    }


@app.get("/api/baglist/jobs/{job_id}/download/{filename}")
def baglist_download(job_id: str, filename: str):
    record = BAGLIST_JOB_STORE.get(job_id)
    if not record or not record.job_dir:
        raise HTTPException(status_code=404, detail="Job not found")
    safe_name = Path(filename).name
    file_path = record.job_dir / safe_name
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path=file_path, filename=safe_name)


# ─── Mapping Tool ─────────────────────────────────────────────────────────────

class MappingColumnDef(BaseModel):
    target_name: str
    source_col: str = ""
    formula: str = ""
    is_pk: bool = False
    aggregation: str = "First"
    format: str = "Auto"
    include_in_output: bool = True

    class Config:
        extra = "ignore"


class MappingFilterRule(BaseModel):
    col: str
    op: str  # "=", "<>", ">", "<", ">=", "<=", "contains", "not_contains", "starts_with", "ends_with", "is_empty", "is_not_empty"
    val: str = ""

    class Config:
        extra = "ignore"


class MappingExecuteConfig(BaseModel):
    columns: List[MappingColumnDef]
    filters: List[MappingFilterRule] = []
    output_filters: List[MappingFilterRule] = []
    dedup_by_pk: bool = False
    output_format: Literal["csv", "excel"] = "csv"
    output_filename: str = "mapping_output.csv"

    class Config:
        extra = "ignore"


def _read_df_from_bytes(content: bytes, filename: str, nrows: Optional[int] = None) -> pd.DataFrame:
    fn = (filename or "").lower()
    if fn.endswith(".csv"):
        return _read_csv_auto(content, nrows=nrows)
    buf = BytesIO(content)
    if fn.endswith(".xls"):
        return pd.read_excel(buf, engine="xlrd", nrows=nrows)
    return pd.read_excel(buf, engine="openpyxl", nrows=nrows)


def _split_formula_args(s: str) -> list:
    """Split comma-separated formula arguments respecting nested parentheses and quoted strings."""
    args: list = []
    depth = 0
    in_quote = False
    quote_char = ""
    current: list = []
    for ch in s:
        if ch in ('"', "'") and not in_quote:
            in_quote, quote_char = True, ch
            current.append(ch)
        elif ch == quote_char and in_quote:
            in_quote = False
            current.append(ch)
        elif ch == "(" and not in_quote:
            depth += 1
            current.append(ch)
        elif ch == ")" and not in_quote:
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0 and not in_quote:
            args.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    if current:
        args.append("".join(current).strip())
    return args


def _find_comparison_in_cond(s: str) -> Optional[tuple]:
    """Find the first comparison operator at paren-depth=0 outside quotes.
    Returns (op, left_str, right_str) or None. Operators checked longest-first."""
    ops = (">=", "<=", "<>", "!=", ">", "<", "=")
    in_quote = False
    quote_char = ""
    depth = 0
    i = 0
    while i < len(s):
        ch = s[i]
        if ch in ('"', "'") and not in_quote:
            in_quote, quote_char = True, ch
        elif ch == quote_char and in_quote:
            in_quote = False
        elif ch == "(" and not in_quote:
            depth += 1
        elif ch == ")" and not in_quote:
            depth -= 1
        elif depth == 0 and not in_quote:
            for op in ops:
                if s[i:i + len(op)] == op:
                    return op, s[:i].strip(), s[i + len(op):].strip()
        i += 1
    return None


def _rfind_op_at_depth0(expr: str, ops: tuple) -> Optional[tuple]:
    """Find the rightmost operator from `ops` at paren-depth=0 outside quotes, position > 0.
    Returns (op, left_str, right_str) or None."""
    in_q = False; q_ch = ""; depth = 0
    last_pos: Optional[int] = None; last_op: Optional[str] = None
    i = 0
    while i < len(expr):
        ch = expr[i]
        if ch in ('"', "'") and not in_q:
            in_q, q_ch = True, ch
        elif ch == q_ch and in_q:
            in_q = False
        elif ch == "(" and not in_q:
            depth += 1
        elif ch == ")" and not in_q:
            depth -= 1
        elif depth == 0 and not in_q and i > 0:
            for op in ops:
                if expr[i:i + len(op)] == op:
                    last_pos, last_op = i, op
                    break
        i += 1
    if last_pos is not None and last_op is not None:
        return last_op, expr[:last_pos].strip(), expr[last_pos + len(last_op):].strip()
    return None


def _eval_condition(cond: str, df: pd.DataFrame) -> "pd.Series":
    """Return a boolean Series for a condition string.
    Supports AND/OR/NOT wrappers and comparisons like Col="val", LEFT(Col,3)>"X".
    Operators are found at paren-depth=0 so nested formulas aren't split."""
    import pandas as _pd
    cond = cond.strip()
    n = len(df)

    # AND(cond1, cond2, ...)
    m = re.match(r'^AND\((.+)\)$', cond, re.IGNORECASE | re.DOTALL)
    if m:
        parts = _split_formula_args(m.group(1))
        result: "pd.Series" = _pd.Series([True] * n)
        for p in parts:
            result = result & _eval_condition(p.strip(), df)
        return result.reset_index(drop=True)

    # OR(cond1, cond2, ...)
    m = re.match(r'^OR\((.+)\)$', cond, re.IGNORECASE | re.DOTALL)
    if m:
        parts = _split_formula_args(m.group(1))
        result = _pd.Series([False] * n)
        for p in parts:
            result = result | _eval_condition(p.strip(), df)
        return result.reset_index(drop=True)

    # NOT(cond)
    m = re.match(r'^NOT\((.+)\)$', cond, re.IGNORECASE | re.DOTALL)
    if m:
        return (~_eval_condition(m.group(1).strip(), df)).reset_index(drop=True)

    # Comparison — depth-aware scan so operators inside parentheses are ignored
    found = _find_comparison_in_cond(cond)
    if found:
        op_str, left_s, right_s = found

        # Left side: evaluate as a formula (handles column refs, LEFT(Col,3), etc.)
        try:
            left_col = _eval_mapping_formula(left_s, df)
        except Exception:
            left_col = _pd.Series([left_s] * n)

        # Right side: quoted string, numeric, column ref, or formula
        if (right_s.startswith('"') and right_s.endswith('"')) or \
           (right_s.startswith("'") and right_s.endswith("'")):
            raw_str = right_s[1:-1]
            if _pd.api.types.is_datetime64_any_dtype(left_col):
                try:
                    right_val: Any = _pd.to_datetime(raw_str)
                except Exception:
                    right_val = raw_str
                    left_col = left_col.astype(str)
            else:
                right_val = raw_str
                left_col = left_col.astype(str)
        else:
            try:
                rv = float(right_s)
                right_val = int(rv) if rv == int(rv) else rv
                left_col = _pd.to_numeric(left_col, errors="coerce")
            except ValueError:
                # Column reference or formula on the right side
                try:
                    right_val = _eval_mapping_formula(right_s, df)
                    left_col = left_col.astype(str)
                    right_val = right_val.astype(str)
                except Exception:
                    right_val = right_s
                    left_col = left_col.astype(str)

        ops_map = {
            ">=": lambda a, b: a >= b,
            "<=": lambda a, b: a <= b,
            "<>": lambda a, b: a != b,
            "!=": lambda a, b: a != b,
            ">":  lambda a, b: a > b,
            "<":  lambda a, b: a < b,
            "=":  lambda a, b: a == b,
        }
        try:
            return ops_map[op_str](left_col, right_val).reset_index(drop=True)
        except Exception:
            return _pd.Series([False] * n)

    return _pd.Series([True] * n)


def _eval_mapping_formula(expr: str, df: pd.DataFrame) -> pd.Series:
    expr = expr.strip()
    n = len(df)
    empty: pd.Series = pd.Series([""] * n, dtype=object)

    if not expr:
        return empty

    # String constant
    if (expr.startswith('"') and expr.endswith('"')) or (expr.startswith("'") and expr.endswith("'")):
        return pd.Series([expr[1:-1]] * n)

    # Numeric constant
    try:
        val = float(expr)
        v: Any = int(val) if val == int(val) else val
        return pd.Series([v] * n)
    except (ValueError, TypeError):
        pass

    # Simple column reference
    if expr in df.columns:
        return df[expr].reset_index(drop=True)

    # Parenthesized expression — strip outer parens and re-evaluate
    if expr.startswith("(") and expr.endswith(")"):
        _pdepth = 0; _fully = True
        for _pi, _pc in enumerate(expr):
            if _pc == "(": _pdepth += 1
            elif _pc == ")": _pdepth -= 1
            if _pdepth == 0 and _pi < len(expr) - 1:
                _fully = False; break
        if _fully:
            return _eval_mapping_formula(expr[1:-1], df)

    # LEFT(Col, k)
    m = re.match(r'^LEFT\((.+),\s*(\d+)\)$', expr, re.IGNORECASE)
    if m:
        col, k = m.group(1).strip(), int(m.group(2))
        if col in df.columns:
            return df[col].astype(str).str[:k].reset_index(drop=True)

    # RIGHT(Col, k)
    m = re.match(r'^RIGHT\((.+),\s*(\d+)\)$', expr, re.IGNORECASE)
    if m:
        col, k = m.group(1).strip(), int(m.group(2))
        if col in df.columns:
            return df[col].astype(str).str[-k:].reset_index(drop=True)

    # MID(Col, start, length)
    m = re.match(r'^MID\((.+),\s*(\d+),\s*(\d+)\)$', expr, re.IGNORECASE)
    if m:
        col, s, lg = m.group(1).strip(), int(m.group(2)), int(m.group(3))
        if col in df.columns:
            return df[col].astype(str).str[s - 1:s - 1 + lg].reset_index(drop=True)

    # LEN(Col)
    m = re.match(r'^LEN\((.+)\)$', expr, re.IGNORECASE)
    if m:
        col = m.group(1).strip()
        if col in df.columns:
            return df[col].astype(str).str.len().reset_index(drop=True)

    # UPPER(Col)
    m = re.match(r'^UPPER\((.+)\)$', expr, re.IGNORECASE)
    if m:
        col = m.group(1).strip()
        if col in df.columns:
            return df[col].astype(str).str.upper().reset_index(drop=True)

    # LOWER(Col)
    m = re.match(r'^LOWER\((.+)\)$', expr, re.IGNORECASE)
    if m:
        col = m.group(1).strip()
        if col in df.columns:
            return df[col].astype(str).str.lower().reset_index(drop=True)

    # TRIM(Col)
    m = re.match(r'^TRIM\((.+)\)$', expr, re.IGNORECASE)
    if m:
        col = m.group(1).strip()
        if col in df.columns:
            return df[col].astype(str).str.strip().reset_index(drop=True)

    # TEXTBEFORE(Col, "delim")
    m = re.match(r'^TEXTBEFORE\((.+),\s*"(.*)"\)$', expr, re.IGNORECASE)
    if m:
        col, delim = m.group(1).strip(), m.group(2)
        if col in df.columns:
            return df[col].astype(str).apply(
                lambda x: x.split(delim)[0] if delim in x else x
            ).reset_index(drop=True)

    # TEXTAFTER(Col, "delim")
    m = re.match(r'^TEXTAFTER\((.+),\s*"(.*)"\)$', expr, re.IGNORECASE)
    if m:
        col, delim = m.group(1).strip(), m.group(2)
        if col in df.columns:
            return df[col].astype(str).apply(
                lambda x: delim.join(x.split(delim)[1:]) if delim in x else x
            ).reset_index(drop=True)

    # SUBSTITUTE(Col, "old", "new"[, instance])  — replace occurrences
    m = re.match(r'^SUBSTITUTE\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        if len(args) >= 3:
            col = args[0].strip()
            old_val = args[1].strip().strip('"\'')
            new_val = args[2].strip().strip('"\'')
            src = _eval_mapping_formula(col, df).astype(str)
            return src.str.replace(old_val, new_val, regex=False).reset_index(drop=True)

    # VALUE(Col)  — convert text to number
    m = re.match(r'^VALUE\((.+)\)$', expr, re.IGNORECASE)
    if m:
        src = _eval_mapping_formula(m.group(1).strip(), df)
        return pd.to_numeric(src, errors="coerce").reset_index(drop=True)

    # ROUND(Col, decimals)
    m = re.match(r'^ROUND\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        if len(args) == 2:
            src = pd.to_numeric(_eval_mapping_formula(args[0].strip(), df), errors="coerce")
            try:
                decimals = int(args[1].strip())
                return src.round(decimals).reset_index(drop=True)
            except ValueError:
                pass

    # INT(Col)  — floor to integer
    m = re.match(r'^INT\((.+)\)$', expr, re.IGNORECASE)
    if m:
        src = pd.to_numeric(_eval_mapping_formula(m.group(1).strip(), df), errors="coerce")
        return src.apply(lambda x: int(x) if pd.notna(x) else "").reset_index(drop=True)

    # ABS(Col)
    m = re.match(r'^ABS\((.+)\)$', expr, re.IGNORECASE)
    if m:
        src = pd.to_numeric(_eval_mapping_formula(m.group(1).strip(), df), errors="coerce")
        return src.abs().reset_index(drop=True)

    # IFERROR(formula, fallback)  — return fallback if formula produces NaN/error
    m = re.match(r'^IFERROR\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        if len(args) == 2:
            try:
                result = _eval_mapping_formula(args[0].strip(), df)
            except Exception:
                result = pd.Series([""] * n, dtype=object)
            fallback = _eval_mapping_formula(args[1].strip(), df)
            combined = result.where(result.notna() & (result.astype(str) != "nan"), other=fallback)
            return combined.reset_index(drop=True)

    # ISNUMBER(Col)  — TRUE/FALSE
    m = re.match(r'^ISNUMBER\((.+)\)$', expr, re.IGNORECASE)
    if m:
        src = _eval_mapping_formula(m.group(1).strip(), df)
        return pd.to_numeric(src, errors="coerce").notna().reset_index(drop=True)

    # ISBLANK(Col)  — TRUE if empty or null
    m = re.match(r'^ISBLANK\((.+)\)$', expr, re.IGNORECASE)
    if m:
        src = _eval_mapping_formula(m.group(1).strip(), df)
        return (src.isna() | (src.astype(str).str.strip() == "")).reset_index(drop=True)

    # ISTEXT(Col)
    m = re.match(r'^ISTEXT\((.+)\)$', expr, re.IGNORECASE)
    if m:
        src = _eval_mapping_formula(m.group(1).strip(), df)
        return (pd.to_numeric(src, errors="coerce").isna() & src.notna()).reset_index(drop=True)

    # DATE(year, month, day) — build a date from numeric parts (columns or constants)
    m = re.match(r'^DATE\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        if len(args) == 3:
            y_s = pd.to_numeric(_eval_mapping_formula(args[0].strip(), df), errors="coerce")
            mo_s = pd.to_numeric(_eval_mapping_formula(args[1].strip(), df), errors="coerce")
            d_s = pd.to_numeric(_eval_mapping_formula(args[2].strip(), df), errors="coerce")
            def _mk_ts(yr, mn, dy):
                try: return pd.Timestamp(int(yr), int(mn), int(dy))
                except Exception: return pd.NaT
            return pd.Series([_mk_ts(yr, mn, dy) for yr, mn, dy in zip(y_s, mo_s, d_s)]).reset_index(drop=True)

    # TODAY() — current date without time
    if re.match(r'^TODAY\(\)$', expr, re.IGNORECASE):
        return pd.Series([pd.Timestamp.today().normalize()] * n)

    # NOW() — current datetime
    if re.match(r'^NOW\(\)$', expr, re.IGNORECASE):
        return pd.Series([pd.Timestamp.now()] * n)

    # YEAR/MONTH/DAY/HOUR/MINUTE/SECOND(Col) — extract date/time component
    m = re.match(r'^(YEAR|MONTH|DAY|HOUR|MINUTE|SECOND)\((.+)\)$', expr, re.IGNORECASE)
    if m:
        fn = m.group(1).upper()
        src_eval = _eval_mapping_formula(m.group(2).strip(), df)

        # timedelta64: pandas reads Excel "time" columns as timedelta (e.g. 0 days 22:45:00)
        if pd.api.types.is_timedelta64_dtype(src_eval) and fn in ("HOUR", "MINUTE", "SECOND"):
            ts = src_eval.dt.total_seconds()
            if fn == "HOUR":   return (ts // 3600).reset_index(drop=True)
            if fn == "MINUTE": return ((ts % 3600) // 60).reset_index(drop=True)
            if fn == "SECOND": return (ts % 60).reset_index(drop=True)

        # float fraction 0–1: Excel time serial (0.9479... = 22:45) — no .astype(int) to avoid NaN crash
        if pd.api.types.is_numeric_dtype(src_eval) and fn in ("HOUR", "MINUTE", "SECOND"):
            ts = src_eval % 1 * 86400
            if fn == "HOUR":   return (ts // 3600).reset_index(drop=True)
            if fn == "MINUTE": return ((ts % 3600) // 60).reset_index(drop=True)
            if fn == "SECOND": return (ts % 60).reset_index(drop=True)

        # Convert to datetime64 for all other cases
        if pd.api.types.is_datetime64_any_dtype(src_eval):
            src_dt = src_eval
        elif pd.api.types.is_timedelta64_dtype(src_eval):
            src_dt = pd.Timestamp("2000-01-01") + src_eval
        else:
            def _coerce_dt(x):
                try:
                    if x is None or (not hasattr(x, 'hour') and pd.isna(x)):
                        return pd.NaT
                    if hasattr(x, 'hour') and hasattr(x, 'minute'):
                        # datetime.time or datetime.datetime objects
                        return pd.Timestamp(2000, 1, 1, x.hour, x.minute, getattr(x, 'second', 0))
                    if hasattr(x, 'total_seconds'):
                        # timedelta object (scalar)
                        s = float(x.total_seconds())
                        return pd.Timestamp(2000, 1, 1, int(s // 3600), int(s % 3600 // 60), int(s % 60))
                    return pd.to_datetime(x, errors='coerce')
                except Exception:
                    return pd.NaT
            src_dt = src_eval.apply(_coerce_dt)

        parts = {"YEAR": src_dt.dt.year, "MONTH": src_dt.dt.month, "DAY": src_dt.dt.day,
                 "HOUR": src_dt.dt.hour, "MINUTE": src_dt.dt.minute, "SECOND": src_dt.dt.second}
        return parts[fn].reset_index(drop=True)

    # DATEVALUE(Col) — parse text to date (time stripped)
    m = re.match(r'^DATEVALUE\((.+)\)$', expr, re.IGNORECASE)
    if m:
        src = _eval_mapping_formula(m.group(1).strip(), df)
        return pd.to_datetime(src, errors="coerce").dt.normalize().reset_index(drop=True)

    # TIMEVALUE(Col) — parse time, return fraction of day (0.0–1.0)
    m = re.match(r'^TIMEVALUE\((.+)\)$', expr, re.IGNORECASE)
    if m:
        src = _eval_mapping_formula(m.group(1).strip(), df)
        dt_t = pd.to_datetime(src, errors="coerce")
        return ((dt_t.dt.hour * 3600 + dt_t.dt.minute * 60 + dt_t.dt.second) / 86400.0).reset_index(drop=True)

    # TEXT(Col, "format") — format date/number as string
    # Convention: MM=month, mm=minute, dd=day, yyyy=year, HH/hh=hour, ss=second
    m = re.match(r'^TEXT\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        if len(args) == 2:
            src = _eval_mapping_formula(args[0].strip(), df)
            fmt_raw = args[1].strip().strip("\"'")
            py_chars: list = []; fi = 0
            while fi < len(fmt_raw):
                if fmt_raw[fi:fi+4] == "yyyy":   py_chars.append("%Y"); fi += 4
                elif fmt_raw[fi:fi+2] == "yy":   py_chars.append("%y"); fi += 2
                elif fmt_raw[fi:fi+2] == "MM":   py_chars.append("%m"); fi += 2
                elif fmt_raw[fi:fi+2] == "dd":   py_chars.append("%d"); fi += 2
                elif fmt_raw[fi:fi+2] in ("HH", "hh"): py_chars.append("%H"); fi += 2
                elif fmt_raw[fi:fi+2] == "mm":   py_chars.append("%M"); fi += 2
                elif fmt_raw[fi:fi+2] == "ss":   py_chars.append("%S"); fi += 2
                else: py_chars.append(fmt_raw[fi]); fi += 1
            py_fmt = "".join(py_chars)
            return pd.to_datetime(src, errors="coerce").dt.strftime(py_fmt).reset_index(drop=True)

    # DATEADD(date, n, "unit") — add a time delta to a date column
    m = re.match(r'^DATEADD\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        if len(args) == 3:
            dt_da = pd.to_datetime(_eval_mapping_formula(args[0].strip(), df), errors="coerce")
            n_da = pd.to_numeric(_eval_mapping_formula(args[1].strip(), df), errors="coerce").fillna(0)
            unit_da = args[2].strip().strip("\"'").lower()
            _u = {"day":"D","days":"D","d":"D","hour":"h","hours":"h","h":"h",
                  "minute":"min","minutes":"min","m":"min","min":"min","second":"s","seconds":"s","s":"s"}
            return (dt_da + pd.to_timedelta(n_da, unit=_u.get(unit_da, "D"))).reset_index(drop=True)

    # DATEDIFF(date1, date2, "unit") — numeric difference between two dates
    m = re.match(r'^DATEDIFF\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        if len(args) >= 2:
            dt1 = pd.to_datetime(_eval_mapping_formula(args[0].strip(), df), errors="coerce")
            dt2 = pd.to_datetime(_eval_mapping_formula(args[1].strip(), df), errors="coerce")
            unit_dd = args[2].strip().strip("\"'").lower() if len(args) >= 3 else "day"
            diff = dt2 - dt1
            if unit_dd in ("day", "days", "d"): return diff.dt.days.reset_index(drop=True)
            if unit_dd in ("hour", "hours", "h"): return (diff.dt.total_seconds() / 3600).reset_index(drop=True)
            if unit_dd in ("minute", "minutes", "m", "min"): return (diff.dt.total_seconds() / 60).reset_index(drop=True)
            return diff.dt.days.reset_index(drop=True)

    # TIMETOMIN(time_col [, day_col]) — convert time to total minutes, with optional day offset
    # Handles all time formats: timedelta64, float fraction (0–1), datetime.time, datetime string
    # Examples:  TIMETOMIN(UnloadTime)              → minutes since midnight (22:45 → 1365)
    #            TIMETOMIN(UnloadTime, UnloadDay)   → day*1440 + time_minutes
    m = re.match(r'^TIMETOMIN\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        t_src = _eval_mapping_formula(args[0].strip(), df)
        if pd.api.types.is_timedelta64_dtype(t_src):
            mins = t_src.dt.total_seconds() / 60
        elif pd.api.types.is_numeric_dtype(t_src):
            mins = t_src % 1 * 1440  # Excel time fraction → minutes
        else:
            def _t2s(x):
                try:
                    if x is None: return float("nan")
                    if hasattr(x, 'hour'): return x.hour * 60 + x.minute + getattr(x, 'second', 0) / 60
                    if hasattr(x, 'total_seconds'): return x.total_seconds() / 60
                    ts = pd.to_datetime(x, errors='coerce')
                    return float("nan") if pd.isna(ts) else ts.hour * 60 + ts.minute + ts.second / 60
                except Exception: return float("nan")
            mins = t_src.apply(_t2s)
        if len(args) >= 2:
            day_src = pd.to_numeric(_eval_mapping_formula(args[1].strip(), df), errors="coerce").fillna(0)
            mins = mins + day_src * 1440
        return mins.reset_index(drop=True)

    # NOT(condition)
    m = re.match(r'^NOT\((.+)\)$', expr, re.IGNORECASE)
    if m:
        return (~_eval_condition(m.group(1).strip(), df)).reset_index(drop=True)

    # COALESCE(Col1, Col2, ...)  — first non-null/empty value
    m = re.match(r'^COALESCE\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        result = pd.Series([""] * n, dtype=object)
        for arg in reversed(args):
            src = _eval_mapping_formula(arg.strip(), df)
            mask = src.notna() & (src.astype(str).str.strip() != "")
            result = src.where(mask, other=result)
        return result.reset_index(drop=True)

    # CONCAT(Col1, Col2, ...)  — multi-arg concatenation (alias for & chain)
    m = re.match(r'^CONCAT\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        result_str = pd.Series([""] * n, dtype=str)
        for arg in args:
            src = _eval_mapping_formula(arg.strip(), df)
            result_str = result_str + src.fillna("").astype(str)
        return result_str.reset_index(drop=True)

    # IF(condition, true_value, false_value)
    # Examples:
    #   IF(Terminal="T1", "T1", "Other")
    #   IF(Weight>100, "Heavy", "Light")
    #   IF(AND(Status="OK", Weight>50), "Good", "Bad")
    #   IF(OR(Status="DELAYED", Status="CANCELLED"), "Issue", "OK")
    m = re.match(r'^IF\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        if len(args) == 3:
            cond_str, true_str, false_str = args
            condition = _eval_condition(cond_str, df)
            true_series = _eval_mapping_formula(true_str.strip(), df)
            false_series = _eval_mapping_formula(false_str.strip(), df)
            return pd.Series(
                [t if c else f for c, t, f in zip(condition, true_series, false_series)],
                dtype=object,
            )

    # ROW([start]) — row index with optional arithmetic
    # Examples: ROW()  ROW(1)  ROW()+1  ROW(1)**2  ROW()*2+1
    m = re.match(r'^ROW\((\d*)\)\s*(.*)$', expr, re.IGNORECASE)
    if m:
        start = int(m.group(1)) if m.group(1) else 0
        arithmetic = m.group(2).strip()
        idx = np.arange(start, start + n, dtype=float)
        if not arithmetic:
            return pd.Series(idx.astype(int))
        # Allow only safe arithmetic characters to avoid code injection
        if re.match(r'^[\d\s\+\-\*\/\(\)\.\^%]+$', arithmetic):
            arithmetic = arithmetic.replace('^', '**')  # accept ^ as power operator
            try:
                result_arr = eval(f"idx{arithmetic}", {"idx": idx, "__builtins__": {}})  # noqa: S307
                return pd.Series(result_arr)
            except Exception:
                pass

    # Concatenation with &  — split respecting quotes and parentheses
    if "&" in expr:
        amp_parts: list = []
        _depth = 0
        _in_q = False
        _qc = ""
        _cur: list = []
        for _ch in expr:
            if _ch in ('"', "'") and not _in_q:
                _in_q, _qc = True, _ch
                _cur.append(_ch)
            elif _ch == _qc and _in_q:
                _in_q = False
                _cur.append(_ch)
            elif _ch == "(" and not _in_q:
                _depth += 1
                _cur.append(_ch)
            elif _ch == ")" and not _in_q:
                _depth -= 1
                _cur.append(_ch)
            elif _ch == "&" and _depth == 0 and not _in_q:
                amp_parts.append("".join(_cur).strip())
                _cur = []
            else:
                _cur.append(_ch)
        if _cur:
            amp_parts.append("".join(_cur).strip())

        if len(amp_parts) > 1:
            result: pd.Series = pd.Series([""] * n, dtype=str)
            for p in amp_parts:
                part_val = _eval_mapping_formula(p, df)
                result = result + part_val.fillna("").astype(str)
            return result

    # Arithmetic: additive (+, -) — checked before multiplicative for correct precedence
    found_add = _rfind_op_at_depth0(expr, ("+", "-"))
    if found_add:
        op_a, l_a, r_a = found_add
        lv = _eval_mapping_formula(l_a, df)
        rv = _eval_mapping_formula(r_a, df)
        if pd.api.types.is_datetime64_any_dtype(lv):
            delta = pd.to_timedelta(pd.to_numeric(rv, errors="coerce").fillna(0), unit="D")
            return (lv + delta if op_a == "+" else lv - delta).reset_index(drop=True)
        ln = pd.to_numeric(lv, errors="coerce")
        rn = pd.to_numeric(rv, errors="coerce")
        return (ln + rn if op_a == "+" else ln - rn).reset_index(drop=True)

    # Arithmetic: multiplicative (*, /)
    found_mul = _rfind_op_at_depth0(expr, ("*", "/"))
    if found_mul:
        op_m, l_m, r_m = found_mul
        ln_m = pd.to_numeric(_eval_mapping_formula(l_m, df), errors="coerce")
        rn_m = pd.to_numeric(_eval_mapping_formula(r_m, df), errors="coerce")
        if op_m == "*":
            return (ln_m * rn_m).reset_index(drop=True)
        return (ln_m / rn_m.replace(0, float("nan"))).reset_index(drop=True)

    return empty


def _apply_filters(df: pd.DataFrame, filters: list) -> pd.DataFrame:
    """Apply row filters to a DataFrame, returning only matching rows."""
    if not filters:
        return df
    mask = pd.Series([True] * len(df), index=df.index)
    for f in filters:
        if f.col not in df.columns:
            continue
        col = df[f.col]
        op, val = f.op, f.val
        try:
            if op == "=":
                try:
                    mask &= pd.to_numeric(col, errors="raise") == float(val)
                except Exception:
                    mask &= col.astype(str).str.lower() == val.lower()
            elif op == "<>":
                try:
                    mask &= pd.to_numeric(col, errors="raise") != float(val)
                except Exception:
                    mask &= col.astype(str).str.lower() != val.lower()
            elif op == ">":
                mask &= pd.to_numeric(col, errors="coerce") > float(val)
            elif op == "<":
                mask &= pd.to_numeric(col, errors="coerce") < float(val)
            elif op == ">=":
                mask &= pd.to_numeric(col, errors="coerce") >= float(val)
            elif op == "<=":
                mask &= pd.to_numeric(col, errors="coerce") <= float(val)
            elif op == "contains":
                mask &= col.astype(str).str.contains(val, case=False, na=False)
            elif op == "not_contains":
                mask &= ~col.astype(str).str.contains(val, case=False, na=False)
            elif op == "starts_with":
                mask &= col.astype(str).str.startswith(val, na=False)
            elif op == "ends_with":
                mask &= col.astype(str).str.endswith(val, na=False)
            elif op == "is_empty":
                mask &= col.isna() | (col.astype(str).str.strip() == "")
            elif op == "is_not_empty":
                mask &= col.notna() & (col.astype(str).str.strip() != "")
        except Exception:
            continue
    return df[mask].reset_index(drop=True)


def _run_mapping(df_src: pd.DataFrame, config: "MappingExecuteConfig") -> pd.DataFrame:
    df_src = _apply_filters(df_src, config.filters)
    out: Dict[str, pd.Series] = {}
    pk_col: Optional[str] = None

    # Build a combined DataFrame incrementally so later formulas can reference
    # already-computed output columns (e.g. =test_2 reusing an earlier column).
    # Output column names take precedence over source columns with the same name.
    df_work = df_src.reset_index(drop=True).copy()

    for col_def in config.columns:
        formula = col_def.formula.strip()
        if formula.startswith("="):
            series = _eval_mapping_formula(formula[1:], df_work)
        elif formula:
            series = pd.Series([formula] * len(df_work))
        else:
            series = pd.Series([""] * len(df_work))
        series = series.reset_index(drop=True)
        # Always store raw (datetime-aware) in df_work for cross-column references
        df_work[col_def.target_name] = series
        # Only include in final output if include_in_output is True
        if col_def.include_in_output:
            # Apply format: convert datetime to user-friendly string
            out_series = series
            if pd.api.types.is_datetime64_any_dtype(series):
                _fmt = (col_def.format or "").lower()
                if _fmt == "date":
                    out_series = series.dt.strftime("%d/%m/%Y")
                elif _fmt == "datetime":
                    out_series = series.dt.strftime("%d/%m/%Y %H:%M")
                elif _fmt == "time":
                    out_series = series.dt.strftime("%H:%M")
                else:
                    # Auto: if all times are midnight, render date only
                    _no_time = (series.dt.hour == 0) & (series.dt.minute == 0) & (series.dt.second == 0)
                    if _no_time.all():
                        out_series = series.dt.strftime("%d/%m/%Y")
            out[col_def.target_name] = out_series
        if col_def.is_pk:
            pk_col = col_def.target_name

    df_out = pd.DataFrame(out)

    if pk_col and pk_col in df_out.columns:
        mask = df_out[pk_col].notna() & (df_out[pk_col].astype(str).str.strip() != "")
        df_out = df_out[mask].reset_index(drop=True)

    if config.dedup_by_pk and pk_col and pk_col in df_out.columns:
        agg_map: Dict[str, Any] = {}
        for col_def in config.columns:
            t = col_def.target_name
            if t == pk_col:
                continue
            a = col_def.aggregation.lower()
            if a == "sum":       agg_map[t] = "sum"
            elif a == "count":   agg_map[t] = "count"
            elif a == "max":     agg_map[t] = "max"
            elif a == "min":     agg_map[t] = "min"
            elif a == "average": agg_map[t] = "mean"
            elif a == "last":    agg_map[t] = "last"
            elif a == "concat":  agg_map[t] = lambda x: "; ".join(str(v) for v in x if str(v) not in ("", "nan"))
            else:                agg_map[t] = "first"
        df_out = df_out.groupby(pk_col, sort=False).agg(agg_map).reset_index()

    # Apply output filters (filter on computed output columns, after dedup)
    if config.output_filters:
        df_out = _apply_filters(df_out, config.output_filters)

    return df_out


@app.post("/api/mapping/columns")
def mapping_get_columns(file: UploadFile = File(...)):
    content = file.file.read()
    try:
        df = _read_df_from_bytes(content, file.filename or "")
        return {"columns": list(df.columns), "row_count": len(df)}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Cannot read file: {exc}")


@app.post("/api/mapping/preview")
def mapping_preview(
    file: UploadFile = File(...),
    config_json: str = Form(...),
):
    try:
        config = MappingExecuteConfig(**json.loads(config_json))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid config: {exc}")

    content = file.file.read()
    try:
        df_src = _read_df_from_bytes(content, file.filename or "")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Cannot read file: {exc}")

    df_out = _run_mapping(df_src, config)
    total = len(df_out)
    preview = df_out.head(100)

    def _safe(v: Any) -> Any:
        if isinstance(v, float) and (v != v):  # NaN
            return None
        try:
            if pd.isna(v):
                return None
        except (TypeError, ValueError):
            pass
        if isinstance(v, (int, float, bool, str, type(None))):
            return v
        return str(v)

    rows_json = [
        {col: _safe(val) for col, val in row.items()}
        for _, row in preview.iterrows()
    ]
    return {
        "columns": list(df_out.columns),
        "rows": rows_json,
        "total_rows": total,
        "preview_rows": len(rows_json),
    }


@app.post("/api/mapping/execute")
def mapping_execute(
    file: UploadFile = File(...),
    config_json: str = Form(...),
):
    try:
        config = MappingExecuteConfig(**json.loads(config_json))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid config: {exc}")

    content = file.file.read()
    try:
        df_src = _read_df_from_bytes(content, file.filename or "")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Cannot read file: {exc}")

    df_out = _run_mapping(df_src, config)

    buf = BytesIO()
    if config.output_format == "excel":
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df_out.to_excel(writer, sheet_name="Output", index=False)
        buf.seek(0)
        return Response(
            content=buf.read(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{config.output_filename}"'},
        )
    df_out.to_csv(buf, index=False, encoding="utf-8-sig")
    buf.seek(0)
    return Response(
        content=buf.read(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={config.output_filename}"},
    )


@app.get("/baglist")
@app.get("/baglist/results/{job_id}")
def baglist_page(job_id: Optional[str] = None):
    baglist_path = FRONTEND_DIR / "baglist.html"
    if not baglist_path.exists():
        raise HTTPException(status_code=404, detail="Baglist frontend not found")
    return FileResponse(baglist_path)


if FRONTEND_DIR.exists():
    app.mount("/app", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
