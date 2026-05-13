"""
allocator.py — Façade publique de l'outil d'allocation
=======================================================

RÔLE DANS LE SYSTÈME
--------------------
Ce fichier est le POINT D'ENTRÉE unique pour l'outil d'allocation.
Il n'a aucune logique propre : il re-exporte tout depuis allocator_engine.py.

Pourquoi ce fichier existe ?
    En important depuis "allocator" (ce fichier) plutôt que depuis "allocator_engine"
    directement, le reste du code (api_app.py, allocator_io.py) est découplé de
    l'organisation interne. Si on renomme ou réorganise allocator_engine.py un jour,
    on ne change que ce fichier — pas tous les imports ailleurs.

CE QUI EST EXPORTÉ
------------------
- CarouselCapacity                  : dataclass(wide, narrow) — capacité d'un carrousel
- allocate_round_robin              : allocation simple round-robin
- allocate_round_robin_with_rules   : allocation avec règles (multi, narrow→wide, extras)
- allocate_with_fixed_assignments   : réallocation avec vols fixes déjà assignés
- build_timeline_from_assignments   : construit le tableau chronologique des assignations
- compute_single_assignment_segments: calcule les segments de positions utilisées
- size_extra_makeups                : calcule le nombre de makeup zones supplémentaires nécessaires

POUR MODIFIER LA LOGIQUE D'ALLOCATION
--------------------------------------
Ouvrir allocator_engine.py — c'est là que se trouve tout le code.
"""

from __future__ import annotations

from allocator_engine import (
    CarouselCapacity,
    allocate_round_robin,
    allocate_round_robin_with_rules,
    allocate_with_fixed_assignments,
    build_timeline_from_assignments,
    compute_single_assignment_segments,
    size_extra_makeups,
)

__all__ = [
    "CarouselCapacity",
    "allocate_round_robin",
    "allocate_round_robin_with_rules",
    "allocate_with_fixed_assignments",
    "build_timeline_from_assignments",
    "compute_single_assignment_segments",
    "size_extra_makeups",
]
