# Binance Futures Testnet Trading Bot

A clean, structured Python CLI for placing orders on Binance Futures Testnet (USDT-M perpetual futures).

---

## Features

- **MARKET**, **LIMIT**, and **STOP_LIMIT** orders
- **BUY** and **SELL** sides
- **Interactive mode** (`--interactive`) — guided step-by-step prompts with numbered menus and real-time validation
- Full input validation with helpful error messages
- Rich CLI output — order summary, response table, colour-coded status
- Separate log files per order type (`market_order.log`, `limit_order.log`, `stop_limit_order.log`)
- Confirmation prompt before every order (skippable with `--yes`)
- Graceful error handling for API errors, network failures, and bad input

---

## Project structure

```
trading_bot/
├── bot/
│   ├── __init__.py
│   ├── client.py          # Binance REST API wrapper + HMAC signing
│   ├── orders.py          # Order placement logic
│   ├── validators.py      # Input validation
│   └── logging_config.py  # Rotating file loggers
├── cli.py                 # CLI entry point
├── logs/                  # Auto-created on first run
│   ├── market_order.log
│   ├── limit_order.log
│   ├── stop_limit_order.log
│   └── trading_bot.log
├── .env                   # Your credentials (never commit this)
├── requirements.txt
└── README.md
```

---

## Setup

### 1. Get Testnet credentials

1. Register at <https://testnet.binancefuture.com>
2. Log in → **API Key** tab → **Create**
3. Copy your **API Key** and **Secret Key**

### 2. Install dependencies

```bash
cd trading_bot
pip install -r requirements.txt
```

### 3. Configure credentials

Create a `.env` file in the `trading_bot/` directory:

```env
BINANCE_TESTNET_API_KEY=your_api_key_here
BINANCE_TESTNET_API_SECRET=your_api_secret_here
```

Or export them as environment variables:

```bash
export BINANCE_TESTNET_API_KEY=your_api_key_here
export BINANCE_TESTNET_API_SECRET=your_api_secret_here
```

> **Never commit your `.env` file to version control.**

---

## How to run

All commands are run from the `trading_bot/` directory.

### Interactive mode (recommended for new users)

Walks you through every field with numbered menus, plain-English hints, and live validation — no flags to memorise.

```bash
python cli.py --interactive
# or shorthand:
python cli.py -i
```

Example session:

```
Step 1/5 — Symbol
  Enter a USDT-M futures trading pair, e.g. BTCUSDT, ETHUSDT
  Symbol (e.g. BTCUSDT): BTCUSDT
  ✓  BTCUSDT

Step 2/5 — Side
  Symbol: BTCUSDT
  Which side?
    1  BUY   Open a long / close a short
    2  SELL  Open a short / close a long
  Enter number or name: 1
  ✓  BUY

Step 3/5 — Order Type
  Which order type?
    1  MARKET      Execute immediately at the best available price
    2  LIMIT       Execute at a specific price or better
    3  STOP_LIMIT  Trigger a limit order when the market hits a stop price
  Enter number or name: 1
  ✓  MARKET

Step 4/5 — Quantity
  Quantity (e.g. 0.001): 0.001
  ✓  0.001

Step 5/5 — Review & Confirm
  ┌─ Order Request ──────────┐
  │ Symbol   │ BTCUSDT      │
  │ Side     │ BUY          │
  │ Type     │ MARKET       │
  │ Quantity │ 0.001        │
  └──────────┴──────────────┘

  Confirm order? [y/N]: y
```

---

### Market BUY

```bash
python cli.py --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001
```

### Market SELL

```bash
python cli.py --symbol BTCUSDT --side SELL --type MARKET --quantity 0.001
```

### Limit BUY

```bash
python cli.py --symbol ETHUSDT --side BUY --type LIMIT --quantity 0.01 --price 2800
```

### Limit SELL

```bash
python cli.py --symbol ETHUSDT --side SELL --type LIMIT --quantity 0.01 --price 3500
```

### Stop-Limit BUY (trigger at 44000, execute limit at 44100)

