"""
api_app.py — Serveur FastAPI : point d'entrée de l'API backend
==============================================================

RÔLE DANS LE SYSTÈME
--------------------
Ce fichier est le serveur HTTP de l'outil d'allocation.
Il reçoit les requêtes du frontend (Next.js sur Vercel), exécute l'allocation,
et renvoie les résultats (KPIs, téléchargements, tables).

Il est déployé sur Railway et répond aux endpoints /api/*.

ORGANISATION DU FICHIER
------------------------
  1. Imports
  2. Modèles Pydantic (schémas de requête/réponse)
  3. Dataclasses internes (JobRecord, SessionRecord, CustomKPI)
  4. Configuration du stockage (chemins disque)
  5. Client Supabase (persistance cloud)
  6. Application FastAPI + CORS
  7. Stores en mémoire (JOB_STORE, SESSION_STORE, CUSTOM_KPI_STORE)
  8. Helpers de persistance (disque + Supabase)
  9. Helpers de gestion de session
 10. Helpers de lecture des fichiers (Excel/CSV)
 11. Helpers de parsing de la configuration
 12. Pipeline d'allocation (_run_allocation_pipeline)
 13. Calcul des KPIs et analytics
 14. Écriture des fichiers de sortie (_write_outputs)
 15. Endpoints de l'outil d'allocation (/api/preview, /api/inspect, /api/run, …)
 16. Endpoints KPI custom (/api/kpis)
 17. Endpoints admin (/api/admin/migrate)
 18. Endpoints jobs (/api/jobs, /api/jobs/{id}/download, …)
 19. Outil de mapping (modèles + helpers + endpoints /api/mapping/*)

POUR MODIFIER
-------------
- Ajouter un endpoint                 : ajouter @app.post("/api/...") avec sa fonction
- Ajouter un champ de configuration   : modifier le modèle Pydantic correspondant
- Changer l'algorithme d'allocation   : modifier allocator_engine.py (pas ce fichier)
- Changer les fichiers de sortie      : modifier _write_outputs() ou allocator_io.py
- Ajouter un KPI                      : modifier _compute_kpis() et CustomKPI
- Changer le comportement des filtres : modifier _get_filter_mask() (Mapping Tool)
"""

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
from allocator_io import (
    _build_heatmap_sheets,
    _build_extra_terms_and_defaults,
    write_heatmap_excel,
    write_summary_csv,
    write_summary_txt,
    write_timeline_excel,
)
from app_mapping import _apply_cat_term_mapping, _guess_col


# ── 2. Modèles Pydantic (schémas de requête JSON) ─────────────────────────────

class ColumnMapping(BaseModel):
    """Correspondance entre les noms de colonnes du fichier source et les noms standards.

    Le frontend envoie les noms bruts (ex: "Heure de départ") et ce modèle
    les associe aux noms standards attendus par l'allocateur (ex: "DepartureTime").
    keep_extra_cols : colonnes supplémentaires à conserver dans les résultats.
    """
    departure_time: str = Field(..., description="Raw column for DepartureTime")
    flight_number: str = Field(..., description="Raw column for FlightNumber")
    category: str = Field(..., description="Raw column for Category")
    positions: str = Field(..., description="Raw column for Positions")
    terminal: Optional[str] = Field(None, description="Raw column for Terminal")
    makeup_opening: Optional[str] = Field(None, description="Raw column for MakeupOpening")
    makeup_closing: Optional[str] = Field(None, description="Raw column for MakeupClosing")
    keep_extra_cols: List[str] = Field(default_factory=list)


class CategoryTerminalMapping(BaseModel):
    """Tables de correspondance pour normaliser les catégories et terminaux.

    categories : ex {"W": "Wide", "NB": "Narrow", "XL": "IGNORER"}
    terminals  : ex {"TER1": "T1", "MAIN": "IGNORER"}
    Les valeurs "IGNORER" excluent les lignes correspondantes de l'allocation.
    """
    categories: Dict[str, str] = Field(default_factory=dict)
    terminals: Dict[str, str] = Field(default_factory=dict)


class MakeupConfig(BaseModel):
    """Configuration des fenêtres de makeup (ouverture/fermeture).

    mode "columns" : lit MakeupOpening et MakeupClosing depuis le fichier.
    mode "compute" : calcule ouverture/fermeture par offset depuis DepartureTime.
    Les offsets sont en minutes avant le départ (valeurs positives).
    """
    mode: Literal["columns", "compute"] = "columns"
    wide_open_min: int = 120
    wide_close_min: int = 60
    narrow_open_min: int = 90
    narrow_close_min: int = 45

    @validator("wide_open_min", "wide_close_min", "narrow_open_min", "narrow_close_min")
    def _non_negative(cls, v: int) -> int:
        return max(0, int(v))


class CarouselCap(BaseModel):
    """Capacité d'un carrousel : nombre de positions Wide et Narrow disponibles."""
    wide: int = 0
    narrow: int = 0

    @validator("wide", "narrow")
    def _non_negative(cls, v: int) -> int:
        return max(0, int(v))


class CarouselsConfig(BaseModel):
    """Configuration des carrousels disponibles pour l'allocation.

    mode "manual"   : capacités saisies manuellement dans le wizard.
    mode "file"     : capacités lues depuis un fichier Excel uploadé par terminal.
    manual          : dict {nom_carrousel → capacité} (mode manual).
    by_terminal     : dict {terminal → {nom_carrousel → capacité}} (mode file).
    """
    mode: Literal["manual", "file"] = "manual"
    manual: Dict[str, CarouselCap] = Field(default_factory=dict)
    by_terminal: Dict[str, Dict[str, CarouselCap]] = Field(default_factory=dict)


