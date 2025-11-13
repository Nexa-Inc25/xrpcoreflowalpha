from prometheus_client import Counter

xrpl_tx_processed = Counter(
    "xrpl_tx_processed",
    "Number of XRPL transactions processed",
    ["type"],
)

zk_proof_detected = Counter(
    "zk_proof_detected",
    "Number of suspected ZK proof verifications detected",
    ["network"],
)

equity_dark_pool_volume = Counter(
    "equity_dark_pool_volume",
    "Total shares from detected dark pool prints",
    ["symbol", "venue"],
)
