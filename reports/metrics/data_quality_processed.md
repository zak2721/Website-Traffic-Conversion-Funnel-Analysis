## Data-quality profile: `processed`

| Table | Rows | Exact duplicate rows | Duplicate PKs | Unparseable timestamps | Timestamp range |
|---|---:|---:|---:|---:|---|
| sessions | 35,822 | 0 | 0 | 0 | 2025-01-01 00:02:20 → 2025-06-30 23:58:16 |
| events | 160,474 | 0 | 0 | 0 | 2025-01-01 00:02:20 → 2025-07-01 00:00:33 |
| transactions | 913 | 0 | 0 | 0 | 2025-01-01 03:51:01 → 2025-06-30 22:54:01 |

**Missing values**

- sessions: none
- events: `product_id`: 115,444
- transactions: none

**Non-standard labels**

- none

**Relationship and business-rule checks**

| Check | Count |
|---|---:|
| orphan_events (session_id not in sessions) | 0 |
| orphan_transactions (session_id not in sessions) | 0 |
| events_before_session_start | 0 |
| transactions_before_session_start | 0 |
| revenue_unparseable | 0 |
| revenue_negative | 0 |
| revenue_zero | 0 |
| test_transactions | 0 |
| sessions_with_purchase_before_checkout | 25 |
| sessions_with_transaction_but_no_purchase_event | 13 |
| sessions_with_purchase_event_but_no_valid_transaction | 13 |
| sessions_without_session_start_event | 0 |

