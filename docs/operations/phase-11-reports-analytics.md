# Phase 11: Reports and analytics

Staff can open `/reports/` for permission-aware operational reporting over the last 7, 30, or 90 days. Paid orders are the sole source of revenue and product-performance figures; unpaid, failed, and refunded payments are excluded.

Exports are available as CSV, Excel, and PDF. They include only aggregates, SKU-level performance, inventory exceptions, promotion totals, and security-event counts that the requesting staff account may view. Customer names, email addresses, address snapshots, and payment-provider payloads are deliberately excluded.

The page uses Chart.js for the optional browser chart, while all three downloads are generated server-side. The report data is calculated at request time to keep the first implementation correct and easy to operate. If reporting grows beyond the current request-time window, add scheduled aggregate tables after measuring the actual query load.