class RulesConfig(BaseModel):
    """Configuration des règles de réajustement appliquées après l'allocation initiale.

    apply_readjustment : si False, aucune règle n'est appliquée.
    rule_multi         : autorise le split d'un vol sur plusieurs carrousels.
    rule_narrow_wide   : autorise les vols Narrow à utiliser des positions Wide.
    rule_extras        : autorise la création de carrousels EXTRA.
    rule_order         : ordre d'application des règles (ex: ["multi", "extras"]).
    max_carousels_*    : nombre maximum de carrousels alloués par vol.
    """
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
    """Capacité des carrousels EXTRA à créer si la règle 'extras' est activée.

    by_terminal : dict {terminal → capacité_extra}.
    "ALL" est utilisé quand il n'y a pas de multi-terminal.
    Si vide, la capacité est déduite automatiquement depuis les carrousels existants.
    """
    by_terminal: Dict[str, CarouselCap] = Field(default_factory=dict)


class ColorsConfig(BaseModel):
    """Configuration des couleurs de mise en forme de la timeline Excel.

    color_mode : "category" (Wide=rouge, Narrow=rose), "flight" (1 couleur/vol),
                 "terminal" (1 couleur/terminal).
    Les couleurs spéciales split et narrow_wide s'appliquent en priorité.
    """
    color_mode: Literal["category", "terminal", "flight"] = "category"
    wide_color: str = "#D32F2F"
    narrow_color: str = "#FFEBEE"
    split_color: str = "#FFC107"
    narrow_wide_color: str = "#00B894"


class RunConfig(BaseModel):
    """Configuration complète d'un run d'allocation.

    Regroupe tous les paramètres nécessaires : colonnes, mapping, makeup,
    carrousels, règles, extras et couleurs. Envoyé par le frontend en JSON.
    """
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
    """Payload pour sauvegarder l'état du wizard dans la session utilisateur."""
    current_step: Optional[int] = None
    wizard_state: Dict[str, object] = Field(default_factory=dict)


# ── 3. Dataclasses internes ───────────────────────────────────────────────────

@dataclass
class JobRecord:
    """Représente un job d'allocation en mémoire.

    Un job est créé à chaque appel POST /api/run.
    Il est stocké dans JOB_STORE (mémoire) et persisté sur disque + Supabase.
    job_dir : répertoire sur disque contenant les fichiers de résultats.
    """
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
    """Représente la session d'un utilisateur du wizard.

    La session est identifiée par un UUID transmis dans le header X-Session-Id.
    Elle mémorise l'état du wizard (étape courante, paramètres saisis)
    et le chemin du fichier Excel uploadé par l'utilisateur.
    """
    session_id: str
    wizard_state: Dict[str, object] = field(default_factory=dict)
    current_step: int = 1
    last_job_id: Optional[str] = None
    file_path: Optional[str] = None
    file_meta: Dict[str, object] = field(default_factory=dict)
    updated_at: str = ""


@dataclass
class CustomKPI:
    """KPI personnalisé défini par l'utilisateur pour la page analytics.

    metric : identifiant de la métrique (ex: "assigned_pct", "unassigned_count").
    display_type : "percentage" | "counter" | "text".
    alert_enabled : si True, une alerte est déclenchée selon alert_operator/threshold.
    """
    kpi_id: str
    name: str
    metric: str
    display_type: str
    description: str = ""
    alert_enabled: bool = False
    alert_operator: str = "lt"   # "lt" | "gt"
    alert_threshold: float = 0.0
    created_at: str = ""


class CustomKPIPayload(BaseModel):
    """Payload pour créer ou modifier un KPI personnalisé."""
    name: str
    metric: str
    display_type: str
    description: str = ""
    alert_enabled: bool = False
    alert_operator: str = "lt"
    alert_threshold: float = 0.0

    class Config:
        extra = "ignore"


# ── 4. Configuration du stockage (chemins disque) ─────────────────────────────

ROOT_DIR = Path(__file__).resolve().parent
STORAGE_DIR = ROOT_DIR / "storage"
JOBS_DIR = STORAGE_DIR / "jobs"          # Un sous-dossier par job_id
SESSIONS_DIR = STORAGE_DIR / "sessions"  # Un fichier JSON par session
FRONTEND_DIR = ROOT_DIR / "frontend"
CUSTOM_KPI_FILE = STORAGE_DIR / "custom_kpis.json"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
JOBS_DIR.mkdir(parents=True, exist_ok=True)
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

# ── 5. Client Supabase ────────────────────────────────────────────────────────

# Le client est initialisé en lazy (à la première utilisation) pour éviter
# de bloquer le démarrage si SUPABASE_URL n'est pas configuré.
_supabase_client = None

def _get_supabase():
    """Retourne le client Supabase, ou None si non configuré.

    Variables d'environnement requises (sur Railway) :
        SUPABASE_URL  : URL du projet Supabase
        SUPABASE_KEY  : service_role key (ou NEXT_PUBLIC_SUPABASE_ANON_KEY si RLS désactivé)
    """
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


# ── 6. Application FastAPI + CORS ─────────────────────────────────────────────

app = FastAPI(title="Carousel Allocation API", version="1.0")

# CORS : autorise le frontend Vercel et localhost en développement.
# Pour ajouter un domaine : ajouter à ALLOWED_ORIGINS ou modifier ALLOWED_ORIGIN_REGEX.
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

# ── 7. Stores en mémoire ──────────────────────────────────────────────────────

# Ces dicts sont rechargés depuis le disque et Supabase au démarrage.
# En production (Railway), ils sont partagés entre toutes les requêtes.
JOB_STORE: Dict[str, JobRecord] = {}
SESSION_STORE: Dict[str, SessionRecord] = {}
CUSTOM_KPI_STORE: Dict[str, CustomKPI] = {}


