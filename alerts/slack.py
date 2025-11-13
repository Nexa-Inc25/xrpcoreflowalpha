import httpx
from typing import Any, Dict
from app.config import ALERTS_SLACK_WEBHOOK

async def send_slack_alert(payload: Dict[str, Any]) -> None:
    if not ALERTS_SLACK_WEBHOOK:
        return
    async with httpx.AsyncClient(timeout=10) as client:
        await client.post(ALERTS_SLACK_WEBHOOK, json=payload)

def build_rich_slack_payload(flow: Dict[str, Any]) -> Dict[str, Any]:
    header_text = "CROSS-MARKET SIGNAL" if flow.get("type") == "cross" else "FLOW ALERT"
    detail_lines = []
    if flow.get("type") == "equity" and "trade" in flow:
        t = flow["trade"]
        detail_lines.append(f"Equity: {t.get('s')} {t.get('v')} @ {t.get('p')}")
    if flow.get("type") == "xrp" and "flow" in flow:
        xf = flow["flow"]
        detail_lines.append(f"XRPL: {getattr(xf,'amount_xrp',0):,.0f} XRP")
    if flow.get("type") == "zk" and "flow" in flow:
        zf = flow["flow"]
        detail_lines.append(f"ZK Proof: {getattr(zf,'tx_hash','')}")
    text_block = "\n".join(detail_lines) if detail_lines else ""
    return {
        "blocks": [
            {"type": "header", "text": {"type": "plain_text", "text": header_text}},
            {"type": "section", "text": {"type": "mrkdwn", "text": text_block}},
        ]
    }
