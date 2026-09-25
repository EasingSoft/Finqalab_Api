# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-09-25

### Added

- `FinqalabClient` - REST auth (login, device OTP, profile) and session misc
- `MarketClient` - market summary, index snapshot, news, per-symbol statistics,
  company profile, financials, price/volume graph
- `WatchlistClient` - read and add/remove symbols across watchlists 1-5
- `AlertsClient` - alert permissions and alert history
- `PaymentsClient` - deposit history, withdrawal history, bank codes, beneficiary
  accounts, cashbook ledger, periodic trade details, PDF reports
- `StompClient` - STOMP 1.2 over SockJS trading WebSocket
- `order` - place, modify, cancel, and list orders
- `portfolio` - holdings, cash balance, executed trades
- `oms` - trade-intimation logging
- `encryption` - AES-256-CBC helpers for password and PIN/CNIC/mobile fields
- Usage documentation in `doc/api/`
- Reverse-engineering documentation in `doc/reverse/`

### Notes

- Requires Python 3.9+
- Not affiliated with, endorsed by, or supported by Next Capital or Finqalab