def _utc_now() -> str:
    """Retourne l'heure actuelle en UTC au format ISO 8601."""
    return datetime.now(timezone.utc).isoformat()


# ── 8. Helpers de persistance (disque + Supabase) ─────────────────────────────

def _job_to_dict(record: JobRecord) -> dict:
    """Sérialise un JobRecord en dict JSON-compatible pour la persistance disque."""
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
    """Calcule la taille totale en octets de tous les fichiers d'un job."""
    if not job_dir or not job_dir.exists():
        return 0
    return sum(f.stat().st_size for f in job_dir.iterdir() if f.is_file())


def _save_job_to_supabase(record: JobRecord) -> None:
    """Sauvegarde (ou met à jour) un job dans la table Supabase "jobs".

    Utilise upsert (insert ou update selon si job_id existe déjà).
    Silencieux en cas d'erreur pour ne pas bloquer l'allocation.
    """
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
    """Charge tous les jobs depuis Supabase dans JOB_STORE.

    Appelée au démarrage pour récupérer les jobs persistés (ex: après redémarrage Railway).
    Si un job existe en mémoire et en Supabase, Supabase prend le dessus
    (il contient scenario_name et storage_size_bytes mis à jour).
    """
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
    """Sauvegarde un job sur disque (job.json) ET dans Supabase."""
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
    """Charge tous les jobs depuis le disque local dans JOB_STORE au démarrage."""
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
    """Sauvegarde l'état d'une session dans un fichier JSON sur disque."""
    try:
        session_path = SESSIONS_DIR / f"{record.session_id}.json"
        data = {
            "session_id": record.session_id,
            "wizard_state": record.wizard_state,
            "current_step": record.current_step,
            "last_job_id": record.last_job_id,
            "file_meta": record.file_meta,
            "file_path": record.file_path,
            "updated_at": record.updated_at,
        }
        with open(session_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, default=str)
    except Exception:
        pass