```bash
python cli.py --symbol BTCUSDT --side BUY --type STOP_LIMIT \
    --quantity 0.001 --stop-price 44000 --price 44100
```

### Stop-Limit SELL (trigger at 42000, execute limit at 41900)

```bash
python cli.py --symbol BTCUSDT --side SELL --type STOP_LIMIT \
    --quantity 0.001 --stop-price 42000 --price 41900
```

### Skip confirmation (useful for scripts)

```bash
python cli.py --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001 --yes
```

---

## CLI arguments

| Argument     | Required | Description                              |
|--------------|----------|------------------------------------------|
| `--interactive`/`-i` | No    | Launch guided interactive order builder               |
| `--symbol`      | Yes*       | Trading pair (e.g. `BTCUSDT`, `ETHUSDT`)              |
| `--side`        | Yes*       | `BUY` or `SELL`                                       |
| `--type`        | Yes*       | `MARKET`, `LIMIT`, or `STOP_LIMIT`                    |
| `--quantity`    | Yes        | Order quantity                                        |
| `--price`       | LIMIT / SL | Limit price — required for LIMIT and STOP_LIMIT       |
| `--stop-price`  | STOP_LIMIT | Trigger price — required for STOP_LIMIT               |
| `--yes`/`-y`    | No         | Skip the confirmation prompt                          |

---

## Example output

```
  ╔══════════════════════════════════════════╗
  ║   Binance Futures Testnet Trading Bot    ║
  ║          USDT-M Perpetual Futures        ║
  ╚══════════════════════════════════════════╝

╭──────────────────────╮
│    Order Request     │
├──────────────┬───────┤
│ Symbol       │ BTCUSDT │
│ Side         │ BUY     │
│ Type         │ MARKET  │
│ Quantity     │ 0.001   │
╰──────────────┴─────────╯

Confirm order? [y/N]: y

──────────────── Submitting order… ────────────────

╭─────────────────────────────╮
│       Order Response        │
├──────────────────┬──────────┤
│ Order ID         │ 1234567  │
│ Symbol           │ BTCUSDT  │
│ Status           │ FILLED   │
│ Side             │ BUY      │
│ Type             │ MARKET   │
│ Ordered Qty      │ 0.001    │
│ Executed Qty     │ 0.001    │
│ Avg Fill Price   │ 43250.5  │
│ Time in Force    │ GTC      │
╰──────────────────┴──────────╯

╭─────────────────────────────╮
│ ✓  Order placed successfully! │
╰─────────────────────────────╯
```

---

## Logs

Each run appends to the appropriate log file:

| Log file                  | Contains                              |
|---------------------------|---------------------------------------|
| `logs/market_order.log`   | All MARKET order requests/responses   |
| `logs/limit_order.log`    | All LIMIT order requests/responses    |
| `logs/trading_bot.log`    | Low-level HTTP calls and errors       |

Log format:
```
2024-01-15 12:34:56 | market_orders        | INFO     | Placing MARKET order | {...}
2024-01-15 12:34:56 | market_orders        | INFO     | MARKET order result  | {...}
```

Log files rotate at 5 MB and keep 3 backups.

---

## Assumptions

- Only USDT-M perpetual futures are supported (symbols must end with `USDT`)
- LIMIT orders use `timeInForce=GTC` (Good Till Cancelled) by default
- Credentials are loaded from environment variables or a `.env` file — never hardcoded
- The testnet base URL is `https://testnet.binancefuture.com` (no real funds involved)

---

## Troubleshooting

| Error | Fix |
|-------|-----|
| `Missing API credentials` | Set `BINANCE_TESTNET_API_KEY` and `BINANCE_TESTNET_API_SECRET` |
| `Binance API error (code -1121)` | Invalid symbol — check spelling (e.g. `BTCUSDT`) |
| `Binance API error (code -2019)` | Insufficient margin — add test funds on the testnet |
| `Could not connect to Binance Testnet` | Check your internet connection |
| `Request timed out` | Testnet may be slow — retry in a moment |
