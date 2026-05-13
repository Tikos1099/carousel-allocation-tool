"""
formula_engine.py — Moteur d'évaluation des formules Excel-like
================================================================

RÔLE DANS LE SYSTÈME
--------------------
Ce fichier évalue des formules de type Excel sur un DataFrame pandas.
Chaque formule est évaluée LIGNE PAR LIGNE et retourne une pd.Series
(une valeur calculée pour chaque ligne du fichier source).

Il est utilisé par l'outil Mapping pour calculer les colonnes de sortie.
Importé directement depuis api_app.py.

PRINCIPE DE FONCTIONNEMENT
--------------------------
L'évaluation est 100% RÉCURSIVE : chaque fonction évalue ses arguments
en rappelant _eval_mapping_formula(). Cela permet les imbrications arbitraires :
    LEFT(RIGHT(ColA, 5), 2)
    IF(ISBLANK(Col), "vide", UPPER(Col))
    IFERROR(INDEX(Col, MATCH(A&B, ColRef, 0)), "")

FONCTIONS PUBLIQUES
-------------------
_split_formula_args(s)          : découpe les arguments d'une formule (gère guillemets + parenthèses imbriquées)
_find_comparison_in_cond(s)     : trouve le premier opérateur de comparaison (>=, <=, =, etc.) à profondeur 0
_rfind_op_at_depth0(expr, ops)  : trouve le dernier opérateur arithmétique à profondeur 0
_eval_condition(cond, df)       : évalue une condition booléenne → pd.Series de bool
_eval_mapping_formula(expr, df) : évalue une formule quelconque → pd.Series de valeurs

SÉPARATEUR ";" (Excel FR/BE)
----------------------------
Le moteur accepte le ";" comme séparateur d'arguments (style Excel français).
Il est normalisé en "," au début de _eval_mapping_formula.
Exemple : =SI(A>0;"oui";"non")  ←→  =IF(A>0,"oui","non")

ALIASES FRANÇAIS RECONNUS
--------------------------
SI=IF · ALEA=RAND · EQUIV=MATCH · RECHERCHEV=VLOOKUP · CHOISIR=CHOOSE
SOMME=SUM · MOYENNE=AVERAGE · PUISSANCE=POWER · SI.CONDITIONS=IFS
ALEA.ENTRE.BORNES=RANDBETWEEN

FONCTIONS DISPONIBLES PAR CATÉGORIE
------------------------------------
Texte    : LEFT, RIGHT, MID, LEN, UPPER, LOWER, TRIM, FIND, SEARCH,
           TEXTBEFORE, TEXTAFTER, SUBSTITUTE, CONCAT, &
Nombre   : VALUE, ROUND, INT, ABS, MOD, POWER, SQRT, MIN, MAX, SUM, AVERAGE
Dates    : DATE, TODAY, NOW, YEAR, MONTH, DAY, HOUR, MINUTE, SECOND,
           DATEADD, DATEDIFF, TEXT, DATEVALUE, TIMEVALUE
Temps    : TIMETOMIN, TIMETOHOUR, TIMETOSEC
Cond.    : IF, IFS, AND, OR, NOT, IFERROR, IFNA, ISBLANK, ISNUMBER, ISTEXT
Lookup   : VLOOKUP, MATCH, INDEX
Divers   : LET, CHOOSE, RAND, RANDBETWEEN, COALESCE, ROW

POUR AJOUTER UNE NOUVELLE FONCTION
------------------------------------
1. Ajouter un bloc `m = re.match(r'^NOM_FONCTION\((.+)\)$', expr, re.IGNORECASE)`
   dans _eval_mapping_formula, à l'endroit logique (section texte, nombre, etc.)
2. Évaluer les arguments avec `_eval_mapping_formula(args[i], df)` (récursif)
3. Retourner une pd.Series de même longueur que df
"""

from __future__ import annotations

import re
from typing import Any, Optional

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Helpers de parsing : découper les arguments d'une formule
# ---------------------------------------------------------------------------

def _split_formula_args(s: str) -> list:
    """Découpe les arguments d'une formule en respectant parenthèses et guillemets.

    Exemple :
        _split_formula_args('LEFT(Col,3), "hello, world", IF(A>0,1,0)')
        → ['LEFT(Col,3)', '"hello, world"', 'IF(A>0,1,0)']

    Le "," à l'intérieur des parenthèses ou entre guillemets ne coupe PAS.
    """
    args: list = []
    depth = 0           # profondeur de parenthèses imbriquées
    in_quote = False    # sommes-nous à l'intérieur d'une chaîne entre guillemets ?
    quote_char = ""     # quel guillemet ouvre la chaîne courante ('"' ou "'")
    current: list = []  # caractères de l'argument en cours

    for char in s:
        if char in ('"', "'") and not in_quote:
            in_quote, quote_char = True, char
            current.append(char)
        elif char == quote_char and in_quote:
            in_quote = False
            current.append(char)
        elif char == "(" and not in_quote:
            depth += 1
            current.append(char)
        elif char == ")" and not in_quote:
            depth -= 1
            current.append(char)
        elif char == "," and depth == 0 and not in_quote:
            # virgule à profondeur 0 = séparateur d'argument
            args.append("".join(current).strip())
            current = []
        else:
            current.append(char)

    if current:
        args.append("".join(current).strip())

    return args


def _find_comparison_in_cond(s: str) -> Optional[tuple]:
    """Trouve le premier opérateur de comparaison à profondeur 0 (hors parenthèses et guillemets).

    Retourne (op, côté_gauche, côté_droit) ou None si aucun opérateur trouvé.
    Les opérateurs sont vérifiés du plus long au plus court pour éviter les faux positifs
    (ex: ">=" avant ">").

    Exemple :
        _find_comparison_in_cond("LEFT(Col,2)>='AB'")
        → (">=", "LEFT(Col,2)", "'AB'")
    """
    ops = (">=", "<=", "<>", "!=", ">", "<", "=")
    in_quote = False
    quote_char = ""
    depth = 0
    i = 0

    while i < len(s):
        char = s[i]
        if char in ('"', "'") and not in_quote:
            in_quote, quote_char = True, char
        elif char == quote_char and in_quote:
            in_quote = False
        elif char == "(" and not in_quote:
            depth += 1
        elif char == ")" and not in_quote:
            depth -= 1
        elif depth == 0 and not in_quote:
            for op in ops:
                if s[i:i + len(op)] == op:
                    return op, s[:i].strip(), s[i + len(op):].strip()
        i += 1

    return None


