"""
Daily Solana Snapshot Downloader & Local Analyzer
Downloads snapshots once per day instead of running full RPC node
Much lighter on resources - no continuous sync needed

UPDATED: Now uses RPC-based discovery to find snapshot endpoints dynamically
Inspired by community snapshot finder tools but completely rewritten
"""

import subprocess
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Tuple
import schedule
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import re

# pip install requests tqdm
import requests

# Optional progress bar
try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False
    # Fallback dummy progress bar
    class tqdm:
        def __init__(self, total=None, **kwargs):
            self.total = total
            self.n = 0
        def update(self, n):
            self.n += n
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('snapshot_downloader.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class SnapshotInfo:
    """Information about an available snapshot"""
    slot: int
    hash: str
    rpc_url: str
    download_url: str
    size_bytes: int = 0
    latency_ms: float = 0.0
    download_speed_mbps: float = 0.0
    is_incremental: bool = False

    @property
    def size_gb(self) -> float:
        return self.size_bytes / (1024**3) if self.size_bytes else 0.0


class RPCSnapshotDiscovery:
    """Discovers snapshot endpoints by querying RPC nodes"""

    # Known public RPC endpoints - these are used to discover validators
    SEED_RPC_ENDPOINTS = [
        "https://api.mainnet-beta.solana.com",
        "https://solana-api.projectserum.com",
        "https://rpc.ankr.com/solana",
        "https://solana.public-rpc.com",
    ]

    # Known validators/nodes that typically serve snapshots
    # These are more reliable than random cluster nodes
    KNOWN_SNAPSHOT_SERVERS = [
        "https://api.mainnet-beta.solana.com",
        "http://api.mainnet-beta.solana.com",
        "https://mainnet.rpcpool.com",
        "https://solana.getblock.io/mainnet",
        # Add more known snapshot servers here as you discover them
    ]

    def __init__(self, max_threads: int = 20, timeout: int = 10):
        self.max_threads = max_threads
        self.timeout = timeout
        self.current_slot: Optional[int] = None

    def get_current_slot(self, rpc_url: str) -> Optional[int]:
        """Get the current slot from RPC"""
        try:
            response = requests.post(
                rpc_url,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getSlot",
                    "params": [{"commitment": "finalized"}]
                },
                timeout=self.timeout
            )

            if response.status_code == 200:
                data = response.json()
                if 'result' in data:
                    return data['result']
        except Exception as e:
            logger.debug(f"Failed to get slot from {rpc_url}: {e}")
        return None

    def get_cluster_nodes(self, rpc_url: str) -> List[Dict]:
        """Get list of cluster nodes from RPC"""
        try:
            response = requests.post(
                rpc_url,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getClusterNodes",
                },
                timeout=self.timeout
            )

            if response.status_code == 200:
                data = response.json()
                if 'result' in data:
                    return data['result']
        except Exception as e:
            logger.debug(f"Failed to get cluster nodes from {rpc_url}: {e}")
        return []

    def check_snapshot_availability(self, rpc_url: str) -> Optional[SnapshotInfo]:
        """Check if an RPC node has snapshots available via getHighestSnapshotSlot"""
        try:
            # First, check if node has snapshot via RPC method
            response = requests.post(
                rpc_url,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getHighestSnapshotSlot",
                },
                timeout=self.timeout
            )

            if response.status_code == 200:
                data = response.json()
                if 'result' in data and data['result']:
                    snapshot_slot = data['result'].get('full', 0)
                    if snapshot_slot > 0:
                        logger.debug(f"{rpc_url}: Has snapshot at slot {snapshot_slot}")
                        # Try to construct HTTP download URL from RPC URL
                        # RPC: https://rpc.example.com or http://ip:8899
                        # Snapshot HTTP: http://ip:80 or http://hostname:80
                        http_url = self._construct_snapshot_url(rpc_url)

                        if http_url:
                            # Verify the snapshot is actually downloadable
                            snapshot_info = self._verify_snapshot_download(http_url, snapshot_slot)
                            if snapshot_info:
                                snapshot_info.rpc_url = rpc_url
                                return snapshot_info
                            else:
                                logger.debug(f"{rpc_url}: Snapshot not downloadable via HTTP")
                        else:
                            logger.debug(f"{rpc_url}: Could not construct HTTP URL")
                    else:
                        logger.debug(f"{rpc_url}: No full snapshot available")
                elif 'error' in data:
                    logger.debug(f"{rpc_url}: RPC error: {data['error']}")
                else:
                    logger.debug(f"{rpc_url}: No snapshot result in response")
            else:
                logger.debug(f"{rpc_url}: HTTP {response.status_code}")
        except requests.exceptions.Timeout:
            logger.debug(f"{rpc_url}: Timeout")
        except requests.exceptions.ConnectionError:
            logger.debug(f"{rpc_url}: Connection error")
        except Exception as e:
            logger.debug(f"{rpc_url}: {type(e).__name__}: {e}")
        return None

    def _construct_snapshot_url(self, rpc_url: str) -> Optional[str]:
        """Convert RPC URL to potential HTTP snapshot URL"""
        try:
            # Extract hostname/IP from RPC URL
            # Examples:
            # https://api.mainnet-beta.solana.com -> http://api.mainnet-beta.solana.com
            # http://192.168.1.1:8899 -> http://192.168.1.1

            from urllib.parse import urlparse
            parsed = urlparse(rpc_url)
            hostname = parsed.hostname

            if not hostname:
                return None

            # Try HTTP port 80 (standard for snapshot serving)
            return f"http://{hostname}"

        except Exception:
            return None

    def _verify_snapshot_download(self, base_url: str, slot: int) -> Optional[SnapshotInfo]:
        """Verify snapshot is downloadable and get metadata"""
        # Common snapshot file patterns on Solana nodes
        snapshot_paths = [
            "/snapshot.tar.bz2",  # Generic latest snapshot
            "/snapshot.tar.zst",
            f"/snapshot-{slot}*.tar.bz2",
            f"/snapshot-{slot}*.tar.zst",
        ]

        for path in snapshot_paths:
            try:
                url = base_url + path
                # HEAD request to check if file exists without downloading
                start_time = time.time()
                response = requests.head(url, timeout=5, allow_redirects=True)
                latency = (time.time() - start_time) * 1000  # ms

                if response.status_code == 200:
                    size = int(response.headers.get('content-length', 0))

                    # Extract actual slot and hash from redirected URL or filename
                    final_url = response.url if hasattr(response, 'url') else url
                    slot_match = re.search(r'snapshot-(\d+)-([A-Za-z0-9]+)', final_url)

                    if slot_match:
                        actual_slot = int(slot_match.group(1))
                        hash_str = slot_match.group(2)
                    else:
                        actual_slot = slot
                        hash_str = "unknown"

                    return SnapshotInfo(
                        slot=actual_slot,
                        hash=hash_str,
                        rpc_url="",  # Will be set by caller
                        download_url=final_url,
                        size_bytes=size,
                        latency_ms=latency
                    )

            except Exception as e:
                logger.debug(f"Failed to verify {url}: {e}")
                continue

        return None

    def discover_snapshots(self, max_results: int = 10) -> List[SnapshotInfo]:
        """Discover available snapshots from RPC network"""
        logger.info("Starting RPC-based snapshot discovery...")

        # Step 1: Get current network slot
        logger.info("Getting current network slot...")
        for rpc in self.SEED_RPC_ENDPOINTS:
            slot = self.get_current_slot(rpc)
            if slot:
                self.current_slot = slot
                logger.info(f"Current network slot: {slot:,}")
                break

        if not self.current_slot:
            logger.warning("Could not determine current slot, continuing anyway...")

        # Step 2: Collect RPC endpoints to check
        logger.info("Building list of RPC endpoints to check...")

        # Start with known snapshot servers (most reliable)
        rpc_endpoints = set(self.KNOWN_SNAPSHOT_SERVERS)
        logger.info(f"Added {len(self.KNOWN_SNAPSHOT_SERVERS)} known snapshot servers")

        # Also add seed endpoints
        rpc_endpoints.update(self.SEED_RPC_ENDPOINTS)

        # Try to get cluster nodes from seed RPCs for additional sources
        try:
            for seed_rpc in self.SEED_RPC_ENDPOINTS[:1]:  # Just check first one
                nodes = self.get_cluster_nodes(seed_rpc)
                if nodes:
                    logger.info(f"Found {len(nodes)} cluster nodes from {seed_rpc}")
                    # Extract RPC endpoints from node info
                    # Focus on nodes with RPC enabled
                    nodes_with_rpc = [n for n in nodes if n.get('rpc')]
                    logger.info(f"  {len(nodes_with_rpc)} have RPC enabled")

                    # Sample a larger set to increase chances
                    import random
                    sample_size = min(100, len(nodes_with_rpc))
                    sampled_nodes = random.sample(nodes_with_rpc, sample_size) if len(nodes_with_rpc) > sample_size else nodes_with_rpc

                    for node in sampled_nodes:
                        if node.get('rpc'):
                            # Construct RPC URL from node info
                            rpc_endpoints.add(f"http://{node.get('rpc')}")
                    break
        except Exception as e:
            logger.warning(f"Could not fetch cluster nodes: {e}")

        logger.info(f"Checking {len(rpc_endpoints)} RPC endpoints for snapshots...")

        # Step 3: Check each RPC for snapshot availability (multi-threaded)
        snapshots = []

        with ThreadPoolExecutor(max_workers=self.max_threads) as executor:
            future_to_rpc = {
                executor.submit(self.check_snapshot_availability, rpc): rpc
                for rpc in rpc_endpoints
            }

            with tqdm(total=len(future_to_rpc), desc="Scanning RPCs") as pbar:
                for future in as_completed(future_to_rpc):
                    rpc = future_to_rpc[future]
                    try:
                        snapshot_info = future.result()
                        if snapshot_info:
                            snapshots.append(snapshot_info)
                            logger.info(f"✓ Found snapshot at {rpc}: slot {snapshot_info.slot:,}")
                    except Exception as e:
                        logger.debug(f"Error checking {rpc}: {e}")
                    finally:
                        pbar.update(1)

        # Step 4: Sort by freshness and latency
        if self.current_slot and snapshots:
            # Calculate slot difference (freshness)
            for snapshot in snapshots:
                snapshot.slots_diff = self.current_slot - snapshot.slot

            # Sort by: freshness first (lower slots_diff = newer), then latency
            snapshots.sort(key=lambda s: (getattr(s, 'slots_diff', 999999), s.latency_ms))
        else:
            # Just sort by latency
            snapshots.sort(key=lambda s: s.latency_ms)

        logger.info(f"Found {len(snapshots)} available snapshots")

        if len(snapshots) == 0:
            logger.warning("="*60)
            logger.warning("NO SNAPSHOTS FOUND")
            logger.warning("="*60)
            logger.warning("This is normal! Here's why:")
            logger.warning("")
            logger.warning("1. MOST validators don't serve snapshots via HTTP")
            logger.warning("   - Out of 6,000+ validators, only ~10-50 typically do")
            logger.warning("   - Many validators disable HTTP serving to save bandwidth")
            logger.warning("")
            logger.warning("2. Validators that DO serve snapshots:")
            logger.warning("   - Often use private/internal networks")
            logger.warning("   - May require authentication")
            logger.warning("   - Change their HTTP endpoints frequently")
            logger.warning("")
            logger.warning("3. Solutions:")
            logger.warning("   a) Try again (different random sample)")
            logger.warning("   b) Use the c29r3/solana-snapshot-finder tool")
            logger.warning("   c) Ask in Solana Discord for current snapshot URLs")
            logger.warning("   d) Run your own validator to generate snapshots")
            logger.warning("")
            logger.warning("Run with DEBUG logging to see why each node failed:")
            logger.warning("  export LOG_LEVEL=DEBUG")
            logger.warning("  python3 test_snapshot_discovery.py")
            logger.warning("="*60)

        return snapshots[:max_results]


