#!/usr/bin/env python3
"""
Script to repair and validate user_info.json entries.

This script:
1. Reads all user entries from user_info.json
2. Validates each entry against the User model from data_validation.py
3. For invalid entries, prompts the user to enter correct values
4. Saves the repaired data back to user_info.json
"""

import json
import sys
from pathlib import Path
from typing import Any

from pydantic import ValidationError

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from backend.config import USER_INFO_FILE
from backend.data_validation import User
from backend.utils import atomic_file_update, load_user_info_entries


def get_user_input(field_name: str, field_type: str, current_value: Any = None, required: bool = True) -> Any:
    """
    Prompt user for input with type validation.

    Args:
        field_name: Name of the field to prompt for
        field_type: Type of the field (for display)
        current_value: Current value if any
        required: Whether the field is required

    Returns:
        The user's input, converted to appropriate type
    """
    prompt = f"Enter value for '{field_name}' ({field_type})"
    if current_value is not None:
        prompt += f" [current: {current_value}]"
    if not required:
        prompt += " [optional, press Enter to skip]"
    prompt += ": "

    while True:
        user_input = input(prompt).strip()

        # Handle empty input for optional fields
        if not user_input and not required:
            return None

        # Require input for required fields
        if not user_input and required:
            print("❌ This field is required. Please enter a value.")
            continue

        # Type conversion
        try:
            if "int" in field_type.lower():
                return int(user_input)
            elif "bool" in field_type.lower():
                return user_input.lower() in ('true', 'yes', '1', 'y')
            elif "list" in field_type.lower():
                if not user_input:
                    return []
                # Try to parse as JSON array
                try:
                    parsed = json.loads(user_input)
                    if isinstance(parsed, list):
                        return parsed
                except:
                    # Fall back to comma-separated
                    return [item.strip() for item in user_input.split(',') if item.strip()]
            elif "dict" in field_type.lower():
                if not user_input:
                    return {}
                # Parse as JSON dict
                return json.loads(user_input)
            else:
                # String type
                return user_input
        except (ValueError, json.JSONDecodeError) as e:
            print(f"❌ Invalid input format: {e}. Please try again.")
            continue


def repair_user_entry(entry: dict[str, Any], index: int) -> dict[str, Any] | None:
    """
    Validate and repair a single user entry.

    Args:
        entry: User data dictionary
        index: Index of the user in the list (for display)

    Returns:
        Repaired entry dict, or None to skip
    """
    handle = entry.get('handle', f'User #{index + 1}')

    print(f"\n{'=' * 60}")
    print(f"Checking user: {handle}")
    print(f"{'=' * 60}")

    try:
        # Try to validate the entry
        user = User(**entry)
        print(f"✅ User '{handle}' is valid")
        return entry
    except ValidationError as e:
        print(f"❌ User '{handle}' has validation errors:")

        # Parse validation errors
        errors = e.errors()
        for error in errors:
            field = error['loc'][0] if error['loc'] else 'unknown'
            error_type = error['type']
            msg = error['msg']
            print(f"  - {field}: {msg} (type: {error_type})")

        print(f"\nCurrent data: {json.dumps(entry, indent=2)}")

        # Ask if user wants to repair this entry
        should_repair = input("\nRepair this user? (y/n/skip): ").strip().lower()

        if should_repair == 'skip' or should_repair == 's':
            print(f"⏭️  Skipping user '{handle}'")
            return entry  # Return as-is

        if should_repair != 'y' and should_repair != 'yes':
            print(f"⏭️  Skipping user '{handle}'")
            return entry  # Return as-is

        # Repair each missing/invalid field
        repaired_entry = entry.copy()

        for error in errors:
            field = error['loc'][0] if error['loc'] else None
            if not field:
                continue

            error_type = error['type']
            current_value = entry.get(field)

            print(f"\n--- Repairing field: {field} ---")

            # Determine field type from User model
            field_info = User.model_fields.get(field)
            if not field_info:
                print(f"⚠️  Unknown field '{field}', skipping")
                continue

            field_type_str = str(field_info.annotation)
            is_required = field_info.is_required()

            # Get user input
            new_value = get_user_input(field, field_type_str, current_value, is_required)

            if new_value is not None or not is_required:
                repaired_entry[field] = new_value
                print(f"✅ Updated '{field}' = {new_value}")

        # Validate repaired entry
        try:
            user = User(**repaired_entry)
            print(f"\n✅ User '{handle}' successfully repaired and validated!")
            return repaired_entry
        except ValidationError as e:
            print("\n❌ Repaired entry still has errors:")
            for error in e.errors():
                field = error['loc'][0] if error['loc'] else 'unknown'
                print(f"  - {field}: {error['msg']}")

            retry = input("Retry repair? (y/n): ").strip().lower()
            if retry == 'y' or retry == 'yes':
                return repair_user_entry(repaired_entry, index)
            else:
                print(f"⚠️  Keeping user '{handle}' with errors")
                return repaired_entry


def main():
    """Main function to repair user data."""
    print("=" * 60)
    print("USER DATA REPAIR TOOL")
    print("=" * 60)
    print(f"Reading from: {USER_INFO_FILE}")
    print()

    if not USER_INFO_FILE.exists():
        print(f"❌ File not found: {USER_INFO_FILE}")
        return 1

    # Load entries
    entries = load_user_info_entries()

    if not entries:
        print("❌ No user entries found")
        return 1

    print(f"Found {len(entries)} user entries\n")

    # Track changes
    repaired_entries = []
    changes_made = False

    # Process each entry
    for idx, entry in enumerate(entries):
        repaired = repair_user_entry(entry, idx)

        if repaired is not None:
            repaired_entries.append(repaired)
            if repaired != entry:
                changes_made = True
        else:
            # User chose to skip entirely
            repaired_entries.append(entry)

    # Save if changes were made
    if changes_made:
        print("\n" + "=" * 60)
        print("SAVING CHANGES")
        print("=" * 60)

        confirm = input(f"Save {len(repaired_entries)} entries to {USER_INFO_FILE}? (y/n): ").strip().lower()

        if confirm == 'y' or confirm == 'yes':
            try:
                atomic_file_update(USER_INFO_FILE, repaired_entries, ".tmp", ensure_ascii=False)
                print(f"✅ Successfully saved repaired data to {USER_INFO_FILE}")
                return 0
            except Exception as e:
                print(f"❌ Error saving file: {e}")
                return 1
        else:
            print("❌ Changes not saved")
            return 1
    else:
        print("\n" + "=" * 60)
        print("✅ All user entries are valid! No changes needed.")
        print("=" * 60)
        return 0


if __name__ == "__main__":
    sys.exit(main())