def _load_sessions_from_disk() -> None:
    """Charge toutes les sessions depuis le disque dans SESSION_STORE au démarrage."""
    for session_file in SESSIONS_DIR.glob("*.json"):
        try:
            with open(session_file, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            session_id = data["session_id"]
            file_path = data.get("file_path")
            # Only restore file_path if the file still exists on disk
            if file_path and not Path(file_path).exists():
                file_path = None
            # Fallback: scan the session directory for any uploaded file
            if not file_path:
                session_dir = SESSIONS_DIR / session_id
                if session_dir.is_dir():
                    candidates = [
                        p for p in session_dir.iterdir()
                        if p.is_file() and p.suffix.lower() in (".xlsx", ".xls", ".csv")
                    ]
                    if candidates:
                        # Use the most recently modified file
                        file_path = str(max(candidates, key=lambda p: p.stat().st_mtime))
            record = SessionRecord(
                session_id=session_id,
                wizard_state=data.get("wizard_state", {}),
                current_step=data.get("current_step", 1),
                last_job_id=data.get("last_job_id"),
                file_meta=data.get("file_meta", {}),
                file_path=file_path,
                updated_at=data.get("updated_at", ""),
            )
            SESSION_STORE[record.session_id] = record
        except Exception:
            pass


def _save_custom_kpis_to_disk() -> None:
    """Sauvegarde tous les KPIs personnalisés dans custom_kpis.json."""
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
    """Charge les KPIs personnalisés depuis custom_kpis.json au démarrage."""
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


# ── 9. Helpers de gestion de session ──────────────────────────────────────────

def _get_session_id(request: Request) -> str:
    """Extrait le session_id depuis le header X-Session-Id, ou en génère un nouveau."""
    session_id = request.headers.get("x-session-id")
    if session_id:
        return session_id
    return str(uuid.uuid4())


def _ensure_session(session_id: str) -> SessionRecord:
    """Retourne la session existante ou en crée une nouvelle si absente."""
    record = SESSION_STORE.get(session_id)
    if not record:
        record = SessionRecord(session_id=session_id, updated_at=_utc_now())
        SESSION_STORE[session_id] = record
    return record


def _touch_session(record: SessionRecord) -> None:
    """Met à jour le timestamp updated_at d'une session."""
    record.updated_at = _utc_now()


def _save_session_file(session_id: str, upload: UploadFile) -> Path:
    """Sauvegarde le fichier uploadé sur disque et met à jour les métadonnées de session.

    Le fichier est stocké dans SESSIONS_DIR/{session_id}/{filename}.
    Retourne le chemin complet du fichier sauvegardé.
    """
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
    _save_session_to_disk(record)
    return dest_path


def _get_session_file_path(record: SessionRecord) -> Optional[Path]:
    """Retourne le chemin du fichier de la session, ou None s'il n'existe plus."""
    if not record.file_path:
        return None
    path = Path(record.file_path)
    if not path.exists():
        return None
    return path


# ── 10. Helpers de lecture des fichiers ───────────────────────────────────────

def _read_excel_path(path: Path, *, nrows: Optional[int] = None) -> pd.DataFrame:
    """Lit un fichier Excel ou CSV depuis un chemin disque.

    Supporte .csv (auto-détection du séparateur), .xls et .xlsx.
    nrows : limite le nombre de lignes lues (pour la prévisualisation).
    Lève HTTPException 400 en cas d'erreur de lecture.
    """
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
    """Nettoie une valeur de mapping : retourne None si vide, "default", "none", "null" ou "nan"."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.lower() in ("default", "none", "null", "nan"):
        return None
    return text


def _normalize_mapping_value(value: object, *, kind: Literal["category", "terminal"]) -> str:
    """Normalise une valeur de mapping vers sa forme standard ou "IGNORER".

    Pour les catégories : "W"/"WB"/"wide body" → "Wide", "N"/"NB" → "Narrow".
    Pour les terminaux : retourne la valeur en majuscules.
    Toute valeur "ignore"/"none"/vide → "IGNORER" (la ligne sera exclue).
    """
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
    """Normalise toutes les clés et valeurs d'un dict de mapping.

    Applique _normalize_mapping_value sur chaque entrée.
    Pour les terminaux, les clés sont mises en majuscules.
    """
    out: Dict[str, str] = {}
    for key, value in (mapping or {}).items():
        key_text = str(key).strip()
        if not key_text:
            continue
        if kind == "terminal":
            key_text = key_text.upper()
        out[key_text] = _normalize_mapping_value(value, kind=kind)
    return out


# ── 11. Helpers de parsing de la configuration ────────────────────────────────

def _parse_columns_payload(payload: Dict[str, object]) -> ColumnMapping:
    """Extrait le mapping de colonnes depuis un payload JSON (format v1 ou v2).

    Format v2 (nouveau) : {"columns": {"departure_time": "...", ...}}
    Format v1 (ancien)  : {"DepartureTime": "...", "FlightNumber": "...", ...}
                          ou via une clé "mapping".
    """
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
    """Parse la configuration makeup depuis le format v1 du wizard frontend."""
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
    """Parse la configuration des carrousels depuis le format v1 du wizard frontend.

    Supporte les deux formats de "carousels_by_terminal" :
    - dict : {terminal: {carousel: {wide, narrow}}}
    - liste : [{name, wideCapacity, narrowCapacity}]
    """
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
    """Parse la configuration des règles de réajustement depuis le format v1."""
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
    """Parse un payload de configuration au format "v1" (wizard frontend historique).

    Le format v1 est le format plat envoyé par le wizard du frontend.
    Il diffère du format v2 (Pydantic RunConfig direct) par les noms de clés.
    Cette fonction le convertit en RunConfig standardisé.
    """
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
    """Parse la configuration JSON envoyée par le frontend en RunConfig.

    Détecte automatiquement le format :
    - Format v2 : JSON avec clé "columns" ou "carousels" → parse directement en RunConfig.
    - Format v1 : JSON plat du wizard → passe par _parse_config_v1.
    Lève HTTPException 400 si le JSON est invalide.
    """
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
    """Lit un CSV en détectant automatiquement le séparateur (,  ;  tab  |).

    Essaie d'abord l'auto-détection Python, puis teste chaque séparateur.
    """
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
    """Lit un fichier uploadé (Excel ou CSV) depuis un UploadFile FastAPI."""
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
    """Lit le fichier de configuration des carrousels uploadé par l'utilisateur."""
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


def _apply_column_mapping(df: pd.DataFrame, mapping: ColumnMapping) -> tuple[pd.DataFrame, List[str]]:
    """Renomme les colonnes du DataFrame selon le mapping utilisateur.

    Résout chaque nom de colonne source (insensible à la casse, sans espaces doubles)
    vers le nom standard attendu par l'allocateur.
    Lève HTTPException 400 si une colonne requise est manquante après renommage.
    Retourne (df_renommé, liste_des_colonnes_extra_conservées).
    """
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
    """Applique la configuration makeup sur le DataFrame de vols.

    En mode "columns" : vérifie que MakeupOpening/MakeupClosing existent déjà.
    En mode "compute" : calcule les fenêtres par offset depuis DepartureTime.
    Retourne (df_avec_makeup, warnings) où warnings liste les lignes avec dates invalides.
    """
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
    """Construit le dict de capacités {nom_carrousel → CarouselCapacity} depuis le mode manual."""
    caps_manual: Dict[str, CarouselCapacity] = {}
    for name, cap in (config.manual or {}).items():
        caps_manual[str(name)] = CarouselCapacity(int(cap.wide), int(cap.narrow))
    return caps_manual


def _build_caps_by_terminal(config: CarouselsConfig) -> Dict[str, Dict[str, CarouselCapacity]]:
    """Construit le dict de capacités par terminal {terminal → {carrousel → CarouselCapacity}} depuis le mode file."""
    caps_by_terminal: Dict[str, Dict[str, CarouselCapacity]] = {}
    for term, items in (config.by_terminal or {}).items():
        caps_by_terminal[str(term)] = {
            str(name): CarouselCapacity(int(cap.wide), int(cap.narrow))
            for name, cap in (items or {}).items()
        }
    return caps_by_terminal


def _normalize_rule_order(rules: RulesConfig) -> List[str]:
    """Construit la liste ordonnée des règles à appliquer depuis RulesConfig.

    Respecte l'ordre personnalisé de rule_order si fourni, sinon utilise
    l'ordre par défaut : multi → narrow_wide → extras.
    Retourne [] si apply_readjustment est False ou aucune règle activée.
    """
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
    """Construit le dict de capacités EXTRA {terminal → CarouselCapacity}.

    Si des capacités EXTRA sont configurées dans ExtrasConfig → les utilise directement.
    Sinon → déduit automatiquement depuis les capacités existantes (max wide/narrow).
    La clé "ALL" est utilisée en mode manual (pas de multi-terminal).
    """
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

# ── 12. Pipeline d'allocation ─────────────────────────────────────────────────

def _run_allocation_pipeline(df_ready: pd.DataFrame, config: RunConfig) -> dict:
    """Exécute le pipeline complet d'allocation sur le DataFrame de vols préparé.

    Le pipeline se déroule en 3 étapes :

      Étape 1 — Allocation initiale (round-robin)
        - Mode "file" : allocation par terminal, colonnes renommées "TERMINAL-CARROUSEL"
        - Mode "manual" : allocation globale sur tous les carrousels

      Étape 2 — Réajustement (si apply_readjustment = True et règles activées)
        - Par terminal (mode file) ou global (mode manual)
        - Applique les règles dans l'ordre : multi, narrow_wide, extras

      Étape 3 — Agrégation des résultats
        - Construit les DataFrames de résumé des EXTRA makeups
        - Compile les warnings

    Retourne un dict avec :
        flights_out         : résultats de l'allocation initiale
        flights_readjusted  : résultats après réajustement
        timeline_df         : timeline initiale
        timeline_readjusted : timeline après réajustement
        warnings_rows       : liste de warnings (avertissements)
        unassigned_df       : vols non assignés
        color_mode, *_color : paramètres de couleur pour l'export Excel
        extra_columns       : noms des colonnes EXTRA dans la timeline
        extra_summary_df    : résumé des EXTRA par terminal
        extra_makeups_df    : CSV des EXTRA (Terminal, ExtraMakeupsNeeded)
    """
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

# ── 13. Calcul des KPIs et analytics ──────────────────────────────────────────

def _compute_kpis(flights_readjusted: pd.DataFrame, unassigned_df: pd.DataFrame) -> Dict[str, object]:
    """Calcule les KPIs de synthèse à afficher sur le dashboard.

    KPIs calculés :
        total_flights      : nombre total de vols
        assigned_pct       : % de vols assignés
        unassigned_count   : nombre de vols non assignés
        split_count        : nombre de vols splittés sur plusieurs carrousels
        split_pct          : % de vols splittés
        narrow_wide_count  : nombre de vols Narrow réassignés sur Wide
        narrow_wide_pct    : % de vols Narrow→Wide
    """
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
    """Calcule les données analytics détaillées pour les graphiques du dashboard.

    Sections calculées :
        terminal_distribution : nb de vols par terminal
        category_breakdown    : nb de vols assignés/non-assignés par catégorie
        peak_hours            : distribution des départs par heure
        carousel_breakdown    : nb de vols par carrousel et terminal
    """
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
    """Convertit un DataFrame en liste de dicts JSON-sérialisables.

    Les colonnes datetime sont formatées en chaîne "YYYY-MM-DD HH:MM:SS".
    Les valeurs NaN sont remplacées par "".
    limit : tronque à N lignes si fourni.
    """
    if df is None:
        return []
    out = df.copy()
    if limit is not None:
        out = out.head(int(limit))
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = out[col].dt.strftime("%Y-%m-%d %H:%M:%S")
    return out.fillna("").to_dict(orient="records")


# ── 14. Écriture des fichiers de sortie ───────────────────────────────────────

def _write_outputs(
    job_dir: Path,
    results: dict,
    keep_extra_cols: List[str],
    extra_caps_by_terminal: Dict[str, CarouselCapacity],
    carousels_mode: str,
    caps_manual: Dict[str, CarouselCapacity],
    caps_by_terminal: Dict[str, Dict[str, CarouselCapacity]],
) -> Dict[str, str]:
    """Écrit tous les fichiers de résultats dans le répertoire du job.

    Fichiers créés :
        summary.txt / summary.csv                 : résultats bruts de l'allocation
        summary_readjusted.txt / .csv             : résultats après réajustement
        timeline.xlsx                             : planning initial coloré
        timeline_readjusted.xlsx                  : planning après réajustement
        heatmap_positions_occupied.xlsx           : positions occupées
        heatmap_positions_free.xlsx               : positions libres
        extra_makeups_needed.csv                  : nb de zones EXTRA par terminal
        warnings.csv                              : liste des avertissements
        unassigned_reasons.csv                    : vols non assignés avec raison

    Retourne un dict {clé_download → nom_fichier} utilisé pour construire les URLs.
    """
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

# ── 15. Endpoints de l'outil d'allocation ─────────────────────────────────────

@app.get("/")
def root() -> RedirectResponse:
    """Redirige vers /app (frontend) si disponible, sinon vers /docs (Swagger)."""
    if FRONTEND_DIR.exists():
        return RedirectResponse(url="/app")
    return RedirectResponse(url="/docs")


@app.post("/api/preview")
def preview(
    request: Request,
    response: Response,
    file: Optional[UploadFile] = File(None),
):
    """Lit les premières lignes du fichier de vols et suggère le mapping de colonnes.

    Utilisé à l'étape 1 du wizard pour afficher l'aperçu et les suggestions.
    Si file est absent, utilise le fichier déjà uploadé dans la session.
    Retourne : colonnes, aperçu des 10 premières lignes, suggestions de mapping.
    """
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
    """Retourne les valeurs uniques de Category et Terminal après application du mapping de colonnes.

    Utilisé à l'étape 2 du wizard pour afficher les valeurs brutes à mapper.
    Requiert config_json avec au moins le mapping de colonnes.
    """
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

    print(f"[INSPECT] session_id={session_id[:8]}... file_uploaded={file is not None} record.file_path={record.file_path!r}")

    if file is not None:
        path = _save_session_file(session_id, file)
        df_raw = _read_excel_path(path)
    else:
        path = _get_session_file_path(record)
        print(f"[INSPECT] resolved path={path}")
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
    """Retourne l'état courant de la session (étape du wizard, paramètres, dernier job)."""
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
    """Sauvegarde l'état du wizard dans la session (étape courante et paramètres)."""
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
    """Valide et lit un fichier de configuration des carrousels (Excel/CSV).

    Détecte automatiquement les colonnes Terminal, CarouselName, WideCapacity, NarrowCapacity.
    Retourne la liste des carrousels détectés ou une liste d'erreurs si le fichier est invalide.
    """
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
    """Calcule les statistiques descriptives du fichier de vols AVANT allocation.

    Utilisé pour enrichir les analytics du job avec des données d'entrée :
    plage de dates, distribution par heure, par catégorie, par terminal.
    """
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
    """Lance un run d'allocation complet et retourne les résultats.

    Flux d'exécution :
      1. Parse la configuration JSON
      2. Lit le fichier Excel (uploadé ou depuis la session)
      3. Applique le mapping de colonnes, catégories, terminaux
      4. Calcule les fenêtres makeup si nécessaire
      5. Exécute le pipeline d'allocation (_run_allocation_pipeline)
      6. Écrit les fichiers de sortie (_write_outputs)
      7. Calcule les KPIs et analytics
      8. Persiste le job sur disque + Supabase

    Retourne le job complet avec KPIs, analytics, URLs de téléchargement, tables.
    scenario_name : nom optionnel pour identifier le run dans l'historique.
    """
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


# ── 16. Endpoints KPI personnalisés ───────────────────────────────────────────

@app.get("/api/kpis")
def list_custom_kpis():
    """Retourne la liste de tous les KPIs personnalisés triés par date de création."""
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
    """Crée un nouveau KPI personnalisé et le persiste sur disque."""
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
    """Supprime un KPI personnalisé par son ID."""
    if kpi_id not in CUSTOM_KPI_STORE:
        raise HTTPException(status_code=404, detail="KPI non trouve.")
    del CUSTOM_KPI_STORE[kpi_id]
    _save_custom_kpis_to_disk()
    return {"ok": True}


# ── 17. Endpoints admin ───────────────────────────────────────────────────────

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


# ── 18. Endpoints jobs ────────────────────────────────────────────────────────

@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: str):
    """Supprime un job : depuis Supabase, depuis le disque, et de la mémoire."""
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
    """Retourne la liste des jobs terminés, triés du plus récent au plus ancien."""
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
    """Retourne les détails complets d'un job (KPIs, analytics, warnings, downloads)."""
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
    """Télécharge un fichier de résultats d'un job (Excel, CSV, TXT).

    Le nom du fichier est sécurisé (Path().name) pour éviter les traversals.
    """
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
    """Prévisualise un fichier CSV de résultats (paginé).

    Disponible uniquement pour les fichiers .csv.
    limit/offset : pagination des lignes retournées.
    """
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