class SnapshotDownloader:
    """Downloads Solana snapshots on a schedule"""

    def __init__(self,
                 snapshot_dir: str = "./snapshots",
                 ledger_dir: str = "./ledger",
                 min_download_speed_mbps: float = 50.0,
                 speed_test_duration: int = 5):
        self.snapshot_dir = Path(snapshot_dir)
        self.ledger_dir = Path(ledger_dir)
        self.current_snapshot = None
        self.min_download_speed_mbps = min_download_speed_mbps
        self.speed_test_duration = speed_test_duration
        self.discovery = RPCSnapshotDiscovery()

        # Create directories
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        self.ledger_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Initialized SnapshotDownloader")
        logger.info(f"  Snapshot dir: {self.snapshot_dir}")
        logger.info(f"  Ledger dir: {self.ledger_dir}")
        logger.info(f"  Min download speed: {self.min_download_speed_mbps} Mbps")
        logger.info(f"  Using RPC-based snapshot discovery")

    def test_download_speed(self, snapshot_info: SnapshotInfo) -> float:
        """Test download speed by downloading first few MB"""
        try:
            logger.info(f"Testing download speed from {snapshot_info.rpc_url}...")

            start_time = time.time()
            bytes_downloaded = 0
            target_bytes = 10 * 1024 * 1024  # Download 10MB for testing

            response = requests.get(
                snapshot_info.download_url,
                stream=True,
                timeout=30,
                headers={'Range': f'bytes=0-{target_bytes}'}
            )

            if response.status_code in [200, 206]:  # 206 = Partial Content
                for chunk in response.iter_content(chunk_size=1024*1024):  # 1MB chunks
                    if chunk:
                        bytes_downloaded += len(chunk)
                        elapsed = time.time() - start_time

                        # Stop after speed_test_duration seconds or target bytes
                        if elapsed >= self.speed_test_duration or bytes_downloaded >= target_bytes:
                            break

                elapsed = time.time() - start_time
                if elapsed > 0:
                    # Calculate speed in Mbps (megabits per second)
                    speed_mbps = (bytes_downloaded * 8) / (elapsed * 1_000_000)
                    logger.info(f"Download speed: {speed_mbps:.2f} Mbps ({bytes_downloaded/(1024*1024):.2f} MB in {elapsed:.1f}s)")
                    return speed_mbps

        except Exception as e:
            logger.warning(f"Speed test failed: {e}")

        return 0.0

    def find_best_snapshot(self) -> Optional[SnapshotInfo]:
        """Find the best snapshot source using RPC discovery"""
        # Discover available snapshots
        snapshots = self.discovery.discover_snapshots(max_results=20)

        if not snapshots:
            logger.error("No snapshots found via RPC discovery")
            return None

        logger.info(f"\nFound {len(snapshots)} snapshot sources:")
        for i, snap in enumerate(snapshots[:5], 1):
            age_slots = getattr(snap, 'slots_diff', 'unknown')
            logger.info(f"  {i}. Slot {snap.slot:,} | Size: {snap.size_gb:.1f} GB | Latency: {snap.latency_ms:.0f}ms | Age: {age_slots} slots")

        # Test download speeds for top candidates
        logger.info(f"\nTesting download speeds (minimum required: {self.min_download_speed_mbps} Mbps)...")

        best_snapshot = None
        for snapshot in snapshots[:10]:  # Test top 10
            speed = self.test_download_speed(snapshot)
            snapshot.download_speed_mbps = speed

            if speed >= self.min_download_speed_mbps:
                logger.info(f"✓ Found suitable snapshot: {speed:.2f} Mbps from {snapshot.rpc_url}")
                best_snapshot = snapshot
                break
            else:
                logger.info(f"✗ Too slow ({speed:.2f} Mbps < {self.min_download_speed_mbps} Mbps), trying next...")

        if not best_snapshot and snapshots:
            # Fallback: use the fastest one even if below threshold
            logger.warning(f"No snapshot met speed threshold, using fastest available")
            snapshots_with_speed = [s for s in snapshots if s.download_speed_mbps > 0]
            if snapshots_with_speed:
                best_snapshot = max(snapshots_with_speed, key=lambda s: s.download_speed_mbps)

        return best_snapshot

    def download_snapshot_from_source(self, snapshot_info: SnapshotInfo) -> bool:
        """Download a specific snapshot from the given source"""
        try:
            logger.info("="*60)
            logger.info(f"Downloading snapshot from selected source")
            logger.info(f"  Slot: {snapshot_info.slot:,}")
            logger.info(f"  Size: {snapshot_info.size_gb:.2f} GB")
            logger.info(f"  Speed: {snapshot_info.download_speed_mbps:.2f} Mbps")
            logger.info(f"  Source: {snapshot_info.rpc_url}")
            logger.info(f"  URL: {snapshot_info.download_url}")
            logger.info("="*60)

            # Determine filename from URL
            filename = snapshot_info.download_url.split('/')[-1]
            # Handle query parameters
            if '?' in filename:
                filename = filename.split('?')[0]

            snapshot_file = self.snapshot_dir / filename

            logger.info(f"Saving to: {snapshot_file}")

            # Estimate time based on speed test
            if snapshot_info.download_speed_mbps > 0:
                estimated_minutes = (snapshot_info.size_gb * 8 * 1024) / snapshot_info.download_speed_mbps / 60
                logger.info(f"Estimated download time: {estimated_minutes:.0f} minutes")

            # Download with streaming and progress bar
            response = requests.get(snapshot_info.download_url, stream=True, timeout=7200)

            if response.status_code == 200:
                total_size = int(response.headers.get('content-length', 0))
                if total_size == 0:
                    total_size = snapshot_info.size_bytes

                downloaded = 0
                chunk_size = 8 * 1024 * 1024  # 8MB chunks for efficiency

                # Progress bar
                with tqdm(total=total_size, unit='B', unit_scale=True, desc="Downloading") as pbar:
                    with open(snapshot_file, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=chunk_size):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                pbar.update(len(chunk))

                logger.info(f"✓ Snapshot downloaded successfully to {snapshot_file}")

                # Save metadata
                self.current_snapshot = snapshot_info.slot
                self.save_metadata(snapshot_info.slot, snapshot_file.name, snapshot_info)

                return True
            else:
                logger.error(f"Download failed: HTTP {response.status_code}")
                return False

        except requests.exceptions.Timeout:
            logger.error("Download timed out after 2 hours")
            return False
        except Exception as e:
            logger.error(f"Error downloading snapshot: {e}")
            return False

    def save_metadata(self, slot: int, filename: str = None, snapshot_info: Optional[SnapshotInfo] = None):
        """Save snapshot metadata"""
        metadata = {
            'slot': slot,
            'downloaded_at': datetime.now().isoformat(),
            'snapshot_dir': str(self.snapshot_dir),
            'ledger_dir': str(self.ledger_dir),
            'filename': filename
        }

        if snapshot_info:
            metadata.update({
                'hash': snapshot_info.hash,
                'source_rpc': snapshot_info.rpc_url,
                'download_url': snapshot_info.download_url,
                'size_bytes': snapshot_info.size_bytes,
                'download_speed_mbps': snapshot_info.download_speed_mbps
            })

        metadata_file = self.snapshot_dir / 'metadata.json'
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)

        logger.info(f"Metadata saved for slot {slot}")

    def load_snapshot_to_ledger(self, slot: int) -> bool:
        """Extract snapshot into ledger for querying"""
        try:
            logger.info(f"Loading snapshot {slot} into ledger...")

            snapshot_file = self.snapshot_dir / f"snapshot-{slot}-*.tar.zst"
            snapshot_files = list(self.snapshot_dir.glob(f"snapshot-{slot}-*.tar.zst"))

            if not snapshot_files:
                logger.error(f"Snapshot file not found for slot {slot}")
                return False

            snapshot_path = snapshot_files[0]

            # Use solana-ledger-tool to extract
            result = subprocess.run([
                'solana-ledger-tool',
                'create-snapshot',
                str(slot),
                str(self.ledger_dir),
                '--snapshot-archive-path', str(snapshot_path)
            ], capture_output=True, text=True, timeout=1800)

            if result.returncode == 0:
                logger.info("Snapshot loaded into ledger")
                return True
            else:
                logger.error(f"Failed to load snapshot: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Error loading snapshot: {e}")
            return False

    def cleanup_old_snapshots(self, keep_latest: int = 2):
        """Delete old snapshots to save disk space"""
        try:
            # Support multiple snapshot formats (.tar.zst, .tar.bz2)
            snapshot_patterns = ["snapshot*.tar.zst", "snapshot*.tar.bz2", "incremental-snapshot*.tar.bz2"]
            snapshot_files = []

            for pattern in snapshot_patterns:
                snapshot_files.extend(self.snapshot_dir.glob(pattern))

            # Sort by modification time (newest first)
            snapshot_files = sorted(
                snapshot_files,
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )

            # Keep only the latest N snapshots
            for old_snapshot in snapshot_files[keep_latest:]:
                logger.info(f"Removing old snapshot: {old_snapshot.name}")
                old_snapshot.unlink()

            if len(snapshot_files) > keep_latest:
                logger.info(f"Cleaned up {len(snapshot_files) - keep_latest} old snapshots")

        except Exception as e:
            logger.error(f"Error cleaning up snapshots: {e}")

    def daily_snapshot_routine(self):
        """Main routine to run once per day"""
        logger.info("="*60)
        logger.info(f"Starting daily snapshot routine at {datetime.now()}")
        logger.info("="*60)

        # Check if we already have a recent snapshot
        metadata_file = self.snapshot_dir / 'metadata.json'
        if metadata_file.exists():
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
                downloaded_at = datetime.fromisoformat(metadata.get('downloaded_at', '2000-01-01'))
                hours_since_download = (datetime.now() - downloaded_at).total_seconds() / 3600

                # Only download if snapshot is older than 23 hours
                if hours_since_download < 23:
                    logger.info(f"Recent snapshot exists (downloaded {hours_since_download:.1f} hours ago)")
                    logger.info(f"Skipping download. Next download scheduled after 23 hours.")
                    return

        # Find best snapshot source
        logger.info("Discovering snapshot sources...")
        best_snapshot = self.find_best_snapshot()

        if not best_snapshot:
            logger.error("Could not find any suitable snapshot source")
            logger.info("This may be due to:")
            logger.info("  1. Network connectivity issues")
            logger.info("  2. No validators currently serving snapshots via HTTP")
            logger.info("  3. All sources are too slow")
            logger.info("\nAlternative: Run a full Solana validator to sync from scratch")
            return

        # Download the snapshot
        success = self.download_snapshot_from_source(best_snapshot)

        if not success:
            logger.error("Snapshot download failed")
            return

        # Cleanup old snapshots
        self.cleanup_old_snapshots(keep_latest=2)

        logger.info("="*60)
        logger.info(f"✓ Daily snapshot routine completed at {datetime.now()}")
        logger.info("="*60)


