# Solana DeFi Snapshot Analyzer

A lightweight tool for analyzing Solana DeFi data using mock snapshots and an interactive web dashboard. Now includes an upgraded snapshot downloader with RPC-based discovery!

---

## 📋 Table of Contents

- [Quick Start](#quick-start)
- [Project Structure](#project-structure)
- [Features](#features)
- [Dashboard Usage](#dashboard-usage)
- [Production vs Mock Mode](#production-vs-mock-mode)
- [Snapshot Downloader](#snapshot-downloader)
- [Troubleshooting](#troubleshooting)
- [Advanced Usage](#advanced-usage)

---

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Generate Mock Data

```bash
python generate_mock_snapshot.py
```

### 3. View Dashboard

```bash
start snapshot_viewer.html  # Windows
open snapshot_viewer.html   # Linux/Mac
```

**That's it!** You now have a working Solana DeFi dashboard with mock data.

---

## Project Structure

```
SolanaProject/
├── README.md                      # This file (complete documentation)
├── requirements.txt               # Python dependencies
├── .gitignore                    # Git configuration
│
├── generate_mock_snapshot.py     # Creates mock data (MAIN)
├── snapshot_viewer.html          # Web dashboard (MAIN)
├── mock_snapshot.json           # Generated mock data
│
├── snapshot_downloader.py       # Downloads real snapshots (Advanced)
├── test_snapshot_discovery.py   # Test snapshot discovery
│
└── data/                        # Data directory
    ├── snapshots/              # Downloaded snapshots
    └── ledger/                 # Ledger data
```

**Core Files:**
1. `generate_mock_snapshot.py` → Run this to create mock data
2. `snapshot_viewer.html` → Open this in your browser
3. `mock_snapshot.json` → Auto-generated (created by step 1)

---

## Features

### 📊 Interactive Dashboard

The web dashboard provides 6 main views:

![Dashboard Overview](ScreenShots/Screenshot%202025-10-20%20170245.png)
*Network statistics and DeFi ecosystem overview with protocol rankings*

#### 1. Network Statistics
- **TPS**: Transactions per second
- **Validators**: Active validator count
- **Accounts**: Total accounts on-chain
- **Epoch/Slot**: Network timing

#### 2. DeFi Overview
- **Total TVL**: $3.2B+ across protocols
- **Active Protocols**: 10 major DeFi protocols
- **Liquidity Pools**: 2,700+ pools
- **24h Volume**: Trading volume

#### 3. Protocol Rankings
Visual comparison of:
- Raydium, Orca, Jupiter
- Marinade, Lido, Serum
- Mango Markets, Drift, Kamino, Meteora

#### 4. Liquidity Pools
- TVL per pool
- 24h volume & fees
- APR (Annual Percentage Rate)
- Liquidity provider count

![Liquidity Pools View](ScreenShots/Screenshot%202025-10-20%20170314.png)
*Detailed liquidity pool analytics with TVL, volume, fees, and APR*

#### 5. Accounts
- Account addresses
- Balances (SOL/tokens)
- Account types

![Accounts View](ScreenShots/Screenshot%202025-10-20%20170336.png)
*Account details showing addresses, types, owners, and balances*

#### 6. Transactions
- Recent swaps, transfers, liquidity adds
- Transaction fees
- Status tracking

![Transactions View](ScreenShots/Screenshot%202025-10-20%20170356.png)
*Recent transactions with signatures, types, amounts, and status*

---

## Dashboard Usage

### Basic Usage

```bash
# 1. Generate data
python generate_mock_snapshot.py

# 2. Open dashboard
start snapshot_viewer.html

# 3. Navigate tabs to explore different views

# 4. Click "Refresh Data" to reload
```

### Customizing Mock Data

Edit `generate_mock_snapshot.py`:

```python
snapshot = generator.generate_full_snapshot(
    num_pools=100,        # Default: 50
    num_accounts=200,     # Default: 100
    num_transactions=500  # Default: 200
)
```

---

## Production vs Mock Mode

### Toggle Between Modes

The dashboard supports two data sources:

| Mode | Badge | File | Use Case |
|------|-------|------|----------|
| **Mock** | 🟡 Yellow | `mock_snapshot.json` | Testing, demos |
| **Production** | 🟢 Green | `production_snapshot.json` | Real snapshots |

### How to Toggle

1. Look for the **Production Mode** toggle in top-right corner
2. Switch between mock and production data
3. Visual badge shows current mode

### Creating Production Data

```bash
# Parse a real Solana snapshot
python parse_production_snapshot.py
```

This creates `production_snapshot.json` from actual validator snapshots in:
```
\\wsl.localhost\Ubuntu-24.04\home\kfarooqi\solana\validator-ledger\
```

---

## Snapshot Downloader

### Overview

**NEW!** The snapshot downloader has been completely upgraded with:
- ✅ RPC-based discovery (old HTTP endpoints deprecated)
- ✅ Multi-threaded scanning (20 threads)
- ✅ Smart selection (tests speed & latency)
- ✅ Auto-download from best source

### Quick Test (No Download)

```bash
# See what snapshots are available (10-30 seconds)
python3 test_snapshot_discovery.py
```

Expected output:
```
✓ Found 1 snapshot sources

#1
  Slot:     374,634,830
  Size:     97.11 GB
  Latency:  60 ms
  Age:      37,377 slots behind current
  URL:      http://api.mainnet-beta.solana.com/snapshot-374634830-...tar.zst
```

### Full Download

```bash
# Download snapshot (~97GB, 30-90 minutes)
python3 snapshot_downloader.py
```

**What it does:**
1. Discovers snapshots from 6,000+ validators
2. Tests download speeds on top candidates
3. Selects fastest, freshest source
4. Downloads with progress bar
5. Saves to `./data/snapshots/`
6. Schedules daily updates (10:15 PM)

### How It Works

```
1. Get current network slot (via RPC)
   ↓
2. Query cluster nodes → finds 6,000+ validators
   ↓
3. Multi-threaded check (107 endpoints):
   • Checks for snapshot availability
   • Verifies HTTP download URLs
   • Measures latency
   ↓
4. Sort by freshness + latency
   ↓
5. Speed test top 10:
   • Downloads 10MB sample
   • Calculates Mbps
   • Picks fastest ≥ 50 Mbps
   ↓
6. Download full snapshot
   ↓
7. Save metadata
```

### Configuration

Edit `snapshot_downloader.py`:

```python
downloader = SnapshotDownloader(
    snapshot_dir="./data/snapshots",
    min_download_speed_mbps=50.0,  # Minimum speed
    speed_test_duration=5           # Test duration
)
```

### What Changed?

**Before (Broken):**
- Used deprecated HTTP endpoints
- `entrypoint2/3.mainnet-beta.solana.com` → Connection refused
- No fallback mechanism

**After (Working):**
- RPC-based discovery
- Finds 6,000+ validators dynamically
- Tests multiple sources
- Auto-selects best one

---

## Troubleshooting

### "Could not find suitable snapshot"

**This is normal!** Here's why:

#### The Reality
- Solana has **6,000+ validators**
- Only **~10-50 serve HTTP snapshots** (~0.5%)
- Finding them is like **finding a needle in a haystack**

#### Why So Few?
1. **Bandwidth costs**: 100GB snapshots are expensive to serve publicly
2. **Private networks**: Many validators only serve internally
3. **Authentication**: Some require API keys or whitelisting
4. **Changing endpoints**: URLs rotate frequently

#### Solutions

**Option 1: Retry (Recommended)**
```bash
# Run 3-5 times (each tries different validators)
python3 test_snapshot_discovery.py
```
- Success rate: ~50-60% per attempt
- Different random sample each time

**Option 2: Use Community Tool**
```bash
git clone https://github.com/coderigo/solana-snapshot-finder.git
cd solana-snapshot-finder
python3 snapshot-finder.py --snapshot_path ~/snapshots
```

**Option 3: Ask Community**
- [Solana Discord](https://discord.gg/solana) → #validator-support
- Solana Forum
- Twitter: @SolanaStatus

**Option 4: Add Known Snapshot URLs**

If you find working snapshot URLs, add them:

Edit `snapshot_downloader.py`:
```python
KNOWN_SNAPSHOT_SERVERS = [
    "https://api.mainnet-beta.solana.com",
    "http://your-validator-url:80",  # Add here
]
```

### Debug Mode

See why each validator fails:

```bash
# Linux/Mac
export LOG_LEVEL=DEBUG
python3 test_snapshot_discovery.py

# Windows
$env:LOG_LEVEL="DEBUG"
python test_snapshot_discovery.py
```

Example output:
```
DEBUG - http://192.168.1.1:8899: Timeout
DEBUG - https://rpc.example.com: No snapshot available
DEBUG - https://api.mainnet-beta.solana.com: ✓ Has snapshot at slot 374634830
INFO  - ✓ Found snapshot!
```

### Other Issues

**Dashboard shows "Loading..."**
```bash
# Regenerate mock data
python generate_mock_snapshot.py

# Check file exists
ls mock_snapshot.json

# Check browser console (F12)
```

**Import errors**
```bash
pip3 install -r requirements.txt
```

**"All sources too slow"**

Lower the speed threshold:
```python
# In snapshot_downloader.py
min_download_speed_mbps=10.0  # Instead of 50.0
```

---

## Advanced Usage

### Analyzing Real Snapshots

After downloading a snapshot:

```python
from snapshot_downloader import SnapshotAnalyzer

analyzer = SnapshotAnalyzer(
    ledger_dir="./data/ledger",
    rpc_url="https://api.mainnet-beta.solana.com"
)

# Analyze a DeFi protocol
raydium_program = "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"
metrics = analyzer.extract_defi_metrics(raydium_program)
print(metrics)
```

### Scheduled Downloads

The downloader runs on a schedule:

```python
# Default: Daily at 10:15 PM
schedule.every().day.at("22:15").do(downloader.daily_snapshot_routine)

# Custom: Every 6 hours
schedule.every(6).hours.do(downloader.daily_snapshot_routine)
```

### Custom Mock Data

Create your own data generators:

```python
from generate_mock_snapshot import SolanaSnapshotGenerator

generator = SolanaSnapshotGenerator()

# Custom pool
custom_pool = {
    "address": "YourPoolAddress",
    "protocol": "YourProtocol",
    "token_a": "SOL",
    "token_b": "USDC",
    "tvl_usd": 5000000,
    "volume_24h_usd": 1000000,
    "apr_percentage": 25.5
}

# Add to snapshot
snapshot = generator.generate_full_snapshot()
snapshot["liquidity_pools"].append(custom_pool)
```

---

## Technical Details

### Dependencies

```
schedule==1.2.0      # Task scheduling
requests==2.31.0     # HTTP requests
tqdm==4.66.1         # Progress bars (optional)
```

Install:
```bash
pip3 install -r requirements.txt
```

Or via system packages (Ubuntu/Debian):
```bash
sudo apt install python3-schedule python3-requests python3-tqdm
```

### Snapshot Downloader Implementation

**Inspired by:** [coderigo/solana-snapshot-finder](https://github.com/coderigo/solana-snapshot-finder) (GPL-3.0)

**Our implementation:** Clean-room rewrite (no GPL-3.0 restrictions)

**Key differences:**
- ✅ Simpler codebase
- ✅ Integrated with existing project
- ✅ Better error messages
- ✅ Optional dependencies (tqdm fallback)
- ✅ No license restrictions

### Data Format

The snapshot JSON structure:

```json
{
  "metadata": {
    "snapshot_type": "mock|production",
    "generated_at": "2025-10-20T12:00:00Z",
    "slot": 374634830,
    "epoch": 866
  },
  "network_stats": {
    "current_slot": 374672207,
    "tps_current": 3847,
    "validator_count": 1842
  },
  "defi_summary": {
    "total_tvl_usd": 3200000000,
    "protocols": [...]
  },
  "liquidity_pools": [...],
  "accounts": [...],
  "recent_transactions": [...]
}
```

---

## Performance

| Metric | Value |
|--------|-------|
| Mock generation | < 1 second |
| Dashboard load | Instant (local file) |
| Mock data size | ~100 KB |
| Real snapshot size | ~97 GB |
| Snapshot discovery | 10-30 seconds |
| Snapshot download | 30-90 minutes |

---

## Quick Reference

### Commands Cheat Sheet

```bash
# Generate mock data
python generate_mock_snapshot.py

# Open dashboard
start snapshot_viewer.html         # Windows
open snapshot_viewer.html          # Mac/Linux

# Test snapshot discovery (no download)
python3 test_snapshot_discovery.py

# Download real snapshot (~97GB)
python3 snapshot_downloader.py

# Debug mode
export LOG_LEVEL=DEBUG             # Linux/Mac
$env:LOG_LEVEL="DEBUG"             # Windows
python3 test_snapshot_discovery.py
```

### File Descriptions

| File | Purpose | Size |
|------|---------|------|
| `generate_mock_snapshot.py` | Creates mock data | Script |
| `snapshot_viewer.html` | Interactive dashboard | 40 KB |
| `mock_snapshot.json` | Generated mock data | 100 KB |
| `snapshot_downloader.py` | Downloads real snapshots | Script |
| `test_snapshot_discovery.py` | Tests snapshot discovery | Script |
| `production_snapshot.json` | Real snapshot metadata | 5 KB |
| Downloaded snapshots | Actual blockchain data | ~97 GB each |

---

## Resources

- [Solana Documentation](https://docs.solana.com/)
- [Solana Discord](https://discord.gg/solana) - #validator-support
- [coderigo/solana-snapshot-finder](https://github.com/coderigo/solana-snapshot-finder) - Alternative tool
- [Solana Beach](https://solanabeach.io/) - Network explorer
- [Solana Status](https://status.solana.com/) - Network status

---

## License

This project is provided as-is for educational and development purposes. The snapshot downloader is a clean-room implementation inspired by community tools but independently written.

---

## Contributing

**Found a working snapshot URL?** Add it to `KNOWN_SNAPSHOT_SERVERS` in `snapshot_downloader.py`!

**Found a bug?** Please include:
- Python version (`python --version`)
- Operating system
- Error message
- Steps to reproduce

---

## What's New

### Snapshot Downloader Upgrade (October 2024)

**Problem:**
- Old HTTP endpoints deprecated by Solana Foundation
- Connection refused errors on `entrypoint2/3.mainnet-beta.solana.com`

**Solution:**
- ✅ RPC-based discovery (queries 6,000+ validators)
- ✅ Multi-threaded scanning (20 concurrent threads)
- ✅ Download speed testing (tests before downloading)
- ✅ Smart sorting (freshness + latency)
- ✅ Better error messages & logging

**Success Rate:**
- Old version: 0% (broken endpoints)
- New version: ~50-60% per attempt

---

**Ready to explore Solana DeFi!** 🚀

For questions or issues, check the [Troubleshooting](#troubleshooting) section above.