# ── 19. Outil de mapping ───────────────────────────────────────────────────────
#
# L'outil de mapping est une fonctionnalité DISTINCTE de l'allocation.
# Il permet de transformer un fichier Excel/CSV :
#   - Sélectionner/renommer des colonnes
#   - Calculer de nouvelles colonnes via des formules Excel-like (formula_engine.py)
#   - Filtrer les lignes (avec groupes AND/OR)
#   - Joindre des fichiers secondaires (LEFT JOIN)
#   - Dédupliquer par clé primaire avec agrégation
#
# Endpoints : /api/mapping/sheets, /api/mapping/columns, /api/mapping/preview, /api/mapping/execute

class MappingColumnDef(BaseModel):
    """Définition d'une colonne de sortie dans l'outil de mapping.

    target_name       : nom de la colonne dans le fichier de sortie
    source_col        : colonne source (si pas de formule)
    formula           : formule Excel-like (ex: =CONCATENER(A;B)) — prioritaire sur source_col
    is_pk             : si True, les lignes avec cette colonne vide sont exclues
    aggregation       : mode d'agrégation en cas de dédup (First, Sum, Count, Concat…)
    format            : format d'affichage pour les dates (Auto, Date, DateTime, Time)
    include_in_output : si False, la colonne est calculée mais pas incluse dans l'export
    """
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
    """Règle de filtre sur une colonne du fichier source ou de sortie.

    col : nom de la colonne
    op  : opérateur (=, <>, >, <, >=, <=, contains, not_contains, starts_with, ends_with, is_empty, is_not_empty)
    val : valeur de comparaison (ignorée pour is_empty/is_not_empty)
    """
    col: str
    op: str
    val: str = ""

    class Config:
        extra = "ignore"