class SnapshotAnalyzer:
    """Analyze DeFi data from downloaded snapshots"""

    def __init__(self, ledger_dir: str = "./ledger", rpc_url: str = "https://api.mainnet-beta.solana.com"):
        self.ledger_dir = Path(ledger_dir)
        self.rpc_url = rpc_url
        logger.info(f"Initialized SnapshotAnalyzer with ledger: {self.ledger_dir}")

    def query_account(self, pubkey: str) -> Optional[Dict]:
        """Query account data from snapshot"""
        try:
            logger.info(f"Querying account: {pubkey}")
            result = subprocess.run([
                'solana-ledger-tool',
                'account',
                pubkey,
                '--ledger', str(self.ledger_dir)
            ], capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                # Parse output
                return {'data': result.stdout, 'success': True}
            else:
                return {'error': result.stderr, 'success': False}

        except Exception as e:
            logger.error(f"Error querying account: {e}")
            return {'error': str(e), 'success': False}

    def query_program_accounts(self, program_id: str) -> List[str]:
        """Get all accounts owned by a program"""
        try:
            logger.info(f"Querying program accounts: {program_id}")
            # Note: solana-ledger-tool in 1.18.26 doesn't support --program-id filter
            # Instead, we would need to:
            # 1. Use the RPC API (getProgramAccounts) if we have an RPC node
            # 2. Or parse the full accounts output from ledger-tool
            # For now, use RPC API

            response = requests.post(
                self.rpc_url,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getProgramAccounts",
                    "params": [
                        program_id,
                        {"encoding": "base64", "dataSlice": {"offset": 0, "length": 0}}
                    ]
                },
                timeout=60
            )

            if response.status_code == 200:
                data = response.json()
                if 'result' in data:
                    accounts = [acc['pubkey'] for acc in data['result']]
                    logger.info(f"Found {len(accounts)} accounts")
                    return accounts

            logger.warning("Using RPC API for account queries (snapshot-based queries not yet implemented)")
            return []

        except Exception as e:
            logger.error(f"Error querying program accounts: {e}")
            return []

    def extract_defi_metrics(self, program_id: str) -> Dict:
        """Extract DeFi metrics from snapshot"""
        logger.info(f"Analyzing DeFi data for program: {program_id}")

        # Get all accounts for this program
        accounts = self.query_program_accounts(program_id)

        # Analyze each account
        metrics = {
            'program_id': program_id,
            'total_accounts': len(accounts),
            'analyzed_at': datetime.now().isoformat(),
            'pools': []
        }

        return metrics


