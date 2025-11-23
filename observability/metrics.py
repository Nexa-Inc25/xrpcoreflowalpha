from prometheus_client import Counter, Gauge

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

# Billing/Checkout metrics
billing_checkout_session_created = Counter(
    "darkflow_checkout_session_created_total",
    "Number of Stripe checkout sessions created",
    ["tier"],
)

billing_checkout_completed = Counter(
    "darkflow_checkout_completed_total",
    "Number of Stripe checkout sessions completed",
    ["tier"],
)

billing_webhook_failures = Counter(
    "darkflow_webhook_failures_total",
    "Number of Stripe webhook processing failures",
    ["reason"],
)

billing_webhook_duplicates = Counter(
    "darkflow_webhook_duplicates_total",
    "Number of duplicated Stripe webhook events ignored",
)

# On-chain billing and history
onchain_receipt_total = Counter(
    "onchain_receipt_total",
    "Number of on-chain payment receipts applied",
    ["asset", "tier"],
)

replay_requests_total = Counter(
    "replay_requests_total",
    "Number of history replay requests",
    ["days"],
)

pending_payment_total = Counter(
    "pending_payment_total",
    "Number of pending on-chain payments created",
    ["source"],
)

zk_flow_confidence_score = Gauge(
    "zk_flow_confidence_score",
    "Markov-based probability of imminent dark pool execution",
    ["protocol"],
)