class JoinConfig(BaseModel):
    """Configuration d'un LEFT JOIN avec un fichier secondaire.

    alias         : nom préfixe pour les colonnes du fichier secondaire (ex: "sec" → "sec.ColName")
    on_primary    : colonne de jointure dans le fichier principal
    on_secondary  : colonne de jointure dans le fichier secondaire
    sheet_name    : onglet Excel à lire (optionnel)
    skip_rows     : nombre de lignes à sauter en début de fichier
    """
    alias: str
    on_primary: str
    on_secondary: str
    sheet_name: Optional[str] = None
    skip_rows: int = 0

    class Config:
        extra = "ignore"


class FilterGroup(BaseModel):
    """Groupe de règles de filtre combinées par AND ou OR.

    Les groupes eux-mêmes sont toujours combinés entre eux par AND.
    Exemple : (A=1 OR B=2) AND (C>10) → deux groupes.
    """
    id: str = ""
    op: Literal["AND", "OR"] = "AND"
    rules: List[MappingFilterRule] = []

    class Config:
        extra = "ignore"


class MappingExecuteConfig(BaseModel):
    """Configuration complète d'un run de l'outil de mapping.

    columns              : liste des colonnes de sortie à calculer
    filter_groups        : filtres sur les données SOURCE (avant calcul des formules)
    filters              : filtres plats (rétrocompatibilité, utilisé si filter_groups vide)
    output_filter_groups : filtres sur les données DE SORTIE (après calcul, après dédup)
    output_filters       : filtres de sortie plats (rétrocompatibilité)
    dedup_by_pk          : si True, déduplique sur la colonne clé primaire (is_pk=True)
    output_format        : "csv" ou "excel"
    joins                : liste des LEFT JOINs avec fichiers secondaires
    sheet_name, skip_rows: options de lecture du fichier source
    """
    columns: List[MappingColumnDef]
    filters: List[MappingFilterRule] = []
    output_filters: List[MappingFilterRule] = []
    filter_groups: List[FilterGroup] = []
    output_filter_groups: List[FilterGroup] = []
    dedup_by_pk: bool = False
    output_format: Literal["csv", "excel"] = "csv"
    output_filename: str = "mapping_output.csv"
    joins: List[JoinConfig] = []
    sheet_name: Optional[str] = None
    skip_rows: int = 0

    class Config:
        extra = "ignore"