def check_prerequisites() -> bool:
    """Check if required tools are installed"""
    logger.info("Checking prerequisites...")

    # Check Solana CLI
    try:
        result = subprocess.run(['solana', '--version'],
                              capture_output=True, check=True)
        version = result.stdout.decode().strip()
        logger.info(f"Solana CLI found: {version}")
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.error("Solana CLI not found!")
        logger.error("Install with: sh -c \"$(curl -sSfL https://release.solana.com/stable/install)\"")
        return False

    # Check solana-ledger-tool
    try:
        result = subprocess.run(['solana-ledger-tool', '--version'],
                              capture_output=True, check=True)
        version = result.stdout.decode().strip()
        logger.info(f"Solana ledger tool found: {version}")
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.warning("solana-ledger-tool not found - ledger operations will fail")
        logger.warning("This is typically installed with Solana CLI")

    return True


def main():
    """Main execution with scheduling"""

    logger.info("Solana Daily Snapshot System")
    logger.info("=" * 60)

    # Check prerequisites
    if not check_prerequisites():
        return

    # Initialize downloader
    downloader = SnapshotDownloader(
        snapshot_dir="./data/snapshots",
        ledger_dir="./data/ledger",
        min_download_speed_mbps=50.0,  # Require at least 50 Mbps
        speed_test_duration=5  # Test for 5 seconds
    )

    # Initialize analyzer
    analyzer = SnapshotAnalyzer(
        ledger_dir="./data/ledger",
        rpc_url="https://api.mainnet-beta.solana.com"
    )

    logger.info("Configuration loaded successfully")
    logger.info("=" * 60)

    # Run immediately on startup
    logger.info("\nRunning initial snapshot download...")
    downloader.daily_snapshot_routine()

    # Schedule daily at 10:15 PM
    schedule.every().day.at("22:15").do(downloader.daily_snapshot_routine)

    logger.info("\nScheduler started - snapshots will download daily at 10:15 PM")
    logger.info("Press Ctrl+C to stop\n")

    # Example: Analyze Raydium after download
    logger.info("\nExample analysis after snapshot:")
    raydium_program = "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"
    metrics = analyzer.extract_defi_metrics(raydium_program)
    logger.info(f"Metrics: {json.dumps(metrics, indent=2)}")

    # Keep running and check schedule
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    except KeyboardInterrupt:
        logger.info("\n\nShutting down gracefully...")


if __name__ == "__main__":
    main()
