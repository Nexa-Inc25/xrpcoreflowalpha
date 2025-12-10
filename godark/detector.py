from typing import Any, Dict, List

from app.config import GODARK_XRPL_PARTNERS, GODARK_XRPL_DEST_TAGS, REDIS_URL
from app.redis_utils import get_redis, REDIS_ENABLED


def _lower_list(xs: List[str]) -> List[str]:
    return [x.lower() for x in xs]


def _sg(obj: Any, key: str, default: Any = None) -> Any:
    try:
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)
    except Exception:
        return default


async def annotate_godark(signal: Dict[str, Any]) -> Dict[str, Any]:
    tags = list(_sg(signal, "tags") or [])
    if _sg(signal, "type") == "xrp":
        # merge env seeds + dynamic partner set from redis
        r = await get_redis()
        dyn = await r.smembers("godark:partners:xrpl")
        partners = set(_lower_list(GODARK_XRPL_PARTNERS)) | {str(x).lower() for x in (dyn or [])}
        dest = str(_sg(signal, "destination") or "").lower()
        src = str(_sg(signal, "source") or "").lower()
        if dest in partners or src in partners:
            if "GoDark Partner" not in tags:
                tags.append("GoDark Partner")
            usd = 0.0
            try:
                usd = float(_sg(signal, "usd_value") or 0.0)
            except Exception:
                usd = 0.0
            if usd >= 10_000_000 and "GoDark Prep" not in tags:
                tags.append("GoDark Prep")
            if usd > 50_000_000 and "GoDark Likely" not in tags:
                tags.append("GoDark Likely")
            st = str(_sg(signal, "sub_type") or "").lower()
            summ = str(_sg(signal, "summary") or "")
            if ("escrow" in st) or ("escrow" in summ.lower()):
                if "GoDark XRPL Settlement" not in tags:
                    tags.append("GoDark XRPL Settlement")
        try:
            dtag = int(_sg(signal, "destination_tag") or 0)
        except Exception:
            dtag = None
        if dtag and dtag in GODARK_XRPL_DEST_TAGS and "GoDark ClearLoop Tag" not in tags:
            tags.append("GoDark ClearLoop Tag")
    signal["tags"] = tags
    return signal
