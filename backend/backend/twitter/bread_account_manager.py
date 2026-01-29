"""
Bread Account Manager

Manages per-account locks to prevent concurrent browser usage of the same account.
Jobs can run in parallel if they use different bread accounts.
"""
import asyncio
import random
from backend.twitter.bread_accounts import BREAD_ACCOUNTS
from backend.utlils.utils import notify


class BreadAccountManager:
    """
    Manages per-account locks to prevent concurrent browser usage.
    Jobs can run in parallel if they use different accounts.
    """

    def __init__(self):
        # One lock per bread account
        self._locks = {account[0]: asyncio.Lock() for account in BREAD_ACCOUNTS}

    async def acquire_account(self, job_identifier: str) -> tuple[str, str]:
        """
        Acquire an available bread account for exclusive use.

        Strategy:
        1. Try to acquire a random account (non-blocking)
        2. If busy, try other accounts
        3. If all busy, wait for any to become available

        Returns: (username, password)
        """
        # Shuffle accounts for random selection
        accounts = list(BREAD_ACCOUNTS)
        random.shuffle(accounts)

        # First pass: try to acquire any available account (non-blocking)
        for account_username, account_password in accounts:
            lock = self._locks[account_username]

            # Try to acquire without blocking
            if not lock.locked():
                acquired = await self._try_acquire(lock)
                if acquired:
                    notify(f"🔒 [Account Manager] {job_identifier} acquired {account_username}")
                    return (account_username, account_password)

        # All accounts busy - wait for first available
        notify(f"⏳ [Account Manager] All accounts busy, {job_identifier} waiting...")

        while True:
            for account_username, account_password in accounts:
                lock = self._locks[account_username]

                # Try to acquire (will wait if needed)
                acquired = await self._try_acquire(lock, timeout=1.0)
                if acquired:
                    notify(f"🔒 [Account Manager] {job_identifier} acquired {account_username} (after wait)")
                    return (account_username, account_password)

            # Brief pause before retry
            await asyncio.sleep(0.5)

    async def _try_acquire(self, lock: asyncio.Lock, timeout: float = 0) -> bool:
        """Try to acquire lock with optional timeout."""
        try:
            if timeout > 0:
                await asyncio.wait_for(lock.acquire(), timeout=timeout)
            else:
                # Non-blocking attempt
                if lock.locked():
                    return False
                await lock.acquire()
            return True
        except asyncio.TimeoutError:
            return False

    def release_account(self, account_username: str, job_identifier: str):
        """Release a bread account after job completes."""
        if account_username in self._locks:
            self._locks[account_username].release()
            notify(f"🔓 [Account Manager] {job_identifier} released {account_username}")
        else:
            notify(f"⚠️ [Account Manager] Unknown account: {account_username}")


# Global singleton
_manager = BreadAccountManager()


async def acquire_bread_account(job_identifier: str) -> tuple[str, str]:
    """Acquire an available bread account (blocks until one is free)."""
    return await _manager.acquire_account(job_identifier)


def release_bread_account(account_username: str, job_identifier: str):
    """Release a bread account."""
    _manager.release_account(account_username, job_identifier)
