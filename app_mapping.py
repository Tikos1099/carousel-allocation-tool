"""
app_mapping.py — Normalisation des catégories et terminaux du fichier de vols
==============================================================================

RÔLE DANS LE SYSTÈME
--------------------
Ce fichier prépare les données de vols AVANT l'allocation :
- Il traduit les valeurs brutes de la colonne "Category" (ex: "W", "WB", "WIDE BODY")
  vers les valeurs standards attendues par l'allocateur : "Wide" ou "Narrow".
- Il traduit les valeurs de la colonne "Terminal" vers les noms standards définis
  par l'utilisateur (ex: "TER1" → "T1"), ou les marque "IGNORER" pour les exclure.

Ce fichier est importé directement par api_app.py.

CE QUE FAIT CHAQUE FONCTION
----------------------------
- _norm(s)                          : normalise une chaîne (minuscules, sans accents) pour comparer sans casse
- _guess_col(cols, keywords)        : trouve dans une liste de colonnes celle qui correspond le mieux à des mots-clés
- suggest_cat(v)                    : suggère la catégorie standard ("Wide"/"Narrow") depuis une valeur brute
- suggest_term(v)                   : suggère le nom de terminal standardisé (ex: "TERMINAL 2" → "T2")
- _apply_cat_term_mapping(df, ...)  : applique les mappings category + terminal sur un DataFrame complet

POUR MODIFIER
-------------
- Ajouter un alias de catégorie (ex: "LH" → "Wide")  : modifier suggest_cat()
- Changer la logique de terminal                       : modifier suggest_term()
- Changer ce qui se passe avec les lignes ignorées     : modifier _apply_cat_term_mapping()
"""

from __future__ import annotations

import re
import unicodedata
import pandas as pd


# ---------------------------------------------------------------------------
# Helpers de normalisation de texte
# ---------------------------------------------------------------------------

def _norm(s: str) -> str:
    """Normalise une chaîne pour comparaison insensible à la casse et aux accents.

    Ex: "Héure Départ" → "heure depart"
    Utilisé par _guess_col pour faire des correspondances approximatives.
    """
    s = str(s).strip()
    # Supprime les accents (é → e, à → a, etc.)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = s.lower()
    # Réduit les espaces multiples à un seul
    s = re.sub(r"\s+", " ", s)
    return s


def _guess_col(cols: list, keywords: list) -> str | None:
    """Trouve dans une liste de colonnes celle dont le nom contient un des mots-clés.

    Parcourt les colonnes dans l'ordre des mots-clés (du plus prioritaire au moins).
    Retourne None si aucune correspondance.

    Exemple:
        _guess_col(["dep time", "flight no", "cat"], ["departure", "dep"])
        → "dep time"  (car "dep" est dans "dep time")
    """
    # Crée une map nom_original → nom_normalisé pour éviter de re-normaliser à chaque tour
    norm_map = {col: _norm(col) for col in cols}

    for keyword in keywords:
        for original_col, normalized_col in norm_map.items():
            if keyword in normalized_col:
                return original_col

    return None


# ---------------------------------------------------------------------------
# Suggestions automatiques (utilisées dans l'interface wizard)
# ---------------------------------------------------------------------------

def suggest_cat(v: str) -> str:
    """Suggère la catégorie standard depuis une valeur brute de la colonne Category.

    Retourne "Wide", "Narrow", ou "IGNORER" (pour exclure la ligne).

    Exemples:
        "Wide body" → "Wide"
        "WB"        → "Wide"
        "N"         → "Narrow"
        "XYZ"       → "IGNORER"
    """
    s = v.strip().lower()
    if "wide" in s or s in ("wb", "w"):
        return "Wide"
    if "narrow" in s or s in ("nb", "n"):
        return "Narrow"
    return "IGNORER"