def _read_df_from_bytes(
    content: bytes,
    filename: str,
    *,
    sheet_name: Optional[str] = None,
    skip_rows: int = 0,
    nrows: Optional[int] = None,
) -> pd.DataFrame:
    """Lit un fichier (Excel ou CSV) depuis des bytes en mémoire.

    Supporte .csv, .xls et .xlsx. Utilisé pour le Mapping Tool qui reçoit
    les fichiers en mémoire sans les sauvegarder sur disque.
    """
    fn = (filename or "").lower()
    if fn.endswith(".csv"):
        return _read_csv_auto(content, nrows=nrows)
    buf = BytesIO(content)
    kwargs: dict = {}
    if sheet_name:
        kwargs["sheet_name"] = sheet_name
    if skip_rows:
        kwargs["skiprows"] = int(skip_rows)
    if nrows is not None:
        kwargs["nrows"] = nrows
    if fn.endswith(".xls"):
        return pd.read_excel(buf, engine="xlrd", **kwargs)
    return pd.read_excel(buf, engine="openpyxl", **kwargs)


from formula_engine import (
    _split_formula_args,
    _find_comparison_in_cond,
    _rfind_op_at_depth0,
    _eval_condition,
    _eval_mapping_formula,
)





def _get_filter_mask(df: pd.DataFrame, f: "MappingFilterRule") -> "pd.Series":
    """Calcule le masque booléen pour une règle de filtre sur un DataFrame.

    Retourne une Series de booléens (True = ligne conservée).
    Si la colonne n'existe pas → retourne True pour toutes les lignes (filtre ignoré).
    Pour les comparaisons numériques (>, <, >=, <=), utilise pd.to_numeric.
    Pour = et <>, tente la comparaison numérique d'abord, puis texte insensible à la casse.
    """
    if f.col not in df.columns:
        return pd.Series([True] * len(df), index=df.index)
    col = df[f.col]
    op, val = f.op, f.val
    try:
        if op == "=":
            try:
                return pd.to_numeric(col, errors="raise") == float(val)
            except Exception:
                return col.astype(str).str.lower() == val.lower()
        elif op == "<>":
            try:
                return pd.to_numeric(col, errors="raise") != float(val)
            except Exception:
                return col.astype(str).str.lower() != val.lower()
        elif op == ">":
            return pd.to_numeric(col, errors="coerce") > float(val)
        elif op == "<":
            return pd.to_numeric(col, errors="coerce") < float(val)
        elif op == ">=":
            return pd.to_numeric(col, errors="coerce") >= float(val)
        elif op == "<=":
            return pd.to_numeric(col, errors="coerce") <= float(val)
        elif op == "contains":
            return col.astype(str).str.contains(val, case=False, na=False)
        elif op == "not_contains":
            return ~col.astype(str).str.contains(val, case=False, na=False)
        elif op == "starts_with":
            return col.astype(str).str.startswith(val, na=False)
        elif op == "ends_with":
            return col.astype(str).str.endswith(val, na=False)
        elif op == "is_empty":
            return col.isna() | (col.astype(str).str.strip() == "")
        elif op == "is_not_empty":
            return col.notna() & (col.astype(str).str.strip() != "")
    except Exception:
        pass
    return pd.Series([True] * len(df), index=df.index)


def _apply_filters(df: pd.DataFrame, filters: list) -> pd.DataFrame:
    """Applique une liste plate de filtres (tous combinés par AND).

    Rétrocompatibilité : utilisé quand filter_groups est vide.
    """
    if not filters:
        return df
    mask = pd.Series([True] * len(df), index=df.index)
    for f in filters:
        mask &= _get_filter_mask(df, f)
    return df[mask].reset_index(drop=True)


def _apply_filter_groups(df: pd.DataFrame, groups: list) -> pd.DataFrame:
    """Applique des groupes de filtres sur un DataFrame.

    Au sein d'un groupe, les règles sont combinées par group.op (AND ou OR).
    Les groupes eux-mêmes sont toujours combinés entre eux par AND.
    """
    if not groups:
        return df
    mask = pd.Series([True] * len(df), index=df.index)
    for group in groups:
        if not group.rules:
            continue
        group_mask = _get_filter_mask(df, group.rules[0])
        for rule in group.rules[1:]:
            rule_mask = _get_filter_mask(df, rule)
            if group.op == "OR":
                group_mask = group_mask | rule_mask
            else:
                group_mask = group_mask & rule_mask
        mask = mask & group_mask
    return df[mask].reset_index(drop=True)


