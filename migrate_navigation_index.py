#!/usr/bin/env python3
"""
Migration script for AURA Smart Navigation Fallback

This script initializes the navigation index database and populates it
from existing roteiros in the roteiros_salvos/ directory.

Usage:
    python migrate_navigation_index.py [--rebuild]

Options:
    --rebuild    Clear existing index and rebuild from scratch
"""

import sys
import os
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def migrate_to_navigation_index(rebuild: bool = False):
    """
    Create navigation index database and populate from existing roteiros.
    
    Args:
        rebuild: If True, clear existing index before rebuilding
    """
    try:
        from navigation_fallback import (
            RoteiroIndexer,
            initialize_database,
            NAVIGATION_FALLBACK_ENABLED,
            ROTEIRO_INDEX_DB
        )
        
        if not NAVIGATION_FALLBACK_ENABLED:
            logger.warning("Navigation fallback is disabled in configuration")
            logger.info("Set NAVIGATION_FALLBACK_ENABLED=True in .env to enable")
            return False
        
        logger.info("Starting navigation index migration...")
        
        # Initialize database
        logger.info(f"Initializing database: {ROTEIRO_INDEX_DB}")
        initialize_database(ROTEIRO_INDEX_DB)
        
        # Create indexer
        indexer = RoteiroIndexer()
        
        # Clear index if rebuild requested
        if rebuild:
            logger.info("Clearing existing index...")
            indexer.clear_index()
        
        # Check if roteiros directory exists
        roteiros_dir = Path("roteiros_salvos")
        if not roteiros_dir.exists():
            logger.error(f"Roteiros directory not found: {roteiros_dir}")
            return False
        
        # Count roteiros
        roteiro_files = list(roteiros_dir.glob("*.json"))
        logger.info(f"Found {len(roteiro_files)} roteiro files")
        
        if len(roteiro_files) == 0:
            logger.warning("No roteiro files found - index will be empty")
            return True
        
        # Build index
        logger.info("Building navigation index...")
        result = indexer.build_index()
        
        if result["status"] == "success":
            logger.info(f"✓ Migration successful!")
            logger.info(f"  - Indexed: {result['indexed_count']} roteiros")
            logger.info(f"  - Failed: {result['failed_count']} roteiros")
            logger.info(f"  - Duration: {result['duration_ms']:.2f}ms")
            logger.info(f"  - Index size: {indexer.get_index_size()} entries")
            return True
        else:
            logger.error(f"✗ Migration failed: {result.get('message', 'Unknown error')}")
            return False
        
    except ImportError as e:
        logger.error(f"Failed to import navigation_fallback module: {e}")
        logger.info("Make sure navigation_fallback.py is in the same directory")
        return False
    except Exception as e:
        logger.error(f"Migration failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main entry point for migration script."""
    rebuild = "--rebuild" in sys.argv
    
    if rebuild:
        logger.info("Rebuild mode: existing index will be cleared")
    
    success = migrate_to_navigation_index(rebuild=rebuild)
    
    if success:
        logger.info("Migration completed successfully")
        sys.exit(0)
    else:
        logger.error("Migration failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
