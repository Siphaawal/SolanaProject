#!/usr/bin/env python3
"""
Test script for the new RPC-based snapshot discovery system
This will discover available snapshots without downloading them
"""

import logging
from snapshot_downloader import RPCSnapshotDiscovery, SnapshotDownloader

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_discovery():
    """Test the RPC snapshot discovery"""
    print("="*70)
    print("TESTING SNAPSHOT DISCOVERY SYSTEM")
    print("="*70)
    print()

    # Create discovery instance
    discovery = RPCSnapshotDiscovery(max_threads=20, timeout=10)

    # Discover snapshots
    snapshots = discovery.discover_snapshots(max_results=10)

    if snapshots:
        print(f"\n✓ SUCCESS! Found {len(snapshots)} snapshot sources\n")
        print("="*70)
        print("TOP SNAPSHOT SOURCES:")
        print("="*70)

        for i, snap in enumerate(snapshots, 1):
            age_slots = getattr(snap, 'slots_diff', 'unknown')
            print(f"\n#{i}")
            print(f"  Slot:     {snap.slot:,}")
            print(f"  Hash:     {snap.hash}")
            print(f"  Size:     {snap.size_gb:.2f} GB")
            print(f"  Latency:  {snap.latency_ms:.0f} ms")
            print(f"  Age:      {age_slots} slots behind")
            print(f"  RPC:      {snap.rpc_url}")
            print(f"  URL:      {snap.download_url}")
    else:
        print("\n✗ FAILED - No snapshots found")
        print("\nPossible reasons:")
        print("  1. Network connectivity issues")
        print("  2. No validators currently serving snapshots")
        print("  3. RPC endpoints are rate-limiting requests")

    print("\n" + "="*70)


def test_speed():
    """Test the speed testing functionality"""
    print("\n" + "="*70)
    print("TESTING DOWNLOAD SPEED CHECKER")
    print("="*70)
    print()

    downloader = SnapshotDownloader(
        snapshot_dir="./data/snapshots",
        min_download_speed_mbps=10.0,  # Lower threshold for testing
        speed_test_duration=3  # Quick 3-second test
    )

    print("Finding best snapshot (this will test download speeds)...\n")
    best = downloader.find_best_snapshot()

    if best:
        print("\n" + "="*70)
        print("✓ BEST SNAPSHOT FOUND:")
        print("="*70)
        print(f"  Slot:           {best.slot:,}")
        print(f"  Size:           {best.size_gb:.2f} GB")
        print(f"  Download Speed: {best.download_speed_mbps:.2f} Mbps")
        print(f"  Source:         {best.rpc_url}")
        print("="*70)
    else:
        print("\n✗ Could not find suitable snapshot")

    print()


if __name__ == "__main__":
    try:
        # Test 1: Discovery
        test_discovery()

        # Test 2: Speed testing
        test_speed()

        print("\n" + "="*70)
        print("TESTING COMPLETE")
        print("="*70)
        print("\nNext steps:")
        print("  1. Review the snapshot sources found above")
        print("  2. Run: python3 snapshot_downloader.py")
        print("  3. The system will automatically download from the best source")
        print()

    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        logger.error(f"Test failed with error: {e}", exc_info=True)
