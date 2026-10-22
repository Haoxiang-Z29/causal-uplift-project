# Hillstrom fallback contract (archived D1 setup)

This preserves the original Agent-created fallback contract. It is not the
active modeling route after the user's 2026-08-04 Criteo decision.

- Data: Hillstrom randomized email experiment, 64,000 customers and three arms.
- Binary fallback: Mens E-Mail versus No E-Mail.
- Unit: customer.
- Treatment: Mens E-Mail assignment versus No E-Mail.
- Primary outcome: two-week `conversion`.
- Covariates: `recency, history_segment, history, mens, womens, zip_code,
  newbie, channel`.
- Excluded: `visit` and `spend` are post-treatment outcomes; `segment` defines
  the experimental arm.
- Estimand: CATE of assignment on conversion.
- Decision: rank customers for email contact under a fixed contact budget.

The verified raw file, inspection artifact, downloader, checker, and tests stay
in the repository workspace as a time-boxed fallback.