def _rfind_op_at_depth0(expr: str, ops: tuple) -> Optional[tuple]:
    """Trouve le DERNIER opérateur de `ops` à profondeur 0, à une position > 0.

    Utilisé pour l'arithmétique (priorité des opérations) : on cherche l'opérateur
    le plus à droite pour évaluer de gauche à droite.

    Retourne (op, gauche, droite) ou None.

    Exemple :
        _rfind_op_at_depth0("A+B+C", ("+", "-"))
        → ("+", "A+B", "C")  ← dernier "+"
    """
    in_quote = False
    quote_char = ""
    depth = 0
    last_pos: Optional[int] = None
    last_op: Optional[str] = None
    i = 0

    while i < len(expr):
        char = expr[i]
        if char in ('"', "'") and not in_quote:
            in_quote, quote_char = True, char
        elif char == quote_char and in_quote:
            in_quote = False
        elif char == "(" and not in_quote:
            depth += 1
        elif char == ")" and not in_quote:
            depth -= 1
        elif depth == 0 and not in_quote and i > 0:
            for op in ops:
                if expr[i:i + len(op)] == op:
                    last_pos, last_op = i, op
                    break
        i += 1

    if last_pos is not None and last_op is not None:
        return last_op, expr[:last_pos].strip(), expr[last_pos + len(last_op):].strip()

    return None


# ---------------------------------------------------------------------------
# Évaluation des conditions booléennes
# ---------------------------------------------------------------------------

def _eval_condition(cond: str, df: pd.DataFrame) -> "pd.Series":
    """Évalue une condition et retourne une pd.Series de booléens (une valeur par ligne).

    Gère :
    - AND(cond1, cond2, ...) / OR(...) / NOT(...)
    - Comparaisons : Col="val", LEFT(Col,3)>="X", etc.
    - Fonctions booléennes : ISBLANK(Col), ISNUMBER(Col), ISTEXT(Col)

    Note sur les comparaisons numériques :
        Si le côté droit est numérique, la comparaison se fait en numérique.
        Si le côté droit est une chaîne entre guillemets, comparaison en texte.
        Cela évite les bugs du type "0.5 < 'nan'" = True.
    """
    cond = cond.strip()
    n = len(df)

    # ── AND(cond1, cond2, ...) ────────────────────────────────────────────
    m = re.match(r'^AND\((.+)\)$', cond, re.IGNORECASE | re.DOTALL)
    if m:
        parts = _split_formula_args(m.group(1))
        result: "pd.Series" = pd.Series([True] * n)
        for part in parts:
            result = result & _eval_condition(part.strip(), df)
        return result.reset_index(drop=True)

    # ── OR(cond1, cond2, ...) ─────────────────────────────────────────────
    m = re.match(r'^OR\((.+)\)$', cond, re.IGNORECASE | re.DOTALL)
    if m:
        parts = _split_formula_args(m.group(1))
        result = pd.Series([False] * n)
        for part in parts:
            result = result | _eval_condition(part.strip(), df)
        return result.reset_index(drop=True)

    # ── NOT(cond) ─────────────────────────────────────────────────────────
    m = re.match(r'^NOT\((.+)\)$', cond, re.IGNORECASE | re.DOTALL)
    if m:
        return (~_eval_condition(m.group(1).strip(), df)).reset_index(drop=True)

    # ── Comparaison (Col >= "val", LEFT(Col,3) > "X", etc.) ──────────────
    # _find_comparison_in_cond ignore les opérateurs à l'intérieur des parenthèses
    found = _find_comparison_in_cond(cond)
    if found:
        op_str, left_expr, right_expr = found

        try:
            left_series = _eval_mapping_formula(left_expr, df)
        except Exception:
            left_series = pd.Series([left_expr] * n)

        # Déterminer la valeur du côté droit et le type de comparaison
        if (right_expr.startswith('"') and right_expr.endswith('"')) or \
           (right_expr.startswith("'") and right_expr.endswith("'")):
            # Côté droit = chaîne littérale entre guillemets → comparaison texte
            raw_str = right_expr[1:-1]
            if pd.api.types.is_datetime64_any_dtype(left_series):
                try:
                    right_value: Any = pd.to_datetime(raw_str)
                except Exception:
                    right_value = raw_str
                    left_series = left_series.astype(str)
            else:
                right_value = raw_str
                left_series = left_series.astype(str)
        else:
            try:
                # Côté droit = nombre → comparaison numérique
                rv = float(right_expr)
                right_value = int(rv) if rv == int(rv) else rv
                left_series = pd.to_numeric(left_series, errors="coerce")
            except ValueError:
                try:
                    # Côté droit = autre formule → évaluer récursivement
                    right_value = _eval_mapping_formula(right_expr, df)
                    # Préférer la comparaison numérique quand possible
                    # (évite les faux positifs du type "0.5 < 'nan' = True")
                    right_numeric = pd.to_numeric(right_value, errors="coerce")
                    left_numeric = pd.to_numeric(left_series, errors="coerce")
                    if right_numeric.notna().any():
                        right_value = right_numeric
                        left_series = left_numeric
                    else:
                        left_series = left_series.astype(str)
                        right_value = right_value.astype(str)
                except Exception:
                    right_value = right_expr
                    left_series = left_series.astype(str)

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
            return ops_map[op_str](left_series, right_value).reset_index(drop=True)
        except Exception:
            return pd.Series([False] * n)

    # ── Fonction booléenne (ISBLANK, ISNUMBER, ISTEXT, etc.) ─────────────
    # Si la condition n'est pas une comparaison, on l'évalue comme formule
    # et on caste le résultat en bool.
    # IMPORTANT : retourner [False]*n et non [True]*n en cas d'échec,
    # pour éviter que les IF avec condition inconnue se comportent comme "toujours vrai".
    try:
        result = _eval_mapping_formula(cond, df)
        return result.astype(bool).reset_index(drop=True)
    except Exception:
        pass

    return pd.Series([False] * n)


# ---------------------------------------------------------------------------
# Évaluation principale des formules
# ---------------------------------------------------------------------------

