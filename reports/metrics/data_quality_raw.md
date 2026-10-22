## Data-quality profile: `raw`

| Table | Rows | Exact duplicate rows | Duplicate PKs | Unparseable timestamps | Timestamp range |
|---|---:|---:|---:|---:|---|
| sessions | 35,862 | 30 | 40 | 0 | 2025-01-01 00:02:20 → 2025-06-30 23:58:16 |
| events | 161,427 | 643 | 803 | 0 | 2025-01-01 00:02:20 → 2025-07-01 00:00:33 |
| transactions | 976 | 24 | 30 | 0 | 2025-01-01 03:51:01 → 2025-06-30 22:54:01 |

**Missing values**

- sessions: `campaign`: 20,770, `device_category`: 107, `country`: 358
- events: `product_id`: 116,124
- transactions: none

**Non-standard labels**

- sessions.`traffic_source`: 1,076 rows (e.g. ' google', '(Direct)', 'Bing', 'FACEBOOK ', 'Facebook', 'GOOGLE')
- sessions.`marketing_medium`: 717 rows (e.g. 'CPC', 'Email', 'Organic', 'Paid Social', 'Referral', 'Social')
- sessions.`device_category`: 893 rows (e.g. 'DESKTOP ', 'Desktop', 'MOBILE', 'Mobile', 'Tablet', 'iPad')
- events.`event_name`: 3,236 rows (e.g. 'ADD_TO_CART', 'Add To Cart', 'Begin Checkout', 'PAGE_VIEW', 'PURCHASE', 'Page View')
- transactions.`transaction_status`: 25 rows (e.g. 'COMPLETED', 'REFUNDED', 'test')
- transactions.`currency`: 19 rows (e.g. 'usd')

**Relationship and business-rule checks**

| Check | Count |
|---|---:|
| orphan_events (session_id not in sessions) | 150 |
| orphan_transactions (session_id not in sessions) | 5 |
| events_before_session_start | 0 |
| transactions_before_session_start | 6 |
| revenue_unparseable | 0 |
| revenue_negative | 8 |
| revenue_zero | 0 |
| test_transactions | 15 |
| sessions_with_purchase_before_checkout | 25 |
| sessions_with_transaction_but_no_purchase_event | 38 |
| sessions_with_purchase_event_but_no_valid_transaction | 8 |
| sessions_without_session_start_event | 690 |

