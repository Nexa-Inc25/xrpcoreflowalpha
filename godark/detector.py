from typing import Any, Dict, List

from app.config import GODARK_XRPL_PARTNERS, GODARK_XRPL_DEST_TAGS


def _lower_list(xs: List[str]) -> List[str]:
    return [x.lower() for x in xs]


async def annotate_godark(signal: Dict[str, Any]) -> Dict[str, Any]:
    tags = list(signal.get("tags") or [])
    if signal.get("type") == "xrp":
        partners = _lower_list(GODARK_XRPL_PARTNERS)
        dest = str(signal.get("destination") or "").lower()
        src = str(signal.get("source") or "").lower()
        if dest in partners or src in partners:
            if "GoDark Partner" not in tags:
                tags.append("GoDark Partner")
            usd = 0.0
            try:
                usd = float(signal.get("usd_value") or 0.0)
            except Exception:
                usd = 0.0
            if usd >= 10_000_000 and "GoDark Prep" not in tags:
                tags.append("GoDark Prep")
            if usd > 50_000_000 and "GoDark Likely" not in tags:
                tags.append("GoDark Likely")
            st = str(signal.get("sub_type") or "").lower()
            summ = str(signal.get("summary") or "")
            if ("escrow" in st) or ("escrow" in summ.lower()):
                if "GoDark XRPL Settlement" not in tags:
                    tags.append("GoDark XRPL Settlement")
        try:
            dtag = int(signal.get("destination_tag") or 0)
        except Exception:
            dtag = None
        if dtag and dtag in GODARK_XRPL_DEST_TAGS and "GoDark ClearLoop Tag" not in tags:
            tags.append("GoDark ClearLoop Tag")
    signal["tags"] = tags
    return signal
