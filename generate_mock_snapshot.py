"""
Generate Mock Solana Snapshot Data
Creates realistic mock data for visualization purposes
"""

import json
import random
from datetime import datetime, timedelta
from typing import List, Dict

class MockSnapshotGenerator:
    """Generate realistic mock Solana snapshot data"""

    def __init__(self):
        self.defi_protocols = [
            "Raydium", "Orca", "Jupiter", "Marinade", "Lido",
            "Serum", "Mango Markets", "Drift Protocol", "Kamino", "Meteora"
        ]

        self.token_names = [
            "SOL", "USDC", "USDT", "RAY", "ORCA", "JUP", "MSOL", "STSOL",
            "BONK", "WIF", "JTO", "PYTH", "W", "JLP", "MNDE"
        ]

    def generate_mock_pool(self, pool_id: int) -> Dict:
        """Generate a mock liquidity pool"""
        token_a = random.choice(self.token_names)
        token_b = random.choice([t for t in self.token_names if t != token_a])

        tvl = random.uniform(100000, 50000000)
        volume_24h = tvl * random.uniform(0.05, 0.5)
        fees_24h = volume_24h * 0.0025  # 0.25% fee
        apr = (fees_24h * 365 / tvl) * 100

        return {
            "pool_id": f"pool_{pool_id}",
            "address": self._generate_mock_address(),
            "protocol": random.choice(self.defi_protocols),
            "token_a": token_a,
            "token_b": token_b,
            "tvl_usd": round(tvl, 2),
            "volume_24h_usd": round(volume_24h, 2),
            "fees_24h_usd": round(fees_24h, 2),
            "apr_percentage": round(apr, 2),
            "liquidity_providers": random.randint(50, 5000),
            "created_at": self._random_date().isoformat(),
            "last_updated": datetime.now().isoformat()
        }

    def generate_mock_account(self, account_id: int) -> Dict:
        """Generate a mock Solana account"""
        account_types = ["Liquidity Pool", "Token Account", "Program", "Stake Account", "Vote Account"]

        return {
            "account_id": f"account_{account_id}",
            "address": self._generate_mock_address(),
            "type": random.choice(account_types),
            "owner": random.choice(self.defi_protocols),
            "lamports": random.randint(1000000, 100000000000),
            "data_size_bytes": random.randint(165, 10240),
            "executable": random.choice([True, False]),
            "rent_epoch": random.randint(400, 450)
        }

    def generate_mock_transaction(self, tx_id: int) -> Dict:
        """Generate a mock transaction"""
        tx_types = ["Swap", "Add Liquidity", "Remove Liquidity", "Stake", "Unstake", "Transfer"]

        amount = random.uniform(10, 100000)
        fee = random.uniform(0.000005, 0.00001) * 1000000000  # in lamports

        return {
            "transaction_id": f"tx_{tx_id}",
            "signature": self._generate_mock_signature(),
            "type": random.choice(tx_types),
            "from_token": random.choice(self.token_names),
            "to_token": random.choice(self.token_names),
            "amount_usd": round(amount, 2),
            "fee_lamports": int(fee),
            "status": random.choice(["Success"] * 95 + ["Failed"] * 5),
            "block_time": self._random_recent_datetime().isoformat(),
            "slot": random.randint(280000000, 290000000)
        }

    def generate_network_stats(self) -> Dict:
        """Generate mock network statistics"""
        return {
            "current_slot": random.randint(285000000, 290000000),
            "current_epoch": random.randint(600, 650),
            "total_accounts": random.randint(500000000, 600000000),
            "total_supply_sol": 580000000,
            "circulating_supply_sol": 470000000,
            "tps_current": round(random.uniform(2000, 4500), 2),
            "tps_average_24h": round(random.uniform(2500, 3500), 2),
            "validator_count": random.randint(2000, 2500),
            "stake_percentage": round(random.uniform(65, 75), 2)
        }

    def generate_defi_summary(self) -> Dict:
        """Generate DeFi ecosystem summary"""
        total_tvl = sum(random.uniform(100000000, 500000000) for _ in self.defi_protocols)

        protocol_tvls = []
        for protocol in self.defi_protocols:
            tvl = random.uniform(100000000, 500000000)
            protocol_tvls.append({
                "protocol": protocol,
                "tvl_usd": round(tvl, 2),
                "pools": random.randint(50, 500),
                "users_24h": random.randint(1000, 50000),
                "volume_24h_usd": round(tvl * random.uniform(0.1, 0.5), 2)
            })

        # Sort by TVL
        protocol_tvls.sort(key=lambda x: x["tvl_usd"], reverse=True)

        return {
            "total_tvl_usd": round(total_tvl, 2),
            "total_protocols": len(self.defi_protocols),
            "total_pools": sum(p["pools"] for p in protocol_tvls),
            "total_users_24h": sum(p["users_24h"] for p in protocol_tvls),
            "total_volume_24h_usd": sum(p["volume_24h_usd"] for p in protocol_tvls),
            "protocols": protocol_tvls
        }

    def generate_full_snapshot(self, num_pools: int = 50, num_accounts: int = 100, num_transactions: int = 200) -> Dict:
        """Generate a complete mock snapshot"""

        print(f"Generating mock Solana snapshot...")
        print(f"  - {num_pools} liquidity pools")
        print(f"  - {num_accounts} accounts")
        print(f"  - {num_transactions} transactions")

        snapshot = {
            "metadata": {
                "snapshot_type": "mock",
                "generated_at": datetime.now().isoformat(),
                "slot": random.randint(285000000, 290000000),
                "epoch": random.randint(600, 650),
                "version": "1.0.0",
                "description": "Mock Solana mainnet snapshot for visualization"
            },
            "network_stats": self.generate_network_stats(),
            "defi_summary": self.generate_defi_summary(),
            "liquidity_pools": [self.generate_mock_pool(i) for i in range(num_pools)],
            "accounts": [self.generate_mock_account(i) for i in range(num_accounts)],
            "recent_transactions": [self.generate_mock_transaction(i) for i in range(num_transactions)]
        }

        return snapshot

    def _generate_mock_address(self) -> str:
        """Generate a mock Solana address (base58)"""
        chars = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
        return ''.join(random.choice(chars) for _ in range(44))

    def _generate_mock_signature(self) -> str:
        """Generate a mock transaction signature"""
        chars = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
        return ''.join(random.choice(chars) for _ in range(88))

    def _random_date(self) -> datetime:
        """Generate a random date within the last year"""
        days_ago = random.randint(1, 365)
        return datetime.now() - timedelta(days=days_ago)

    def _random_recent_datetime(self) -> datetime:
        """Generate a random datetime within the last 24 hours"""
        seconds_ago = random.randint(0, 86400)
        return datetime.now() - timedelta(seconds=seconds_ago)


def main():
    """Generate and save mock snapshot data"""
    generator = MockSnapshotGenerator()

    # Generate snapshot
    snapshot = generator.generate_full_snapshot(
        num_pools=50,
        num_accounts=100,
        num_transactions=200
    )

    # Save to file
    output_file = "mock_snapshot.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(snapshot, f, indent=2, ensure_ascii=False)

    print(f"\n[SUCCESS] Mock snapshot generated successfully!")
    print(f"[SUCCESS] Saved to: {output_file}")
    print(f"\nSnapshot Summary:")
    print(f"  - Total TVL: ${snapshot['defi_summary']['total_tvl_usd']:,.2f}")
    print(f"  - Total Protocols: {snapshot['defi_summary']['total_protocols']}")
    print(f"  - Total Pools: {snapshot['defi_summary']['total_pools']}")
    print(f"  - 24h Volume: ${snapshot['defi_summary']['total_volume_24h_usd']:,.2f}")
    print(f"  - Network TPS: {snapshot['network_stats']['tps_current']}")
    print(f"  - Current Slot: {snapshot['metadata']['slot']}")


if __name__ == "__main__":
    main()
