"""
Unified cache management with atomic operations.
Supports both list-based and map-based caches with Pydantic validation.
"""

import json
from pathlib import Path
from typing import Any, Callable, Generic, Literal, TypeVar

from pydantic import BaseModel, ValidationError

from backend.utlils.utils import atomic_file_update, error, notify

T = TypeVar("T", bound=BaseModel)


class CacheManager(Generic[T]):
    """
    Unified cache management with atomic operations.
    Supports both list-based and map-based caches.

    Usage:
        # List-based cache (e.g., edit_cache.py)
        cache_mgr = CacheManager(
            path=get_user_interactions_log(username),
            model_class=ScrapedTweet,
            cache_type="list"
        )

        # Map-based cache (e.g., comments_cache.py)
        cache_mgr = OrderedMapCache(
            path=COMMENTS_CACHE_FILE,
            model_class=CommentRecord,
        )
    """

    def __init__(
        self,
        path: Path,
        model_class: type[T],
        cache_type: Literal["list", "map"] = "list",
        tmp_suffix: str = ".tmp",
    ):
        self.path = path
        self.model_class = model_class
        self.cache_type = cache_type
        self.tmp_suffix = tmp_suffix

    def read(self, validate: bool = True) -> list[dict[str, Any]] | dict[str, Any]:
        """
        Read cache with optional validation.

        Args:
            validate: If True, validate entries with Pydantic model

        Returns:
            List of dicts (for list cache) or dict of dicts (for map cache)
        """
        if not self.path.exists():
            return [] if self.cache_type == "list" else {}

        try:
            data = json.loads(self.path.read_text())
        except Exception as e:
            error(
                f"Failed to read cache {self.path}",
                exception_text=str(e),
                function_name="CacheManager.read",
            )
            return [] if self.cache_type == "list" else {}

        if not validate:
            return data

        # Validate entries
        if self.cache_type == "list":
            return self._validate_list(data)
        else:
            return self._validate_map(data)

    def write(self, data: list[dict[str, Any]] | dict[str, Any]) -> None:
        """Write cache with atomic update."""
        atomic_file_update(self.path, data, self.tmp_suffix)

    def update_item(
        self,
        item_id: str,
        updater: Callable[[dict[str, Any] | None], dict[str, Any] | None],
        key_field: str = "id",
    ) -> dict[str, Any] | None:
        """
        Atomic read-modify-write for single item.

        Args:
            item_id: ID of item to update
            updater: Function that takes current item (or None) and returns updated item
            key_field: Field name to use as key (for list-based caches)

        Returns:
            Updated item or None if deleted
        """
        data = self.read(validate=False)

        if self.cache_type == "map":
            current = data.get(item_id)
            updated = updater(current)
            if updated is None:
                data.pop(item_id, None)
            else:
                # Accept both dict and Pydantic model
                data[item_id] = (
                    updated.model_dump()
                    if isinstance(updated, BaseModel)
                    else updated
                )
        else:
            # List-based cache
            idx = next(
                (
                    i
                    for i, item in enumerate(data)
                    if item.get(key_field) == item_id
                ),
                None,
            )
            current = data[idx] if idx is not None else None
            updated = updater(current)

            if updated is None and idx is not None:
                data.pop(idx)
            elif updated is not None:
                item_dict = (
                    updated.model_dump()
                    if isinstance(updated, BaseModel)
                    else updated
                )
                if idx is not None:
                    data[idx] = item_dict
                else:
                    data.append(item_dict)

        self.write(data)
        return updated

    def filter_items(
        self, predicate: Callable[[dict[str, Any]], bool]
    ) -> int:
        """
        Atomic filter operation - removes items not matching predicate.
        Returns count of removed items.

        Args:
            predicate: Function that returns True for items to keep

        Returns:
            Number of items removed
        """
        data = self.read(validate=False)

        if self.cache_type == "list":
            original_count = len(data)
            filtered = [item for item in data if predicate(item)]
            removed = original_count - len(filtered)
            self.write(filtered)
        else:
            original_count = len(data) - (1 if "_order" in data else 0)
            filtered = {k: v for k, v in data.items() if k == "_order" or predicate(v)}
            removed = original_count - (len(filtered) - (1 if "_order" in filtered else 0))
            self.write(filtered)

        return removed

    def _validate_list(self, data: list) -> list[dict[str, Any]]:
        """Validate list entries with Pydantic model."""
        validated = []
        for item in data:
            try:
                validated_item = self.model_class(**item)
                validated.append(validated_item.model_dump())
            except ValidationError as e:
                error(
                    f"Invalid cache entry: {e}",
                    function_name="CacheManager._validate_list",
                )
                validated.append(item)  # Include invalid but log
        return validated

    def _validate_map(self, data: dict) -> dict[str, Any]:
        """Validate map entries with Pydantic model."""
        validated = {}
        for key, item in data.items():
            if key == "_order":  # Preserve order metadata
                validated[key] = item
                continue
            try:
                validated_item = self.model_class(**item)
                validated[key] = validated_item.model_dump()
            except ValidationError as e:
                error(
                    f"Invalid cache entry for {key}: {e}",
                    function_name="CacheManager._validate_map",
                )
                validated[key] = item
        return validated


class OrderedMapCache(CacheManager[T]):
    """
    Specialized cache for map-based caches with _order array.
    Used by comments_cache and posted_tweets_cache.

    The _order array maintains insertion order with newest items first.
    This supports pagination and chronological display.
    """

    def __init__(
        self,
        path: Path,
        model_class: type[T],
        tmp_suffix: str = ".tmp",
    ):
        super().__init__(
            path=path,
            model_class=model_class,
            cache_type="map",
            tmp_suffix=tmp_suffix,
        )

    def add_item(
        self,
        item_id: str,
        item: T | dict[str, Any],
        position: Literal["start", "end"] = "start",
    ) -> None:
        """
        Add item and update order array.

        Args:
            item_id: Unique ID for the item
            item: Item to add (Pydantic model or dict)
            position: Where to add in order array ("start" for newest-first)
        """
        data = self.read(validate=False)

        # Add to map
        data[item_id] = (
            item.model_dump() if isinstance(item, BaseModel) else item
        )

        # Update order
        order = data.get("_order", [])
        if item_id in order:
            order.remove(item_id)

        if position == "start":
            order.insert(0, item_id)
        else:
            order.append(item_id)

        data["_order"] = order
        self.write(data)

    def delete_item(self, item_id: str) -> bool:
        """
        Delete item and update order.

        Args:
            item_id: ID of item to delete

        Returns:
            True if item was deleted, False if not found
        """
        data = self.read(validate=False)

        if item_id not in data:
            return False

        data.pop(item_id)
        order = data.get("_order", [])
        if item_id in order:
            order.remove(item_id)
        data["_order"] = order

        self.write(data)
        return True

    def get_ordered_items(self, limit: int | None = None, offset: int = 0) -> list[dict[str, Any]]:
        """
        Get items in order (newest first by default).

        Args:
            limit: Maximum number of items to return
            offset: Number of items to skip

        Returns:
            List of items in order
        """
        data = self.read(validate=False)
        order = data.get("_order", [])

        # Apply pagination
        if offset > 0:
            order = order[offset:]
        if limit is not None:
            order = order[:limit]

        # Return items in order
        items = []
        for item_id in order:
            if item_id in data:
                items.append(data[item_id])

        return items
