from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from allocator_types import CarouselCapacity


def _max_capacity_limits(
    carousel_caps: Dict[str, CarouselCapacity],
    *,
    allow_wide_use_narrow: bool = True,
) -> Tuple[int, int]:
    if not carousel_caps:
        return 0, 0
    if allow_wide_use_narrow:
        max_wide_total = max(cap.wide + cap.narrow for cap in carousel_caps.values())
    else:
        max_wide_total = max(cap.wide for cap in carousel_caps.values())
    max_narrow = max(cap.narrow for cap in carousel_caps.values())
    return max_wide_total, max_narrow


def _is_impossible_demand(category: str, positions: int, max_wide_total: int, max_narrow: int) -> bool:
    category = str(category).strip().lower()
    if category == "wide":
        return positions > max_wide_total
    if category == "narrow":
        return positions > max_narrow
    raise ValueError(f"Unknown category: {category} (expected 'Wide' or 'Narrow')")


def _can_fit(
    category: str,
    positions: int,
    free_wide: int,
    free_narrow: int,
    *,
    allow_wide_use_narrow: bool = True,
) -> bool:
    """
    Wide can use wide first then narrow overflow.
    Narrow can use only narrow.
    """
    category = str(category).strip().lower()
    if category == "wide":
        if allow_wide_use_narrow:
            return (free_wide + free_narrow) >= positions
        return free_wide >= positions
    elif category == "narrow":
        return free_narrow >= positions
    else:
        raise ValueError(f"Unknown category: {category} (expected 'Wide' or 'Narrow')")


def _consume(
    category: str,
    positions: int,
    free_wide: int,
    free_narrow: int,
    *,
    allow_wide_use_narrow: bool = True,
) -> Tuple[int, int]:
    """
    Returns updated (free_wide, free_narrow) after allocation.
    """
    category = str(category).strip().lower()
    if category == "narrow":
        # must consume narrow only
        return free_wide, free_narrow - positions

    # wide: consume wide first, overflow to narrow if allowed
    if not allow_wide_use_narrow:
        return free_wide - positions, free_narrow
    use_wide = min(free_wide, positions)
    rem = positions - use_wide
    use_narrow = rem
    return free_wide - use_wide, free_narrow - use_narrow


def _wide_only_possible(
    free: Dict[str, Dict[str, int]],
    positions: int,
    max_carousels: int,
) -> bool:
    if max_carousels <= 0:
        return False
    caps = [int(v.get("wide", 0)) for v in free.values()]
    if not caps:
        return False
    caps.sort(reverse=True)
    return sum(caps[: min(max_carousels, len(caps))]) >= positions


def _normalize_category(value: object) -> str:
    s = str(value or "").strip().lower()
    if s in ("wide", "w"):
        return "wide"
    if s in ("narrow", "n"):
        return "narrow"
    return s


def _max_multi_capacity(
    carousel_caps: Dict[str, CarouselCapacity],
    category: str,
    max_carousels: int,
    *,
    allow_wide_use_narrow: bool = True,
) -> int:
    if not carousel_caps or max_carousels <= 0:
        return 0
    category = _normalize_category(category)
    caps: List[int] = []
    for cap in carousel_caps.values():
        if category == "wide":
            if allow_wide_use_narrow:
                caps.append(int(cap.wide) + int(cap.narrow))
            else:
                caps.append(int(cap.wide))
        else:
            caps.append(int(cap.narrow))
    caps.sort(reverse=True)
    return sum(caps[: min(max_carousels, len(caps))])


def _is_impossible_demand_multi(
    category: str,
    positions: int,
    carousel_caps: Dict[str, CarouselCapacity],
    max_carousels: int,
    *,
    allow_wide_use_narrow: bool = True,
) -> bool:
    return positions > _max_multi_capacity(
        carousel_caps,
        category,
        max_carousels,
        allow_wide_use_narrow=allow_wide_use_narrow,
    )


def _select_split_allocations(
    category: str,
    positions: int,
    free: Dict[str, Dict[str, int]],
    carousels: List[str],
    rr_idx: int,
    max_carousels: int,
    wide_only: bool = False,
    *,
    allow_wide_use_narrow: bool = True,
) -> Optional[List[Dict[str, object]]]:
    if max_carousels <= 0 or not carousels:
        return None
    category = _normalize_category(category)
    candidates: List[Tuple[str, int, int]] = []
    for idx, c in enumerate(carousels):
        fw, fn = free[c]["wide"], free[c]["narrow"]
        if category == "wide":
            if wide_only or not allow_wide_use_narrow:
                cap = fw
            else:
                cap = fw + fn
        else:
            cap = fn
        if cap > 0:
            order = (idx - rr_idx) % len(carousels)
            candidates.append((c, cap, order))
    if not candidates:
        return None

    candidates.sort(key=lambda x: (-x[1], x[2], x[0]))
    if sum(cap for _, cap, _ in candidates[:max_carousels]) < positions:
        return None

    allocations: List[Dict[str, object]] = []
    remaining = positions
    used = 0
    for c, cap, _ in candidates:
        if used >= max_carousels or remaining <= 0:
            break
        take = min(remaining, cap)
        fw, fn = free[c]["wide"], free[c]["narrow"]
        new_fw, new_fn = _consume(
            category,
            take,
            fw,
            fn,
            allow_wide_use_narrow=allow_wide_use_narrow,
        )
        allocations.append({
            "carousel": c,
            "wide_used": fw - new_fw,
            "narrow_used": fn - new_fn,
        })
        remaining -= take
        used += 1
    if remaining > 0:
        return None
    return allocations
