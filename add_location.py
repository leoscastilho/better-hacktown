#!/usr/bin/env python3
"""
Helper script to add new location mappings to a year's locations_config.json.

Location mappings live per year at config/<year>/locations_config.json. This
script provides an interactive way to add new locations using the format that
supports multiple possible names per location.

Usage:
    python add_location.py                # uses activeYear from config/years.json
    python add_location.py --year 2026    # target a specific year
"""

import argparse
import json
import os
import sys
from typing import Dict, Any

# Path to the config file being edited; set by main() based on --year.
CONFIG_FILE = os.path.join("config", "locations_config.json")

# Year currently being edited; set by main().
CURRENT_YEAR = None

YEARS_CONFIG_FILE = os.path.join("config", "years.json")

def resolve_year(requested_year: str = None) -> str:
    """Resolve the target year: --year if given, else activeYear from the registry."""
    if requested_year:
        return str(requested_year)
    try:
        with open(YEARS_CONFIG_FILE, 'r', encoding='utf-8') as f:
            registry = json.load(f)
        active = registry.get("activeYear")
        if active:
            return str(active)
    except Exception as e:
        print(f"⚠️  Could not read {YEARS_CONFIG_FILE} ({e}).")
    print("❌ No year specified and no activeYear found. Use --year <year>.")
    sys.exit(1)

def load_config() -> Dict[str, Any]:
    """Load the current locations configuration for the selected year."""
    if not os.path.exists(CONFIG_FILE):
        print(f"❌ Configuration file {CONFIG_FILE} not found!")
        print("Please make sure you're running this script from the project root directory,")
        print("and that the year exists under config/.")
        sys.exit(1)

    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Error loading configuration: {e}")
        sys.exit(1)

def save_config(config: Dict[str, Any]) -> None:
    """Save the updated configuration for the selected year."""
    try:
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        print(f"✅ Configuration saved to {CONFIG_FILE}")
    except Exception as e:
        print(f"❌ Error saving configuration: {e}")
        sys.exit(1)

def get_user_input(prompt: str, required: bool = True) -> str:
    """Get user input with validation."""
    while True:
        value = input(prompt).strip()
        if value or not required:
            return value
        print("❌ This field is required. Please enter a value.")

def add_location_interactive() -> None:
    """Interactive function to add a new location."""
    print("🏢 Adding a new location mapping")
    print("=" * 50)
    
    # Get location key (unique identifier)
    location_key = get_user_input("Enter location key (unique identifier, e.g., 'new_venue'): ")
    
    # Check if key already exists
    config = load_config()
    if location_key in config.get('location_mappings', {}):
        print(f"⚠️  Location key '{location_key}' already exists!")
        overwrite = input("Do you want to overwrite it? (y/N): ").lower().strip()
        if overwrite != 'y':
            print("❌ Operation cancelled.")
            return
    
    print(f"\n📍 Configuring location: {location_key}")
    print("-" * 30)
    
    # Get possible names
    print("Enter possible names for this location (one per line).")
    print("These are the variations that might appear in the API.")
    print("Press Enter on an empty line when done:")
    
    possible_names = []
    while True:
        name = input(f"  Possible name {len(possible_names) + 1}: ").strip()
        if not name:
            break
        possible_names.append(name.upper())
    
    if not possible_names:
        print("❌ At least one possible name is required.")
        return
    
    # Get other fields
    filter_location = get_user_input("Enter filter location (display name): ")
    
    print("\nNear location options:")
    print("1. Inatel e Arredores")
    print("2. ETE e Arredores") 
    print("3. Praça e Arredores")
    print("4. Other")
    
    near_choice = get_user_input("Choose near location (1-4) or enter custom: ")
    near_options = {
        "1": "Inatel e Arredores",
        "2": "ETE e Arredores", 
        "3": "Praça e Arredores",
        "4": "Other"
    }
    
    near_location = near_options.get(near_choice, near_choice)
    
    gmaps = get_user_input("Enter Google Maps URL (optional): ", required=False)
    
    # Create the new location entry
    new_location = {
        "possible_names": possible_names,
        "filter_location": filter_location,
        "near_location": near_location,
        "gmaps": gmaps
    }
    
    # Show summary
    print(f"\n📋 Summary for '{location_key}':")
    print(f"  Possible names: {', '.join(possible_names)}")
    print(f"  Filter location: {filter_location}")
    print(f"  Near location: {near_location}")
    print(f"  Google Maps: {gmaps or '(none)'}")
    
    # Confirm
    confirm = input("\nSave this location? (Y/n): ").lower().strip()
    if confirm in ('', 'y', 'yes'):
        # Add to configuration
        if 'location_mappings' not in config:
            config['location_mappings'] = {}
        
        config['location_mappings'][location_key] = new_location
        save_config(config)
        print(f"✅ Location '{location_key}' added successfully!")
        print("\n💡 Don't forget to run the scraper to update the generated files:")
        print(f"   python scrape_hacktown.py --year {CURRENT_YEAR}")
    else:
        print("❌ Operation cancelled.")

def list_locations() -> None:
    """List all existing locations."""
    config = load_config()
    mappings = config.get('location_mappings', {})
    
    if not mappings:
        print("📭 No locations configured.")
        return
    
    print(f"📍 Configured locations ({len(mappings)}):")
    print("=" * 50)
    
    for key, location in mappings.items():
        possible_names = location.get('possible_names', [])
        filter_location = location.get('filter_location', 'N/A')
        near_location = location.get('near_location', 'N/A')
        
        print(f"\n🏢 {key}")
        print(f"   Names: {', '.join(possible_names)}")
        print(f"   Filter: {filter_location}")
        print(f"   Near: {near_location}")

def main():
    """Main function."""
    global CONFIG_FILE, CURRENT_YEAR

    parser = argparse.ArgumentParser(description="Add location mappings for a HackTown year")
    parser.add_argument(
        "--year", dest="year", default=None,
        help="Year to edit (e.g. 2025). Defaults to activeYear in config/years.json."
    )
    args = parser.parse_args()

    CURRENT_YEAR = resolve_year(args.year)
    CONFIG_FILE = os.path.join("config", CURRENT_YEAR, "locations_config.json")

    print("🏢 Location Configuration Helper")
    print("=" * 40)
    print(f"📅 Year: {CURRENT_YEAR}")
    print(f"📄 Config file: {CONFIG_FILE}")

    while True:
        print("\nOptions:")
        print("1. Add new location")
        print("2. List existing locations")
        print("3. Exit")
        
        choice = input("\nChoose an option (1-3): ").strip()
        
        if choice == '1':
            add_location_interactive()
        elif choice == '2':
            list_locations()
        elif choice == '3':
            print("👋 Goodbye!")
            break
        else:
            print("❌ Invalid choice. Please enter 1, 2, or 3.")

if __name__ == "__main__":
    main()
