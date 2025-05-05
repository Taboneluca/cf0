#!/usr/bin/env python
"""
Migration script to move in-memory workbooks to Supabase.

Usage:
  python migrate_inmem_to_supabase.py

Environment variables:
  SUPABASE_URL - Supabase URL
  SUPABASE_KEY - Supabase API key
"""

import os
import sys
import asyncio
import json
from dotenv import load_dotenv

# Add parent directory to path so we can import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Load environment variables
load_dotenv()

# Import workbook store and Supabase client
from workbook_store import workbooks
from supabase_store import sb, start_background_worker, _save_sheet

async def migrate_workbooks():
    """Migrate all in-memory workbooks to Supabase"""
    if not sb:
        print("Error: Supabase client not initialized. Make sure SUPABASE_URL and SUPABASE_KEY are set.")
        return

    # Check if Supabase tables exist
    try:
        # Create workbooks table if it doesn't exist
        sb.table("spreadsheet_workbooks").select("*").limit(1).execute()
        print("✓ Connected to spreadsheet_workbooks table")
    except Exception as e:
        print(f"Error connecting to spreadsheet_workbooks table: {str(e)}")
        print("Make sure to run the schema migrations first!")
        return

    # Initialize the background worker
    await start_background_worker()

    # Count of processed items
    workbook_count = 0
    sheet_count = 0

    # Process all workbooks
    for wid, workbook in workbooks.items():
        print(f"Migrating workbook {wid}...")
        
        # Create workbook in Supabase
        try:
            sb.table("spreadsheet_workbooks").upsert({"wid": wid}).execute()
            workbook_count += 1
        except Exception as e:
            print(f"Error creating workbook {wid}: {str(e)}")
            continue

        # Process sheets
        for sheet_name, sheet in workbook.sheets.items():
            try:
                # Save sheet data
                print(f"  - Migrating sheet {sheet_name}...")
                await _save_sheet(wid, sheet)
                sheet_count += 1
            except Exception as e:
                print(f"  - Error saving sheet {sheet_name}: {str(e)}")

    print(f"\nMigration complete: {workbook_count} workbooks and {sheet_count} sheets processed.")

if __name__ == "__main__":
    if not os.environ.get("SUPABASE_URL") or not os.environ.get("SUPABASE_KEY"):
        print("Error: SUPABASE_URL and SUPABASE_KEY environment variables must be set.")
        sys.exit(1)

    print("Starting migration from in-memory storage to Supabase...")
    asyncio.run(migrate_workbooks()) 