def suggest_term(v: str) -> str:
    """Suggère le nom de terminal standardisé depuis une valeur brute.

    Cherche un numéro dans la chaîne et retourne "T{numéro}".

    Exemples:
        "T2"        → "T2"
        "Terminal 3"→ "T3"
        "2"         → "T2"
        "MAIN"      → "MAIN" (aucun numéro trouvé)
    """
    s = v.strip().upper()
    number_match = re.search(r"(\d+)", s)

    # Cas "T2", "T12", etc.
    if s.startswith("T") and len(s) >= 2 and s[1].isdigit():
        return "T" + re.search(r"\d+", s).group(0)

    # Cas "TERMINAL 2", "TERMINAL2"
    if "TERMINAL" in s and number_match:
        return "T" + number_match.group(1)

    # Cas numéro seul "2", "12"
    if number_match and len(number_match.group(1)) <= 2:
        return "T" + number_match.group(1)

    # Fallback : retourne tel quel ou "INCONNU" si vide
    return s if s else "INCONNU"


# ---------------------------------------------------------------------------
# Application du mapping catégorie + terminal sur le DataFrame
# ---------------------------------------------------------------------------

def _apply_cat_term_mapping(
    df: pd.DataFrame,
    cat_mapping: dict,
    term_mapping: dict,
) -> tuple[pd.DataFrame, list[dict]]:
    """Applique les mappings catégorie et terminal sur le DataFrame de vols.

    Paramètres:
        df           : DataFrame contenant au minimum les colonnes "Category" et optionnellement "Terminal"
        cat_mapping  : dict brut → standard, ex: {"W": "Wide", "WB": "Wide", "N": "Narrow"}
        term_mapping : dict brut → standard, ex: {"TER1": "T1", "IGNORE_THIS": "IGNORER"}

    Retourne:
        (df_filtré, warnings) où :
        - df_filtré : DataFrame sans les lignes marquées "IGNORER"
        - warnings  : liste de dicts décrivant les lignes ignorées (pour rapport)

    Règle "IGNORER" :
        - Category non trouvée dans cat_mapping → ligne supprimée
        - Terminal dont la valeur mappée est "IGNORER" → ligne supprimée
    """
    warnings = []
    df = df.copy()

    # ── Étape 1 : mapping des catégories ─────────────────────────────────────
    df["_CategoryStd"] = df["Category"].astype(str).str.strip().map(
        lambda raw: cat_mapping.get(raw, "IGNORER")
    )

    ignored_category_rows = df[df["_CategoryStd"] == "IGNORER"]
    if len(ignored_category_rows) > 0:
        warnings.append({
            "Type": "Category non mappee",
            "Message": "Lignes ignorees (Category non mappee)",
            "Count": int(len(ignored_category_rows)),
        })

    # Supprimer les lignes ignorées et appliquer la nouvelle catégorie
    df = df[df["_CategoryStd"] != "IGNORER"].copy()
    df["Category"] = df["_CategoryStd"]
    df = df.drop(columns=["_CategoryStd"])

    # ── Étape 2 : mapping des terminaux (optionnel) ────────────────────────
    if "Terminal" in df.columns and term_mapping:
        # Normaliser le mapping terminal : clés en MAJUSCULES, valeurs "IGNORER" ou MAJUSCULES
        normalized_term_map = {}
        for raw_key, raw_value in (term_mapping or {}).items():
            key = str(raw_key).strip().upper()
            if not key:
                continue
            value = str(raw_value).strip()
            if value.lower() in ("ignore", "ignorer", "ignored", "none", "null", "nan"):
                normalized_term_map[key] = "IGNORER"
            else:
                normalized_term_map[key] = value.strip().upper()

        df["_TerminalStd"] = (
            df["Terminal"].astype(str).str.strip().str.upper()
            .map(lambda raw: normalized_term_map.get(raw, "IGNORER"))
        )

        ignored_terminal_rows = df[df["_TerminalStd"] == "IGNORER"]
        if len(ignored_terminal_rows) > 0:
            warnings.append({
                "Type": "Terminal non mappe",
                "Message": "Lignes ignorees (Terminal non mappe)",
                "Count": int(len(ignored_terminal_rows)),
            })

        df = df[df["_TerminalStd"] != "IGNORER"].copy()
        df["Terminal"] = df["_TerminalStd"].astype(str).str.strip().str.upper()
        df = df.drop(columns=["_TerminalStd"])

    return df, warnings
