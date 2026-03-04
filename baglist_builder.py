from __future__ import annotations

import hashlib
import json
import re
from io import BytesIO

import pandas as pd

from baglist_expr import eval_formula


def read_table(file) -> pd.DataFrame:
    if file is None:
        raise ValueError("Fichier manquant.")
    name = getattr(file, "name", "").lower()
    if name.endswith((".xlsx", ".xls")):
        file.seek(0)
        return pd.read_excel(file)
    file.seek(0)
    try:
        return pd.read_csv(file)
    except Exception:
        file.seek(0)
        return pd.read_csv(file, sep=";", engine="python")


def template_signature(rows: list[dict]) -> str:
    payload = json.dumps(rows, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _parse_constant(value):
    if value is None:
        return ""
    if isinstance(value, (int, float, bool, pd.Timestamp)):
        return value
    text = str(value).strip()
    if text == "":
        return ""
    lowered = text.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    if re.fullmatch(r"-?\d+\.\d+", text):
        return float(text)
    return text


def _missing_mask(series: pd.Series) -> pd.Series:
    mask = series.isna()
    if series.dtype == object:
        mask = mask | series.astype(str).str.strip().eq("")
    return mask


def _format_keyword(fmt: str) -> str | None:
    if not fmt:
        return None
    fmt_lower = str(fmt).strip().lower()
    if fmt_lower in {"datetime", "date", "time", "number", "numeric", "text", "string", "bool", "boolean", "int"}:
        return fmt_lower
    return None


def _coerce_for_format(series: pd.Series, fmt: str | None) -> pd.Series:
    keyword = _format_keyword(fmt)
    if keyword in {"datetime", "date", "time"}:
        return pd.to_datetime(series, errors="coerce")
    if keyword in {"number", "numeric", "int"}:
        return pd.to_numeric(series, errors="coerce")
    if keyword in {"text", "string"}:
        return series.astype(str)
    if keyword in {"bool", "boolean"}:
        return series.fillna(False).astype(bool)
    return series


def _normalize_excel_format(fmt: str | None) -> str | None:
    if not fmt:
        return None
    fmt_str = str(fmt).strip()
    if fmt_str == "":
        return None
    keyword = _format_keyword(fmt_str)
    if keyword == "datetime":
        return "dd/mm/yy hh:mm"
    if keyword == "date":
        return "dd/mm/yy"
    if keyword == "time":
        return "hh:mm"
    if keyword in {"number", "numeric", "int"}:
        return "0.00"
    if keyword in {"text", "string"}:
        return "@"
    if keyword in {"bool", "boolean"}:
        return "@"
    return re.sub(r"[A-Za-z]+", lambda m: m.group(0).lower(), fmt_str)


def _warnings_for_mask(mask: pd.Series, output_column: str, reason: str, key_series: pd.Series) -> pd.DataFrame | None:
    if mask is None or not mask.any():
        return None
    keys = key_series[mask]
    keys = keys.where(~keys.isna(), "")
    keys = keys.astype(str)
    return pd.DataFrame(
        {
            "output_column": output_column,
            "reason": reason,
            "key": keys,
            "row_index": keys.index,
        }
    )


def _lookup_series(
    left_keys: pd.Series,
    right_df: pd.DataFrame,
    join_key: str,
    field: str,
    default,
    duplicate_strategy: str,
    output_column: str,
) -> tuple[pd.Series, list[pd.DataFrame], dict]:
    if join_key not in right_df.columns:
        raise ValueError(f"Cle '{join_key}' absente du fichier de lookup.")
    if field not in right_df.columns:
        raise ValueError(f"Champ '{field}' absent du fichier de lookup.")

    right = right_df[[join_key, field]].copy()
    dup_mask = right[join_key].duplicated(keep=False)
    dup_keys = right.loc[dup_mask, join_key].dropna()
    dup_count = dup_keys.nunique()

    if dup_count > 0 and duplicate_strategy == "error":
        raise ValueError(f"Doublons detectes sur la cle '{join_key}' ({dup_count} cles).")

    if dup_count > 0:
        right = right.drop_duplicates(subset=join_key, keep="first")

    mapping = right.set_index(join_key)[field]
    result = left_keys.map(mapping)

    missing_mask = _missing_mask(left_keys)
    not_found_mask = ~missing_mask & result.isna()

    if default is not None:
        result = result.copy()
        result[missing_mask | not_found_mask] = default

    warnings = []
    missing_warn = _warnings_for_mask(missing_mask, output_column, "missing_key", left_keys)
    if missing_warn is not None:
        warnings.append(missing_warn)

    not_found_warn = _warnings_for_mask(not_found_mask, output_column, "key_not_found", left_keys)
    if not_found_warn is not None:
        warnings.append(not_found_warn)

    if dup_count > 0:
        warnings.append(
            pd.DataFrame(
                {
                    "output_column": output_column,
                    "reason": "duplicate_right_key",
                    "key": dup_keys.astype(str).unique(),
                    "row_index": pd.NA,
                }
            )
        )

    stats = {
        "missing_keys": int(missing_mask.sum()),
        "not_found": int(not_found_mask.sum()),
        "duplicate_keys": int(dup_count),
    }

    return result, warnings, stats


def build_baglist(
    bags_df: pd.DataFrame,
    allocation_df: pd.DataFrame | None,
    transfers_df: pd.DataFrame | None,
    template_rows: list[dict],
    duplicate_strategy: str = "first",
) -> tuple[pd.DataFrame, pd.DataFrame, dict, dict]:
    if bags_df is None:
        raise ValueError("Le fichier bags est obligatoire.")

    output_df = pd.DataFrame(index=bags_df.index)
    current_df = bags_df.copy()
    warnings_frames: list[pd.DataFrame] = []
    summary = {"missing_keys": 0, "not_found": 0, "duplicate_keys": 0}
    format_map: dict[str, str] = {}
    errors: list[str] = []

    for row in template_rows:
        output_column = str(row.get("output_column", "")).strip()
        if not output_column:
            continue
        col_type = str(row.get("type", "copy")).strip().lower()
        source = str(row.get("source", "")).strip().lower()
        join_key = str(row.get("join_key", "")).strip()
        field = row.get("field")
        default = _parse_constant(row.get("default"))
        fmt = row.get("format")

        try:
            if col_type == "copy":
                source_field = str(field).strip() if field not in (None, "") else output_column
                if source_field not in current_df.columns:
                    raise ValueError(f"Colonne '{source_field}' introuvable pour copy.")
                series = current_df[source_field]
            elif col_type == "const":
                value = field if field not in (None, "") else row.get("default")
                series = pd.Series([_parse_constant(value)] * len(current_df), index=current_df.index)
            elif col_type == "lookup":
                if not join_key:
                    if source == "allocation":
                        join_key = "DepFlightId"
                    elif source == "transfers":
                        join_key = "ArrFlightId"
                    else:
                        raise ValueError("Join key manquant pour lookup.")
                if join_key not in current_df.columns:
                    raise ValueError(f"Cle '{join_key}' introuvable dans bags.")
                lookup_df = None
                if source == "allocation":
                    lookup_df = allocation_df
                elif source == "transfers":
                    lookup_df = transfers_df
                else:
                    raise ValueError("Source lookup invalide (allocation/transfers).")
                if lookup_df is None:
                    raise ValueError(f"Fichier '{source}' manquant pour lookup.")
                if not field:
                    raise ValueError("Champ lookup manquant.")
                series, warnings, stats = _lookup_series(
                    current_df[join_key],
                    lookup_df,
                    join_key,
                    str(field).strip(),
                    default,
                    duplicate_strategy,
                    output_column,
                )
                warnings_frames.extend(warnings)
                summary["missing_keys"] += stats["missing_keys"]
                summary["not_found"] += stats["not_found"]
                summary["duplicate_keys"] += stats["duplicate_keys"]
            elif col_type == "formula":
                expr = str(field).strip() if field not in (None, "") else ""
                if not expr:
                    raise ValueError("Expression manquante pour formula.")
                series = eval_formula(expr, current_df)
            else:
                raise ValueError(f"Type de colonne inconnu: {col_type}")
        except Exception as exc:
            errors.append(f"{output_column}: {exc}")
            continue

        series = _coerce_for_format(series, fmt)
        output_df[output_column] = series
        current_df[output_column] = series

        if fmt:
            format_map[output_column] = str(fmt)

    if errors:
        raise ValueError("\n".join(errors))

    warnings_df = pd.concat(warnings_frames, ignore_index=True) if warnings_frames else pd.DataFrame(
        columns=["output_column", "reason", "key", "row_index"]
    )

    summary.update(
        {
            "rows_in": int(len(bags_df)),
            "rows_out": int(len(output_df)),
            "warnings": int(len(warnings_df)),
        }
    )

    return output_df, warnings_df, summary, format_map


def render_baglist_excel(output_df: pd.DataFrame, format_map: dict[str, str]) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        output_df.to_excel(writer, index=False, sheet_name="baglist")
        workbook = writer.book
        worksheet = writer.sheets["baglist"]
        for col_idx, col_name in enumerate(output_df.columns):
            fmt = format_map.get(col_name)
            fmt_norm = _normalize_excel_format(fmt)
            if fmt_norm:
                cell_format = workbook.add_format({"num_format": fmt_norm})
                worksheet.set_column(col_idx, col_idx, None, cell_format)
    return buffer.getvalue()