def _run_mapping(df_src: pd.DataFrame, config: "MappingExecuteConfig", secondary_dfs: Optional[Dict[str, "pd.DataFrame"]] = None) -> pd.DataFrame:
    """Exécute la transformation de mapping complète sur un DataFrame source.

    Étapes dans l'ordre :
      1. Filtres source (filter_groups ou filters) — filtre avant calcul
      2. LEFT JOINs avec les fichiers secondaires (préfixe "alias.ColName")
      3. Calcul des colonnes de sortie (formules, valeurs fixes ou colonnes source)
         Les colonnes déjà calculées sont disponibles pour les formules suivantes.
      4. Exclusion des lignes avec clé primaire vide (si is_pk=True sur une colonne)
      5. Déduplication sur la clé primaire avec agrégation (si dedup_by_pk=True)
      6. Filtres de sortie (output_filter_groups ou output_filters) — filtre après calcul

    Retourne le DataFrame de sortie (colonnes include_in_output=True uniquement).
    """
    if config.filter_groups:
        df_src = _apply_filter_groups(df_src, config.filter_groups)
    elif config.filters:
        df_src = _apply_filters(df_src, config.filters)

    # LEFT JOIN secondary files
    if secondary_dfs:
        for join in config.joins:
            df_sec = secondary_dfs.get(join.alias)
            if df_sec is None or join.on_primary not in df_src.columns or join.on_secondary not in df_sec.columns:
                continue
            df_sec_prefixed = df_sec.rename(columns={col: f"{join.alias}.{col}" for col in df_sec.columns})
            join_key_prefixed = f"{join.alias}.{join.on_secondary}"
            df_src = df_src.assign(**{join.on_primary: df_src[join.on_primary].astype(str)})
            df_sec_prefixed = df_sec_prefixed.assign(**{join_key_prefixed: df_sec_prefixed[join_key_prefixed].astype(str)})
            df_src = df_src.merge(df_sec_prefixed, left_on=join.on_primary, right_on=join_key_prefixed, how="left")
            if join_key_prefixed in df_src.columns:
                df_src = df_src.drop(columns=[join_key_prefixed])
        df_src = df_src.reset_index(drop=True)
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
    if config.output_filter_groups:
        df_out = _apply_filter_groups(df_out, config.output_filter_groups)
    elif config.output_filters:
        df_out = _apply_filters(df_out, config.output_filters)

    return df_out


@app.post("/api/mapping/sheets")
def mapping_get_sheets(file: UploadFile = File(...)):
    """Retourne la liste des onglets d'un fichier Excel. Retourne [] pour les CSV."""
    content = file.file.read()
    fn = (file.filename or "").lower()
    if fn.endswith(".csv"):
        return {"sheets": []}
    buf = BytesIO(content)
    try:
        xl = pd.ExcelFile(buf, engine="xlrd" if fn.endswith(".xls") else "openpyxl")
        return {"sheets": xl.sheet_names}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Cannot read file sheets: {exc}")


@app.post("/api/mapping/columns")
def mapping_get_columns(
    file: UploadFile = File(...),
    sheet_name: Optional[str] = Form(default=None),
    skip_rows: int = Form(default=0),
):
    """Retourne les colonnes et le nombre de lignes d'un fichier (pour le wizard de mapping)."""
    content = file.file.read()
    try:
        df = _read_df_from_bytes(
            content, file.filename or "",
            sheet_name=sheet_name or None,
            skip_rows=skip_rows,
        )
        return {"columns": list(df.columns), "row_count": len(df)}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Cannot read file: {exc}")


@app.post("/api/mapping/preview")
def mapping_preview(
    file: UploadFile = File(...),
    secondary_files: Optional[List[UploadFile]] = File(default=None),
    config_json: str = Form(...),
):
    """Exécute le mapping et retourne un aperçu des 100 premières lignes (sans téléchargement).

    Utilisé par le wizard de mapping pour prévisualiser le résultat avant export.
    secondary_files : fichiers secondaires pour les LEFT JOINs (dans l'ordre des joins).
    """
    try:
        config = MappingExecuteConfig(**json.loads(config_json))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid config: {exc}")

    content = file.file.read()
    try:
        df_src = _read_df_from_bytes(
            content, file.filename or "",
            sheet_name=config.sheet_name or None,
            skip_rows=config.skip_rows,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Cannot read file: {exc}")

    secondary_dfs: Dict[str, Any] = {}
    for i, sec_file in enumerate(secondary_files or []):
        if i < len(config.joins):
            try:
                join = config.joins[i]
                secondary_dfs[join.alias] = _read_df_from_bytes(
                    sec_file.file.read(), sec_file.filename or "",
                    sheet_name=join.sheet_name or None,
                    skip_rows=join.skip_rows,
                )
            except Exception:
                pass

    df_out = _run_mapping(df_src, config, secondary_dfs)
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
    secondary_files: Optional[List[UploadFile]] = File(default=None),
    config_json: str = Form(...),
):
    """Exécute le mapping complet et retourne le fichier de sortie en téléchargement.

    output_format "csv"   → retourne un fichier CSV (UTF-8 with BOM pour Excel).
    output_format "excel" → retourne un fichier .xlsx.
    secondary_files : fichiers secondaires pour les LEFT JOINs (dans l'ordre des joins).
    """
    try:
        config = MappingExecuteConfig(**json.loads(config_json))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid config: {exc}")

    content = file.file.read()
    try:
        df_src = _read_df_from_bytes(
            content, file.filename or "",
            sheet_name=config.sheet_name or None,
            skip_rows=config.skip_rows,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Cannot read file: {exc}")

    secondary_dfs: Dict[str, Any] = {}
    for i, sec_file in enumerate(secondary_files or []):
        if i < len(config.joins):
            try:
                join = config.joins[i]
                secondary_dfs[join.alias] = _read_df_from_bytes(
                    sec_file.file.read(), sec_file.filename or "",
                    sheet_name=join.sheet_name or None,
                    skip_rows=join.skip_rows,
                )
            except Exception:
                pass

    df_out = _run_mapping(df_src, config, secondary_dfs)

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