def _eval_mapping_formula(expr: str, df: pd.DataFrame) -> pd.Series:
    """Évalue une expression de formule sur toutes les lignes du DataFrame.

    Retourne une pd.Series de longueur len(df).

    Cette fonction est récursive : chaque fonction appelle _eval_mapping_formula
    pour évaluer ses propres arguments. Les formules imbriquées sont ainsi
    supportées à profondeur arbitraire.

    Ordre d'évaluation :
    1. Normalisation des ";" en ","
    2. Cas simples : constante vide, chaîne littérale, nombre, colonne directe
    3. Parenthèses englobantes → strippées
    4. Fonctions texte (LEFT, RIGHT, MID, ...)
    5. Fonctions numériques (VALUE, ROUND, INT, ...)
    6. Fonctions de condition (IF, IFERROR, ISBLANK, ...)
    7. Fonctions de date/temps
    8. Fonctions lookup (MATCH, INDEX, VLOOKUP)
    9. Fonctions spéciales (LET, CHOOSE, COALESCE, CONCAT, ROW)
    10. Opérateur de concaténation &
    11. Arithmétique (+, -, *, /)
    """

    # ── Étape 1 : normaliser les ";" → "," (style Excel FR/BE) ────────────
    # On ne remplace que les ";" qui NE sont PAS à l'intérieur de guillemets.
    normalized_chars: list = []
    in_quote = False
    quote_char = ""

    for char in expr:
        if char in ('"', "'") and not in_quote:
            in_quote = True
            quote_char = char
            normalized_chars.append(char)
        elif char == quote_char and in_quote:
            in_quote = False
            normalized_chars.append(char)
        elif char == ";" and not in_quote:
            normalized_chars.append(",")  # remplace ";" par ","
        else:
            normalized_chars.append(char)

    expr = "".join(normalized_chars).strip()
    n = len(df)
    empty: pd.Series = pd.Series([""] * n, dtype=object)

    if not expr:
        return empty

    # ── Étape 2a : constante chaîne (entre guillemets) ────────────────────
    if (expr.startswith('"') and expr.endswith('"')) or (expr.startswith("'") and expr.endswith("'")):
        return pd.Series([expr[1:-1]] * n)

    # ── Étape 2b : constante numérique ────────────────────────────────────
    try:
        val = float(expr)
        v: Any = int(val) if val == int(val) else val
        return pd.Series([v] * n)
    except (ValueError, TypeError):
        pass

    # ── Étape 2c : référence directe à une colonne ────────────────────────
    if expr in df.columns:
        return df[expr].reset_index(drop=True)

    # ── Étape 3 : expression entre parenthèses englobantes ────────────────
    # Ex: (Col1 + Col2)  →  strip les parens et réévalue
    if expr.startswith("(") and expr.endswith(")"):
        paren_depth = 0
        fully_wrapped = True
        for i, char in enumerate(expr):
            if char == "(":
                paren_depth += 1
            elif char == ")":
                paren_depth -= 1
            if paren_depth == 0 and i < len(expr) - 1:
                fully_wrapped = False
                break
        if fully_wrapped:
            return _eval_mapping_formula(expr[1:-1], df)

    # =========================================================================
    # FONCTIONS TEXTE
    # Chaque bloc : re.match détecte la fonction, _split_formula_args découpe
    # les arguments, _eval_mapping_formula évalue chaque argument récursivement.
    # =========================================================================

    # ── LEFT(texte, nb_caractères) ────────────────────────────────────────
    m = re.match(r'^LEFT\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        if len(args) == 2:
            src = _eval_mapping_formula(args[0].strip(), df).astype(str)
            k_series = pd.to_numeric(_eval_mapping_formula(args[1].strip(), df), errors="coerce").fillna(0)
            return pd.Series([s[:int(k)] for s, k in zip(src, k_series)]).reset_index(drop=True)

    # ── RIGHT(texte, nb_caractères) ───────────────────────────────────────
    m = re.match(r'^RIGHT\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        if len(args) == 2:
            src = _eval_mapping_formula(args[0].strip(), df).astype(str)
            k_series = pd.to_numeric(_eval_mapping_formula(args[1].strip(), df), errors="coerce").fillna(0)
            return pd.Series([s[-int(k):] if int(k) > 0 else "" for s, k in zip(src, k_series)]).reset_index(drop=True)

    # ── MID(texte, position_départ, longueur) ─────────────────────────────
    m = re.match(r'^MID\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        if len(args) == 3:
            src = _eval_mapping_formula(args[0].strip(), df).astype(str)
            start_series = pd.to_numeric(_eval_mapping_formula(args[1].strip(), df), errors="coerce").fillna(1)
            len_series = pd.to_numeric(_eval_mapping_formula(args[2].strip(), df), errors="coerce").fillna(0)
            return pd.Series([
                x[int(s) - 1:int(s) - 1 + int(ln)]
                for x, s, ln in zip(src, start_series, len_series)
            ]).reset_index(drop=True)

    # ── LEN(texte) ────────────────────────────────────────────────────────
    m = re.match(r'^LEN\((.+)\)$', expr, re.IGNORECASE)
    if m:
        src = _eval_mapping_formula(m.group(1).strip(), df)
        return src.astype(str).str.len().reset_index(drop=True)

    # ── UPPER(texte) ──────────────────────────────────────────────────────
    m = re.match(r'^UPPER\((.+)\)$', expr, re.IGNORECASE)
    if m:
        src = _eval_mapping_formula(m.group(1).strip(), df)
        return src.astype(str).str.upper().reset_index(drop=True)

    # ── LOWER(texte) ──────────────────────────────────────────────────────
    m = re.match(r'^LOWER\((.+)\)$', expr, re.IGNORECASE)
    if m:
        src = _eval_mapping_formula(m.group(1).strip(), df)
        return src.astype(str).str.lower().reset_index(drop=True)

    # ── TRIM(texte) ───────────────────────────────────────────────────────
    m = re.match(r'^TRIM\((.+)\)$', expr, re.IGNORECASE)
    if m:
        src = _eval_mapping_formula(m.group(1).strip(), df)
        return src.astype(str).str.strip().reset_index(drop=True)

    # ── TEXTBEFORE(texte, délimiteur) ─────────────────────────────────────
    m = re.match(r'^TEXTBEFORE\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        if len(args) >= 2:
            src = _eval_mapping_formula(args[0].strip(), df).astype(str)
            delim_series = _eval_mapping_formula(args[1].strip(), df).astype(str)
            return pd.Series([
                x.split(d)[0] if d in x else x
                for x, d in zip(src, delim_series)
            ]).reset_index(drop=True)

    # ── TEXTAFTER(texte, délimiteur) ──────────────────────────────────────
    m = re.match(r'^TEXTAFTER\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        if len(args) >= 2:
            src = _eval_mapping_formula(args[0].strip(), df).astype(str)
            delim_series = _eval_mapping_formula(args[1].strip(), df).astype(str)
            return pd.Series([
                d.join(x.split(d)[1:]) if d in x else x
                for x, d in zip(src, delim_series)
            ]).reset_index(drop=True)

    # ── SUBSTITUTE(texte, ancien, nouveau[, instance]) ────────────────────
    m = re.match(r'^SUBSTITUTE\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        if len(args) >= 3:
            src = _eval_mapping_formula(args[0].strip(), df).astype(str)
            old_series = _eval_mapping_formula(args[1].strip(), df).astype(str)
            new_series = _eval_mapping_formula(args[2].strip(), df).astype(str)
            return pd.Series([
                x.replace(old, new)
                for x, old, new in zip(src, old_series, new_series)
            ]).reset_index(drop=True)

    # ── FIND(texte_cherché, dans_texte[, position_départ]) ────────────────
    # Retourne la position 1-based (case-sensitive), NaN si non trouvé
    m = re.match(r'^FIND\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        if len(args) >= 2:
            find_series = _eval_mapping_formula(args[0].strip(), df).astype(str)
            within_series = _eval_mapping_formula(args[1].strip(), df).astype(str)
            start_series = (
                pd.to_numeric(_eval_mapping_formula(args[2].strip(), df), errors="coerce").fillna(1)
                if len(args) >= 3
                else pd.Series([1] * n)
            )

            def _find_pos(needle, haystack, start):
                try:
                    pos = haystack.find(needle, int(start) - 1)
                    return pos + 1 if pos >= 0 else float("nan")
                except Exception:
                    return float("nan")

            return pd.Series([
                _find_pos(f, w, s)
                for f, w, s in zip(find_series, within_series, start_series)
            ]).reset_index(drop=True)

    # ── SEARCH(texte_cherché, dans_texte[, position_départ]) ──────────────
    # Identique à FIND mais insensible à la casse
    m = re.match(r'^SEARCH\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        if len(args) >= 2:
            find_series = _eval_mapping_formula(args[0].strip(), df).astype(str)
            within_series = _eval_mapping_formula(args[1].strip(), df).astype(str)
            start_series = (
                pd.to_numeric(_eval_mapping_formula(args[2].strip(), df), errors="coerce").fillna(1)
                if len(args) >= 3
                else pd.Series([1] * n)
            )

            def _search_pos(needle, haystack, start):
                try:
                    pos = haystack.lower().find(needle.lower(), int(start) - 1)
                    return pos + 1 if pos >= 0 else float("nan")
                except Exception:
                    return float("nan")

            return pd.Series([
                _search_pos(f, w, s)
                for f, w, s in zip(find_series, within_series, start_series)
            ]).reset_index(drop=True)

    # =========================================================================
    # FONCTIONS NUMÉRIQUES
    # =========================================================================

    # ── VALUE(texte) → convertit texte en nombre ──────────────────────────
    m = re.match(r'^VALUE\((.+)\)$', expr, re.IGNORECASE)
    if m:
        src = _eval_mapping_formula(m.group(1).strip(), df)
        return pd.to_numeric(src, errors="coerce").reset_index(drop=True)

    # ── ROUND(nombre, décimales) ──────────────────────────────────────────
    m = re.match(r'^ROUND\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        if len(args) == 2:
            src = pd.to_numeric(_eval_mapping_formula(args[0].strip(), df), errors="coerce")
            dec_series = pd.to_numeric(_eval_mapping_formula(args[1].strip(), df), errors="coerce").fillna(0)
            if dec_series.nunique() == 1:
                return src.round(int(dec_series.iloc[0])).reset_index(drop=True)
            return pd.Series([
                round(v, int(d)) if pd.notna(v) else v
                for v, d in zip(src, dec_series)
            ]).reset_index(drop=True)

    # ── INT(nombre) → arrondi vers le bas ─────────────────────────────────
    m = re.match(r'^INT\((.+)\)$', expr, re.IGNORECASE)
    if m:
        src = pd.to_numeric(_eval_mapping_formula(m.group(1).strip(), df), errors="coerce")
        return src.apply(lambda x: int(x) if pd.notna(x) else "").reset_index(drop=True)

    # ── ABS(nombre) ───────────────────────────────────────────────────────
    m = re.match(r'^ABS\((.+)\)$', expr, re.IGNORECASE)
    if m:
        src = pd.to_numeric(_eval_mapping_formula(m.group(1).strip(), df), errors="coerce")
        return src.abs().reset_index(drop=True)

    # =========================================================================
    # FONCTIONS DE CONDITION / INSPECTION
    # =========================================================================

    # ── IFERROR(formule, valeur_si_erreur) ───────────────────────────────
    m = re.match(r'^IFERROR\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        if len(args) == 2:
            try:
                result = _eval_mapping_formula(args[0].strip(), df)
            except Exception:
                result = pd.Series([""] * n, dtype=object)
            fallback = _eval_mapping_formula(args[1].strip(), df)
            # Remplace les NaN et "nan" par le fallback
            combined = result.where(result.notna() & (result.astype(str) != "nan"), other=fallback)
            return combined.reset_index(drop=True)

    # ── ISNUMBER(valeur) → True si convertible en nombre ──────────────────
    m = re.match(r'^ISNUMBER\((.+)\)$', expr, re.IGNORECASE)
    if m:
        src = _eval_mapping_formula(m.group(1).strip(), df)
        return pd.to_numeric(src, errors="coerce").notna().reset_index(drop=True)

    # ── ISBLANK(valeur) → True si vide ou NaN ─────────────────────────────
    m = re.match(r'^ISBLANK\((.+)\)$', expr, re.IGNORECASE)
    if m:
        src = _eval_mapping_formula(m.group(1).strip(), df)
        return (src.isna() | (src.astype(str).str.strip() == "")).reset_index(drop=True)

    # ── ISTEXT(valeur) → True si non-numérique et non-vide ───────────────
    m = re.match(r'^ISTEXT\((.+)\)$', expr, re.IGNORECASE)
    if m:
        src = _eval_mapping_formula(m.group(1).strip(), df)
        return (pd.to_numeric(src, errors="coerce").isna() & src.notna()).reset_index(drop=True)

    # =========================================================================
    # FONCTIONS DE DATE ET TEMPS
    # =========================================================================

    # ── DATE(année, mois, jour) ───────────────────────────────────────────
    m = re.match(r'^DATE\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        if len(args) == 3:
            year_series = pd.to_numeric(_eval_mapping_formula(args[0].strip(), df), errors="coerce")
            month_series = pd.to_numeric(_eval_mapping_formula(args[1].strip(), df), errors="coerce")
            day_series = pd.to_numeric(_eval_mapping_formula(args[2].strip(), df), errors="coerce")

            def _make_timestamp(yr, mn, dy):
                try:
                    return pd.Timestamp(int(yr), int(mn), int(dy))
                except Exception:
                    return pd.NaT

            return pd.Series([
                _make_timestamp(yr, mn, dy)
                for yr, mn, dy in zip(year_series, month_series, day_series)
            ]).reset_index(drop=True)

    # ── TODAY() ───────────────────────────────────────────────────────────
    if re.match(r'^TODAY\(\)$', expr, re.IGNORECASE):
        return pd.Series([pd.Timestamp.today().normalize()] * n)

    # ── NOW() ─────────────────────────────────────────────────────────────
    if re.match(r'^NOW\(\)$', expr, re.IGNORECASE):
        return pd.Series([pd.Timestamp.now()] * n)

    # ── YEAR/MONTH/DAY/HOUR/MINUTE/SECOND(date_ou_heure) ─────────────────
    m = re.match(r'^(YEAR|MONTH|DAY|HOUR|MINUTE|SECOND)\((.+)\)$', expr, re.IGNORECASE)
    if m:
        fn_name = m.group(1).upper()
        src_eval = _eval_mapping_formula(m.group(2).strip(), df)

        # Cas timedelta (durée) pour HOUR/MINUTE/SECOND
        if pd.api.types.is_timedelta64_dtype(src_eval) and fn_name in ("HOUR", "MINUTE", "SECOND"):
            total_secs = src_eval.dt.total_seconds()
            if fn_name == "HOUR":   return (total_secs // 3600).reset_index(drop=True)
            if fn_name == "MINUTE": return ((total_secs % 3600) // 60).reset_index(drop=True)
            if fn_name == "SECOND": return (total_secs % 60).reset_index(drop=True)

        # Cas fraction Excel (0.0–1.0 = heure de la journée) pour HOUR/MINUTE/SECOND
        if pd.api.types.is_numeric_dtype(src_eval) and fn_name in ("HOUR", "MINUTE", "SECOND"):
            total_secs = src_eval % 1 * 86400
            if fn_name == "HOUR":   return (total_secs // 3600).reset_index(drop=True)
            if fn_name == "MINUTE": return ((total_secs % 3600) // 60).reset_index(drop=True)
            if fn_name == "SECOND": return (total_secs % 60).reset_index(drop=True)

        # Conversion vers datetime
        if pd.api.types.is_datetime64_any_dtype(src_eval):
            src_dt = src_eval
        elif pd.api.types.is_timedelta64_dtype(src_eval):
            src_dt = pd.Timestamp("2000-01-01") + src_eval
        else:
            def _coerce_to_datetime(x):
                try:
                    if x is None or (not hasattr(x, 'hour') and pd.isna(x)):
                        return pd.NaT
                    if hasattr(x, 'hour') and hasattr(x, 'minute'):
                        return pd.Timestamp(2000, 1, 1, x.hour, x.minute, getattr(x, 'second', 0))
                    if hasattr(x, 'total_seconds'):
                        secs = float(x.total_seconds())
                        return pd.Timestamp(2000, 1, 1, int(secs // 3600), int(secs % 3600 // 60), int(secs % 60))
                    return pd.to_datetime(x, errors='coerce')
                except Exception:
                    return pd.NaT
            src_dt = src_eval.apply(_coerce_to_datetime)

        parts_map = {
            "YEAR": src_dt.dt.year, "MONTH": src_dt.dt.month, "DAY": src_dt.dt.day,
            "HOUR": src_dt.dt.hour, "MINUTE": src_dt.dt.minute, "SECOND": src_dt.dt.second,
        }
        return parts_map[fn_name].reset_index(drop=True)

    # ── DATEVALUE(texte) → date sans heure ───────────────────────────────
    m = re.match(r'^DATEVALUE\((.+)\)$', expr, re.IGNORECASE)
    if m:
        src = _eval_mapping_formula(m.group(1).strip(), df)
        return pd.to_datetime(src, errors="coerce").dt.normalize().reset_index(drop=True)

    # ── TIMEVALUE(texte) → fraction de journée (0.0–1.0) ─────────────────
    m = re.match(r'^TIMEVALUE\((.+)\)$', expr, re.IGNORECASE)
    if m:
        src = _eval_mapping_formula(m.group(1).strip(), df)
        dt_series = pd.to_datetime(src, errors="coerce")
        return (
            (dt_series.dt.hour * 3600 + dt_series.dt.minute * 60 + dt_series.dt.second) / 86400.0
        ).reset_index(drop=True)

    # ── TEXT(date, "format") → formate une date en texte ──────────────────
    m = re.match(r'^TEXT\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        if len(args) == 2:
            src = _eval_mapping_formula(args[0].strip(), df)
            fmt_raw = args[1].strip().strip("\"'")
            # Convertit le format Excel (yyyy, MM, dd...) en format Python (%Y, %m, %d...)
            py_chars: list = []
            fi = 0
            while fi < len(fmt_raw):
                if fmt_raw[fi:fi+4] == "yyyy":          py_chars.append("%Y"); fi += 4
                elif fmt_raw[fi:fi+2] == "yy":          py_chars.append("%y"); fi += 2
                elif fmt_raw[fi:fi+2] == "MM":          py_chars.append("%m"); fi += 2
                elif fmt_raw[fi:fi+2] == "dd":          py_chars.append("%d"); fi += 2
                elif fmt_raw[fi:fi+2] in ("HH", "hh"): py_chars.append("%H"); fi += 2
                elif fmt_raw[fi:fi+2] == "mm":          py_chars.append("%M"); fi += 2
                elif fmt_raw[fi:fi+2] == "ss":          py_chars.append("%S"); fi += 2
                else:                                    py_chars.append(fmt_raw[fi]); fi += 1
            py_fmt = "".join(py_chars)
            return pd.to_datetime(src, errors="coerce").dt.strftime(py_fmt).reset_index(drop=True)

    # ── DATEADD(date, n, "unité") → ajoute une durée à une date ──────────
    m = re.match(r'^DATEADD\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        if len(args) == 3:
            dt_series = pd.to_datetime(_eval_mapping_formula(args[0].strip(), df), errors="coerce")
            n_series = pd.to_numeric(_eval_mapping_formula(args[1].strip(), df), errors="coerce").fillna(0)
            unit_str = args[2].strip().strip("\"'").lower()
            # Mapping des unités Excel vers unités pandas timedelta
            unit_map = {
                "day": "D", "days": "D", "d": "D",
                "hour": "h", "hours": "h", "h": "h",
                "minute": "min", "minutes": "min", "m": "min", "min": "min",
                "second": "s", "seconds": "s", "s": "s",
            }
            return (dt_series + pd.to_timedelta(n_series, unit=unit_map.get(unit_str, "D"))).reset_index(drop=True)

    # ── DATEDIFF(date1, date2, "unité") → différence entre deux dates ─────
    m = re.match(r'^DATEDIFF\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        if len(args) >= 2:
            dt1 = pd.to_datetime(_eval_mapping_formula(args[0].strip(), df), errors="coerce")
            dt2 = pd.to_datetime(_eval_mapping_formula(args[1].strip(), df), errors="coerce")
            unit_str = args[2].strip().strip("\"'").lower() if len(args) >= 3 else "day"
            diff = dt2 - dt1
            if unit_str in ("day", "days", "d"):
                return diff.dt.days.reset_index(drop=True)
            if unit_str in ("hour", "hours", "h"):
                return (diff.dt.total_seconds() / 3600).reset_index(drop=True)
            if unit_str in ("minute", "minutes", "m", "min"):
                return (diff.dt.total_seconds() / 60).reset_index(drop=True)
            return diff.dt.days.reset_index(drop=True)

    # ── TIMETOMIN(heure[, jour]) → convertit une heure en minutes totales ─
    # Ex: "22:45" → 1365 min ; avec jour=1 → 1365+1440=2805 min
    m = re.match(r'^TIMETOMIN\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        t_src = _eval_mapping_formula(args[0].strip(), df)

        if pd.api.types.is_timedelta64_dtype(t_src):
            minutes = t_src.dt.total_seconds() / 60
        elif pd.api.types.is_numeric_dtype(t_src):
            minutes = t_src % 1 * 1440  # fraction Excel → minutes
        else:
            def _time_to_minutes(x):
                try:
                    if x is None: return float("nan")
                    if hasattr(x, 'hour'): return x.hour * 60 + x.minute + getattr(x, 'second', 0) / 60
                    if hasattr(x, 'total_seconds'): return x.total_seconds() / 60
                    ts = pd.to_datetime(x, errors='coerce')
                    return float("nan") if pd.isna(ts) else ts.hour * 60 + ts.minute + ts.second / 60
                except Exception: return float("nan")
            minutes = t_src.apply(_time_to_minutes)

        if len(args) >= 2:
            day_series = pd.to_numeric(_eval_mapping_formula(args[1].strip(), df), errors="coerce").fillna(0)
            minutes = minutes + day_series * 1440
        return minutes.reset_index(drop=True)

    # ── TIMETOHOUR(heure[, jour]) → convertit une heure en heures décimales
    # Ex: "22:45" → 22.75
    m = re.match(r'^TIMETOHOUR\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        t_src = _eval_mapping_formula(args[0].strip(), df)

        if pd.api.types.is_timedelta64_dtype(t_src):
            hours = t_src.dt.total_seconds() / 3600
        elif pd.api.types.is_numeric_dtype(t_src):
            hours = t_src % 1 * 24
        else:
            def _time_to_hours(x):
                try:
                    if x is None: return float("nan")
                    if hasattr(x, 'hour'): return x.hour + x.minute / 60 + getattr(x, 'second', 0) / 3600
                    if hasattr(x, 'total_seconds'): return x.total_seconds() / 3600
                    ts = pd.to_datetime(x, errors='coerce')
                    return float("nan") if pd.isna(ts) else ts.hour + ts.minute / 60 + ts.second / 3600
                except Exception: return float("nan")
            hours = t_src.apply(_time_to_hours)

        if len(args) >= 2:
            day_series = pd.to_numeric(_eval_mapping_formula(args[1].strip(), df), errors="coerce").fillna(0)
            hours = hours + day_series * 24
        return hours.reset_index(drop=True)

    # ── TIMETOSEC(heure[, jour]) → convertit une heure en secondes totales ─
    m = re.match(r'^TIMETOSEC\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        t_src = _eval_mapping_formula(args[0].strip(), df)

        if pd.api.types.is_timedelta64_dtype(t_src):
            secs = t_src.dt.total_seconds()
        elif pd.api.types.is_numeric_dtype(t_src):
            secs = t_src % 1 * 86400
        else:
            def _time_to_secs(x):
                try:
                    if x is None: return float("nan")
                    if hasattr(x, 'hour'): return x.hour * 3600 + x.minute * 60 + getattr(x, 'second', 0)
                    if hasattr(x, 'total_seconds'): return x.total_seconds()
                    ts = pd.to_datetime(x, errors='coerce')
                    return float("nan") if pd.isna(ts) else ts.hour * 3600 + ts.minute * 60 + ts.second
                except Exception: return float("nan")
            secs = t_src.apply(_time_to_secs)

        if len(args) >= 2:
            day_series = pd.to_numeric(_eval_mapping_formula(args[1].strip(), df), errors="coerce").fillna(0)
            secs = secs + day_series * 86400
        return secs.reset_index(drop=True)

    # =========================================================================
    # FONCTIONS NUMÉRIQUES AVANCÉES
    # =========================================================================

    # ── RAND() / ALEA() → nombre aléatoire [0, 1) par ligne ──────────────
    if re.match(r'^(?:RAND|ALEA)\(\)$', expr, re.IGNORECASE):
        return pd.Series(np.random.random(n))

    # ── RANDBETWEEN(min, max) / ALEA.ENTRE.BORNES(min, max) ──────────────
    m = re.match(r'^(?:RANDBETWEEN|ALEA\.ENTRE\.BORNES)\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        if len(args) == 2:
            lo = pd.to_numeric(_eval_mapping_formula(args[0].strip(), df), errors="coerce").fillna(0)
            hi = pd.to_numeric(_eval_mapping_formula(args[1].strip(), df), errors="coerce").fillna(1)
            return pd.Series([int(np.random.randint(int(a), int(b) + 1)) for a, b in zip(lo, hi)])

    # ── MOD(valeur, diviseur) ─────────────────────────────────────────────
    m = re.match(r'^MOD\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        if len(args) == 2:
            a = pd.to_numeric(_eval_mapping_formula(args[0].strip(), df), errors="coerce")
            b = pd.to_numeric(_eval_mapping_formula(args[1].strip(), df), errors="coerce")
            return (a % b).reset_index(drop=True)

    # ── POWER(base, exposant) / PUISSANCE(base, exposant) ────────────────
    m = re.match(r'^(?:POWER|PUISSANCE)\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        if len(args) == 2:
            base = pd.to_numeric(_eval_mapping_formula(args[0].strip(), df), errors="coerce")
            exp_ = pd.to_numeric(_eval_mapping_formula(args[1].strip(), df), errors="coerce")
            return (base ** exp_).reset_index(drop=True)

    # ── SQRT(valeur) ──────────────────────────────────────────────────────
    m = re.match(r'^SQRT\((.+)\)$', expr, re.IGNORECASE)
    if m:
        src = pd.to_numeric(_eval_mapping_formula(m.group(1).strip(), df), errors="coerce")
        return np.sqrt(src).reset_index(drop=True)

    # ── MIN(a, b, ...) ────────────────────────────────────────────────────
    m = re.match(r'^MIN\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        cols = [pd.to_numeric(_eval_mapping_formula(a.strip(), df), errors="coerce") for a in args]
        return pd.concat(cols, axis=1).min(axis=1).reset_index(drop=True)

    # ── MAX(a, b, ...) ────────────────────────────────────────────────────
    m = re.match(r'^MAX\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        cols = [pd.to_numeric(_eval_mapping_formula(a.strip(), df), errors="coerce") for a in args]
        return pd.concat(cols, axis=1).max(axis=1).reset_index(drop=True)

    # ── SUM(a, b, ...) / SOMME(a, b, ...) ────────────────────────────────
    m = re.match(r'^(?:SUM|SOMME)\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        cols = [pd.to_numeric(_eval_mapping_formula(a.strip(), df), errors="coerce").fillna(0) for a in args]
        return pd.concat(cols, axis=1).sum(axis=1).reset_index(drop=True)

    # ── AVERAGE(a, b, ...) / MOYENNE(a, b, ...) ──────────────────────────
    m = re.match(r'^(?:AVERAGE|MOYENNE)\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        cols = [pd.to_numeric(_eval_mapping_formula(a.strip(), df), errors="coerce") for a in args]
        return pd.concat(cols, axis=1).mean(axis=1).reset_index(drop=True)

    # ── IFNA(valeur, alternative) → remplace NaN par alternative ─────────
    m = re.match(r'^IFNA\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        if len(args) == 2:
            val_series = _eval_mapping_formula(args[0].strip(), df)
            alt_series = _eval_mapping_formula(args[1].strip(), df)
            is_na = val_series.isna() | (val_series.astype(str).isin(["nan", "NaT", ""]))
            return val_series.where(~is_na, other=alt_series).reset_index(drop=True)

    # ── IFS(cond1, val1, cond2, val2, ...) / SI.CONDITIONS(...) ──────────
    # Évalue les conditions dans l'ordre, retourne la valeur de la première vraie
    m = re.match(r'^(?:IFS|SI\.CONDITIONS)\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        result = pd.Series([""] * n, dtype=object)
        filled = pd.Series([False] * n)  # garde trace des lignes déjà assignées
        for i in range(0, len(args) - 1, 2):
            cond_series = _eval_condition(args[i].strip(), df)
            val_series = _eval_mapping_formula(args[i + 1].strip(), df)
            apply_mask = cond_series & ~filled
            result = result.where(~apply_mask, other=val_series)
            filled = filled | apply_mask
        return result.reset_index(drop=True)

    # ── CHOOSE(index, val1, val2, ...) / CHOISIR(...) ─────────────────────
    # index 1-based : CHOOSE(2, "a", "b", "c") → "b"
    m = re.match(r'^(?:CHOOSE|CHOISIR)\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        if len(args) >= 2:
            idx_series = pd.to_numeric(_eval_mapping_formula(args[0].strip(), df), errors="coerce")
            options = [_eval_mapping_formula(a.strip(), df) for a in args[1:]]
            result = pd.Series([""] * n, dtype=object)
            for row_i, idx_val in enumerate(idx_series):
                try:
                    ii = int(idx_val) - 1  # convertit en 0-based
                    if 0 <= ii < len(options):
                        result.iloc[row_i] = options[ii].iloc[row_i]
                except Exception:
                    pass
            return result.reset_index(drop=True)

    # =========================================================================
    # FONCTIONS LOOKUP
    # =========================================================================

    # ── MATCH(valeur, colonne[, 0]) / EQUIV(...) ──────────────────────────
    # Retourne la position 1-based de la première correspondance dans la colonne
    m = re.match(r'^(?:MATCH|EQUIV)\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        if len(args) >= 2:
            lookup_series = _eval_mapping_formula(args[0].strip(), df).astype(str)
            search_series = _eval_mapping_formula(args[1].strip(), df).astype(str)
            search_list = search_series.tolist()

            def _match_fn(val):
                try: return search_list.index(val) + 1
                except ValueError: return float("nan")

            return lookup_series.apply(_match_fn).reset_index(drop=True)

    # ── INDEX(colonne, numéro_ligne) ──────────────────────────────────────
    # Retourne la valeur de la colonne à la ligne donnée (1-based)
    m = re.match(r'^INDEX\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        if len(args) == 2:
            col_series = _eval_mapping_formula(args[0].strip(), df)
            row_series = pd.to_numeric(_eval_mapping_formula(args[1].strip(), df), errors="coerce")
            col_list = col_series.tolist()

            def _index_fn(row_num):
                try:
                    ri = int(row_num) - 1  # convertit en 0-based
                    return col_list[ri] if 0 <= ri < len(col_list) else float("nan")
                except Exception:
                    return float("nan")

            return row_series.apply(_index_fn).reset_index(drop=True)

    # ── VLOOKUP(valeur, col_clé, col_résultat[, 0]) / RECHERCHEV(...) ─────
    # Cherche valeur dans col_clé et retourne la valeur correspondante dans col_résultat
    m = re.match(r'^(?:VLOOKUP|RECHERCHEV)\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        if len(args) >= 3:
            lookup_series = _eval_mapping_formula(args[0].strip(), df).astype(str)
            key_series = _eval_mapping_formula(args[1].strip(), df).astype(str)
            result_col_series = _eval_mapping_formula(args[2].strip(), df)
            key_list = key_series.tolist()
            result_list = result_col_series.tolist()

            def _vlookup_fn(val):
                try:
                    idx = key_list.index(val)
                    return result_list[idx]
                except (ValueError, IndexError):
                    return float("nan")

            return lookup_series.apply(_vlookup_fn).reset_index(drop=True)

    # =========================================================================
    # FONCTIONS SPÉCIALES
    # =========================================================================

    # ── LET(nom1, val1, ..., formule_finale) ─────────────────────────────
    # Crée des variables locales réutilisables dans la formule finale.
    # Ex: LET(p, RAND(), IF(p<Col1, "A", IF(p<Col2, "B", "C")))
    # Les variables sont ajoutées comme colonnes temporaires dans df_let.
    m = re.match(r'^LET\((.+)\)$', expr, re.IGNORECASE | re.DOTALL)
    if m:
        args = _split_formula_args(m.group(1))
        if len(args) >= 3 and len(args) % 2 == 1:
            df_let = df.copy()
            for i in range(0, len(args) - 1, 2):
                var_name = args[i].strip().strip("\"'")
                var_value = _eval_mapping_formula(args[i + 1].strip(), df_let)
                df_let[var_name] = var_value.values
            return _eval_mapping_formula(args[-1].strip(), df_let).reset_index(drop=True)

    # ── NOT(condition) ────────────────────────────────────────────────────
    m = re.match(r'^NOT\((.+)\)$', expr, re.IGNORECASE)
    if m:
        return (~_eval_condition(m.group(1).strip(), df)).reset_index(drop=True)

    # ── COALESCE(Col1, Col2, ...) → première valeur non vide ─────────────
    m = re.match(r'^COALESCE\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        result = pd.Series([""] * n, dtype=object)
        # On parcourt les arguments à l'envers pour que le premier non-vide "gagne"
        for arg in reversed(args):
            src = _eval_mapping_formula(arg.strip(), df)
            is_non_empty = src.notna() & (src.astype(str).str.strip() != "")
            result = src.where(is_non_empty, other=result)
        return result.reset_index(drop=True)

    # ── CONCAT(Col1, Col2, ...) → concatène plusieurs colonnes en texte ──
    m = re.match(r'^CONCAT\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        result_str = pd.Series([""] * n, dtype=str)
        for arg in args:
            src = _eval_mapping_formula(arg.strip(), df)
            result_str = result_str + src.fillna("").astype(str)
        return result_str.reset_index(drop=True)

    # ── IF(condition, valeur_si_vrai, valeur_si_faux) / SI(...) ──────────
    m = re.match(r'^(?:IF|SI)\((.+)\)$', expr, re.IGNORECASE)
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

    # ── ROW([départ]) → numéro de ligne (index) ───────────────────────────
    m = re.match(r'^ROW\((\d*)\)\s*(.*)$', expr, re.IGNORECASE)
    if m:
        start = int(m.group(1)) if m.group(1) else 0
        arithmetic = m.group(2).strip()
        idx = np.arange(start, start + n, dtype=float)
        if not arithmetic:
            return pd.Series(idx.astype(int))
        # Permet ROW()+1, ROW()*2, etc.
        if re.match(r'^[\d\s\+\-\*\/\(\)\.\^%]+$', arithmetic):
            arithmetic = arithmetic.replace('^', '**')
            try:
                result_arr = eval(f"idx{arithmetic}", {"idx": idx, "__builtins__": {}})  # noqa: S307
                return pd.Series(result_arr)
            except Exception:
                pass

    # =========================================================================
    # OPÉRATEURS
    # =========================================================================

    # ── Concaténation avec & ──────────────────────────────────────────────
    # Ex: Col1 & " - " & Col2  → "valA - valB"
    # On découpe sur les "&" qui ne sont PAS dans des parenthèses ou guillemets
    if "&" in expr:
        amp_parts: list = []
        depth = 0
        in_quote = False
        quote_char = ""
        current_part: list = []

        for char in expr:
            if char in ('"', "'") and not in_quote:
                in_quote, quote_char = True, char
                current_part.append(char)
            elif char == quote_char and in_quote:
                in_quote = False
                current_part.append(char)
            elif char == "(" and not in_quote:
                depth += 1
                current_part.append(char)
            elif char == ")" and not in_quote:
                depth -= 1
                current_part.append(char)
            elif char == "&" and depth == 0 and not in_quote:
                amp_parts.append("".join(current_part).strip())
                current_part = []
            else:
                current_part.append(char)

        if current_part:
            amp_parts.append("".join(current_part).strip())

        if len(amp_parts) > 1:
            result: pd.Series = pd.Series([""] * n, dtype=str)
            for part in amp_parts:
                part_val = _eval_mapping_formula(part, df)
                result = result + part_val.fillna("").astype(str)
            return result

    # ── Arithmétique additive (+, -) ──────────────────────────────────────
    # Vérifiée AVANT la multiplicative pour respecter la priorité des opérations
    # (on évalue de gauche à droite en trouvant le dernier + ou -)
    found_add = _rfind_op_at_depth0(expr, ("+", "-"))
    if found_add:
        op, left_expr, right_expr = found_add
        left_val = _eval_mapping_formula(left_expr, df)
        right_val = _eval_mapping_formula(right_expr, df)
        # Cas spécial : date + nombre de jours
        if pd.api.types.is_datetime64_any_dtype(left_val):
            delta = pd.to_timedelta(pd.to_numeric(right_val, errors="coerce").fillna(0), unit="D")
            return (left_val + delta if op == "+" else left_val - delta).reset_index(drop=True)
        left_num = pd.to_numeric(left_val, errors="coerce")
        right_num = pd.to_numeric(right_val, errors="coerce")
        return (left_num + right_num if op == "+" else left_num - right_num).reset_index(drop=True)

    # ── Arithmétique multiplicative (*, /) ────────────────────────────────
    found_mul = _rfind_op_at_depth0(expr, ("*", "/"))
    if found_mul:
        op, left_expr, right_expr = found_mul
        left_num = pd.to_numeric(_eval_mapping_formula(left_expr, df), errors="coerce")
        right_num = pd.to_numeric(_eval_mapping_formula(right_expr, df), errors="coerce")
        if op == "*":
            return (left_num * right_num).reset_index(drop=True)
        # Division : remplace 0 par NaN pour éviter la division par zéro
        return (left_num / right_num.replace(0, float("nan"))).reset_index(drop=True)

    # Aucune règle ne correspond → retourner une série vide
    return empty
