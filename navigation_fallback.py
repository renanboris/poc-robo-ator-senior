"""
AURA Smart Navigation Fallback Module

This module implements a hierarchical fallback strategy for AURA to guide users
to UI elements that are not currently visible in the DOM. It leverages saved roteiros
to extract navigation paths and provide step-by-step guided navigation.

Architecture:
- NavigationFallbackEngine: Main orchestrator
- RoteiroIndexer: Fast O(log n) lookup with SQLite FTS5 and LRU cache
- NavigationPathExtractor: Parses roteiro JSON files
- GuidedNavigationExecutor: Step-by-step navigation execution

Performance Targets:
- Element visibility check: < 500ms
- Index lookup: < 200ms for 95% of queries
- Navigation step timeout: 2 seconds
"""

import asyncio
import json
import logging
import os
import sqlite3
import time
from collections import OrderedDict
from pathlib import Path
from typing import Dict, List, Optional

from unidecode import unidecode

# Configure logging
logger = logging.getLogger(__name__)

try:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    logger.warning("watchdog not installed - file watching disabled")

# Configuration constants
ROTEIRO_INDEX_DB = os.getenv("ROTEIRO_INDEX_DB", "roteiro_index.db")
ROTEIRO_INDEX_CACHE_SIZE = int(os.getenv("ROTEIRO_INDEX_CACHE_SIZE", "100"))
NAVIGATION_STEP_TIMEOUT_MS = int(os.getenv("NAVIGATION_STEP_TIMEOUT_MS", "2000"))
ELEMENT_VISIBILITY_CHECK_TIMEOUT_MS = int(os.getenv("ELEMENT_VISIBILITY_CHECK_TIMEOUT_MS", "500"))
NAVIGATION_FALLBACK_ENABLED = os.getenv("NAVIGATION_FALLBACK_ENABLED", "True").lower() == "true"

# SQLite schema for navigation index
NAVIGATION_INDEX_SCHEMA = """
CREATE TABLE IF NOT EXISTS navigation_index (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    roteiro_name TEXT NOT NULL,
    target_element TEXT NOT NULL,
    navigation_path TEXT NOT NULL,
    breadcrumb TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    path_length INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_target_element ON navigation_index(target_element);
CREATE INDEX IF NOT EXISTS idx_tenant_id ON navigation_index(tenant_id);
CREATE INDEX IF NOT EXISTS idx_breadcrumb ON navigation_index(breadcrumb);

-- Enable FTS5 for full-text search
CREATE VIRTUAL TABLE IF NOT EXISTS navigation_index_fts USING fts5(
    roteiro_name,
    target_element,
    breadcrumb,
    content='navigation_index',
    content_rowid='id'
);

-- Triggers to keep FTS index in sync
CREATE TRIGGER IF NOT EXISTS navigation_index_ai AFTER INSERT ON navigation_index BEGIN
    INSERT INTO navigation_index_fts(rowid, roteiro_name, target_element, breadcrumb)
    VALUES (new.id, new.roteiro_name, new.target_element, new.breadcrumb);
END;

CREATE TRIGGER IF NOT EXISTS navigation_index_ad AFTER DELETE ON navigation_index BEGIN
    INSERT INTO navigation_index_fts(navigation_index_fts, rowid, roteiro_name, target_element, breadcrumb)
    VALUES('delete', old.id, old.roteiro_name, old.target_element, old.breadcrumb);
END;

CREATE TRIGGER IF NOT EXISTS navigation_index_au AFTER UPDATE ON navigation_index BEGIN
    INSERT INTO navigation_index_fts(navigation_index_fts, rowid, roteiro_name, target_element, breadcrumb)
    VALUES('delete', old.id, old.roteiro_name, old.target_element, old.breadcrumb);
    INSERT INTO navigation_index_fts(rowid, roteiro_name, target_element, breadcrumb)
    VALUES (new.id, new.roteiro_name, new.target_element, new.breadcrumb);
END;
"""

# Stop words for query normalization (Portuguese)
STOP_WORDS = {
    'o', 'a', 'os', 'as', 'um', 'uma', 'uns', 'umas',
    'de', 'do', 'da', 'dos', 'das', 'em', 'no', 'na', 'nos', 'nas',
    'por', 'para', 'com', 'sem', 'sob', 'sobre',
    'e', 'ou', 'mas', 'que', 'se', 'como'
}


def initialize_database(db_path: str = ROTEIRO_INDEX_DB) -> None:
    """
    Initialize the navigation index database with schema.
    
    Args:
        db_path: Path to the SQLite database file
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Execute schema creation
        cursor.executescript(NAVIGATION_INDEX_SCHEMA)

        conn.commit()
        conn.close()

        logger.info(f"Navigation index database initialized at {db_path}")
    except Exception as e:
        logger.error(f"Failed to initialize navigation index database: {e}")
        raise


# Initialize database on module import
if NAVIGATION_FALLBACK_ENABLED:
    initialize_database()


class LRUCache:
    """
    Simple LRU (Least Recently Used) cache implementation.
    """
    def __init__(self, capacity: int):
        self.cache = OrderedDict()
        self.capacity = capacity

    def get(self, key: str) -> Optional[Dict]:
        """Get value from cache, moving it to end (most recently used)."""
        if key not in self.cache:
            return None
        self.cache.move_to_end(key)
        return self.cache[key]

    def put(self, key: str, value: Dict) -> None:
        """Put value in cache, evicting least recently used if at capacity."""
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = value
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)

    def invalidate(self, key: str = None) -> None:
        """Invalidate specific key or entire cache."""
        if key is None:
            self.cache.clear()
        elif key in self.cache:
            del self.cache[key]

    def size(self) -> int:
        """Get current cache size."""
        return len(self.cache)


class RoteiroIndexer:
    """
    Indexes roteiro navigation paths for fast O(log n) lookup.
    
    Features:
    - SQLite backend with FTS5 full-text search
    - LRU cache for frequently accessed paths
    - Incremental index updates
    - Query normalization for better cache hits
    
    Performance targets:
    - Index build: < 5 seconds for 1000 roteiros
    - Lookup: < 200ms for 95% of queries
    - Cache hit rate: > 80% for frequent queries
    """

    def __init__(self, roteiros_dir: str = "roteiros_salvos", index_db: str = ROTEIRO_INDEX_DB):
        """
        Initialize the RoteiroIndexer.
        
        Args:
            roteiros_dir: Directory containing roteiro JSON files
            index_db: Path to SQLite index database
        """
        self.roteiros_dir = roteiros_dir
        self.index_db = index_db
        self.cache = LRUCache(ROTEIRO_INDEX_CACHE_SIZE)

        # Ensure database exists
        if not os.path.exists(index_db):
            initialize_database(index_db)

        logger.info(f"RoteiroIndexer initialized with cache size {ROTEIRO_INDEX_CACHE_SIZE}")

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(self.index_db)
        conn.row_factory = sqlite3.Row
        return conn

    def _normalize_query(self, query: str) -> str:
        """
        Normalize query for consistent cache keys.
        
        Steps:
        1. Convert to lowercase
        2. Remove accents
        3. Remove stop words (but keep at least one word)
        4. Sort words alphabetically
        
        Args:
            query: Raw search query
            
        Returns:
            Normalized query string
        """
        # Convert to lowercase
        query = query.lower()

        # Remove accents
        query = unidecode(query)

        # Remove punctuation
        import re
        query = re.sub(r'[^\w\s]', ' ', query)

        # Split into words
        all_words = query.split()

        # Remove stop words but keep at least one word
        words = [word for word in all_words if word not in STOP_WORDS]

        # If all words were stop words, keep the original words
        if not words:
            words = all_words

        # Sort alphabetically for consistent cache keys
        words.sort()

        return ' '.join(words)

    def get_index_size(self) -> int:
        """
        Get the number of entries in the index.
        
        Returns:
            Number of indexed navigation paths
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM navigation_index")
            count = cursor.fetchone()[0]
            conn.close()
            return count
        except Exception as e:
            logger.error(f"Failed to get index size: {e}")
            return 0

    def clear_index(self) -> None:
        """Clear all entries from the index."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM navigation_index")
            conn.commit()
            conn.close()
            self.cache.invalidate()
            logger.info("Navigation index cleared")
        except Exception as e:
            logger.error(f"Failed to clear index: {e}")
            raise

    def build_index(self, tenant_id: str = "senior_default") -> Dict:
        """
        Build or rebuild the complete roteiro index.
        Scans all roteiro files and extracts navigation paths.
        
        Args:
            tenant_id: Tenant identifier for multi-tenancy support
            
        Returns:
            dict: {
                "status": "success" | "error",
                "indexed_count": int,
                "failed_count": int,
                "duration_ms": float
            }
        """
        start_time = time.time()
        indexed_count = 0
        failed_count = 0

        try:
            # Clear existing index
            self.clear_index()

            # Get all roteiro JSON files
            roteiros_path = Path(self.roteiros_dir)
            if not roteiros_path.exists():
                logger.warning(f"Roteiros directory not found: {self.roteiros_dir}")
                return {
                    "status": "error",
                    "message": f"Directory not found: {self.roteiros_dir}",
                    "indexed_count": 0,
                    "failed_count": 0,
                    "duration_ms": 0
                }

            roteiro_files = list(roteiros_path.glob("*.json"))
            logger.info(f"Building index from {len(roteiro_files)} roteiro files...")

            conn = self._get_connection()
            cursor = conn.cursor()

            # Use NavigationPathExtractor to parse roteiros
            extractor = NavigationPathExtractor()

            for roteiro_file in roteiro_files:
                try:
                    with open(roteiro_file, 'r', encoding='utf-8') as f:
                        roteiro_data = json.load(f)

                    # Extract navigation path
                    nav_path = extractor.extract_navigation_path(roteiro_data)

                    if nav_path and nav_path.get("steps"):
                        # Insert into database
                        cursor.execute("""
                            INSERT INTO navigation_index 
                            (roteiro_name, target_element, navigation_path, breadcrumb, tenant_id, path_length)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (
                            roteiro_file.stem,
                            nav_path.get("target_element", ""),
                            json.dumps(nav_path.get("steps", []), ensure_ascii=False),
                            nav_path.get("breadcrumb", ""),
                            tenant_id,
                            len(nav_path.get("steps", []))
                        ))
                        indexed_count += 1

                except Exception as e:
                    logger.error(f"Failed to index {roteiro_file.name}: {e}")
                    failed_count += 1

            conn.commit()
            conn.close()

            duration_ms = (time.time() - start_time) * 1000
            logger.info(f"Index build complete: {indexed_count} indexed, {failed_count} failed in {duration_ms:.2f}ms")

            return {
                "status": "success",
                "indexed_count": indexed_count,
                "failed_count": failed_count,
                "duration_ms": duration_ms
            }

        except Exception as e:
            logger.error(f"Failed to build index: {e}")
            return {
                "status": "error",
                "message": str(e),
                "indexed_count": indexed_count,
                "failed_count": failed_count,
                "duration_ms": (time.time() - start_time) * 1000
            }

    def search(self, query: str, tenant_id: str = "senior_default", top_k: int = 5) -> List[Dict]:
        """
        Search for navigation paths matching the query.
        
        Args:
            query: Search query
            tenant_id: Tenant identifier
            top_k: Maximum number of results to return
            
        Returns:
            list[dict]: [
                {
                    "roteiro_name": str,
                    "navigation_path": list[dict],
                    "breadcrumb": str,
                    "confidence_score": float,
                    "path_length": int
                }
            ]
        """
        # Normalize query for cache lookup
        normalized_query = self._normalize_query(query)
        cache_key = f"{tenant_id}_{normalized_query}"

        # Check cache first
        cached_result = self.cache.get(cache_key)
        if cached_result:
            logger.debug(f"Cache hit for query: {query}")
            return cached_result

        # If normalized query is empty, return empty results
        if not normalized_query or normalized_query.strip() == "":
            logger.warning(f"Normalized query is empty for: {query}")
            return []

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Prepare FTS5 query - escape special characters and use OR for multiple words
            fts_query = ' OR '.join(normalized_query.split())

            # Use FTS5 for full-text search with ranking
            cursor.execute("""
                SELECT 
                    ni.roteiro_name,
                    ni.navigation_path,
                    ni.breadcrumb,
                    ni.path_length,
                    fts.rank as score
                FROM navigation_index ni
                JOIN navigation_index_fts fts ON ni.id = fts.rowid
                WHERE navigation_index_fts MATCH ? AND ni.tenant_id = ?
                ORDER BY fts.rank, ni.path_length ASC
                LIMIT ?
            """, (fts_query, tenant_id, top_k))

            results = []
            for row in cursor.fetchall():
                # Calculate confidence score from FTS rank (higher rank = better match)
                # FTS5 rank is negative, so we invert and normalize
                confidence_score = min(1.0, abs(row['score']) / 10.0)

                results.append({
                    "roteiro_name": row['roteiro_name'],
                    "navigation_path": json.loads(row['navigation_path']),
                    "breadcrumb": row['breadcrumb'],
                    "confidence_score": confidence_score,
                    "path_length": row['path_length']
                })

            conn.close()

            # Cache the results
            self.cache.put(cache_key, results)

            logger.debug(f"Search for '{query}' returned {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"Search failed for query '{query}': {e}")
            return []

    def update_index(self, roteiro_file: str, tenant_id: str = "senior_default") -> bool:
        """
        Update index for a specific roteiro file.
        Called when roteiros are modified.
        
        Args:
            roteiro_file: Path to the roteiro JSON file
            tenant_id: Tenant identifier
            
        Returns:
            bool: True if update successful, False otherwise
        """
        try:
            roteiro_path = Path(roteiro_file)
            if not roteiro_path.exists():
                logger.warning(f"Roteiro file not found: {roteiro_file}")
                return False

            # Load roteiro data
            with open(roteiro_path, 'r', encoding='utf-8') as f:
                roteiro_data = json.load(f)

            # Extract navigation path
            extractor = NavigationPathExtractor()
            nav_path = extractor.extract_navigation_path(roteiro_data)

            if not nav_path or not nav_path.get("steps"):
                logger.warning(f"No navigation path found in {roteiro_file}")
                return False

            conn = self._get_connection()
            cursor = conn.cursor()

            # Delete existing entry
            cursor.execute("""
                DELETE FROM navigation_index 
                WHERE roteiro_name = ? AND tenant_id = ?
            """, (roteiro_path.stem, tenant_id))

            # Insert updated entry
            cursor.execute("""
                INSERT INTO navigation_index 
                (roteiro_name, target_element, navigation_path, breadcrumb, tenant_id, path_length, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                roteiro_path.stem,
                nav_path.get("target_element", ""),
                json.dumps(nav_path.get("steps", []), ensure_ascii=False),
                nav_path.get("breadcrumb", ""),
                tenant_id,
                len(nav_path.get("steps", []))
            ))

            conn.commit()
            conn.close()

            # Invalidate cache entries that might be affected
            self.cache.invalidate()

            logger.info(f"Index updated for {roteiro_path.name}")
            return True

        except Exception as e:
            logger.error(f"Failed to update index for {roteiro_file}: {e}")
            return False

    def watch_roteiros_directory(self) -> Optional[Observer]:
        """
        Watch roteiros_salvos/ directory for file changes using watchdog.
        Triggers incremental index updates on file modifications.
        
        Returns:
            Observer instance or None if watchdog not available
        """
        if not WATCHDOG_AVAILABLE:
            logger.warning("watchdog not available - file watching disabled")
            return None

        try:
            class RoteiroChangeHandler(FileSystemEventHandler):
                def __init__(self, indexer):
                    self.indexer = indexer
                    super().__init__()

                def on_modified(self, event):
                    if event.is_directory:
                        return

                    if event.src_path.endswith('.json'):
                        logger.info(f"Roteiro modified: {event.src_path}")
                        self.indexer.update_index(event.src_path)

                def on_created(self, event):
                    if event.is_directory:
                        return

                    if event.src_path.endswith('.json'):
                        logger.info(f"Roteiro created: {event.src_path}")
                        self.indexer.update_index(event.src_path)

                def on_deleted(self, event):
                    if event.is_directory:
                        return

                    if event.src_path.endswith('.json'):
                        logger.info(f"Roteiro deleted: {event.src_path}")
                        # Remove from index
                        roteiro_name = Path(event.src_path).stem
                        try:
                            conn = self.indexer._get_connection()
                            cursor = conn.cursor()
                            cursor.execute("""
                                DELETE FROM navigation_index 
                                WHERE roteiro_name = ?
                            """, (roteiro_name,))
                            conn.commit()
                            conn.close()
                            self.indexer.cache.invalidate()
                            logger.info(f"Removed {roteiro_name} from index")
                        except Exception as e:
                            logger.error(f"Failed to remove {roteiro_name} from index: {e}")

            observer = Observer()
            event_handler = RoteiroChangeHandler(self)
            observer.schedule(event_handler, self.roteiros_dir, recursive=False)
            observer.start()

            logger.info(f"Started watching {self.roteiros_dir} for changes")
            return observer

        except Exception as e:
            logger.error(f"Failed to start file watcher: {e}")
            return None



class NavigationPathExtractor:
    """
    Parses roteiro JSON files to extract hierarchical navigation sequences.
    
    Extracts:
    - Navigation steps from passos array
    - Breadcrumb paths (e.g., "Senior Flow > SIGN > Nova Gestão")
    - Selector hints and element descriptions
    - Target element identification
    """

    def extract_navigation_path(self, roteiro_data: Dict, target_query: Optional[str] = None) -> Optional[Dict]:
        """
        Extract navigation path from roteiro JSON.
        
        Args:
            roteiro_data: Parsed roteiro JSON
            target_query: Optional query to limit extraction to specific target element
        
        Returns:
            dict: {
                "breadcrumb": str,  # "Senior Flow > SIGN > Nova Gestão"
                "steps": list[dict],  # Navigation steps
                "target_element": str  # Final destination
            } or None if no navigation path found
        """
        try:
            passos = roteiro_data.get("passos", [])
            if not passos:
                return None

            steps = []
            breadcrumb_parts = []
            target_found = False

            # Normalize target query for matching
            normalized_target = None
            if target_query:
                # Extract keywords from query (remove question words and patterns)
                query_lower = target_query.lower()

                # Remove common question patterns (more aggressive)
                patterns_to_remove = [
                    'o que é', 'o que e', 'como acessar', 'como chegar', 'como ir',
                    'onde fica', 'onde está', 'onde esta', 'me leve', 'me guie',
                    'me mostre', 'quero ir', 'preciso ir', 'ir para', 'acessar',
                    'navegar', 'encontrar', 'localizar', 'chegar em', 'chegar no',
                    'como faço para', 'como fazer para', 'caminho para',
                    'o ', 'a ', 'os ', 'as ', 'um ', 'uma ', '?', '!'
                ]

                query_clean = query_lower
                for pattern in patterns_to_remove:
                    query_clean = query_clean.replace(pattern, ' ')

                # Normalize and clean
                normalized_target = unidecode(query_clean).strip()
                # Remove extra spaces and punctuation
                normalized_target = ' '.join(normalized_target.split())
                # Remove remaining punctuation
                import re
                normalized_target = re.sub(r'[^\w\s]', '', normalized_target).strip()

                logger.info(f"Target query: '{target_query}' -> normalized: '{normalized_target}'")

            for passo in passos:
                step = self._parse_step(passo)
                if step:
                    steps.append(step)

                    # Build breadcrumb from tooltips
                    tooltip = step.get("tooltip", "")
                    if tooltip and " > " in tooltip:
                        # Extract last part of breadcrumb for this step
                        parts = tooltip.split(" > ")
                        if parts[-1] not in breadcrumb_parts:
                            breadcrumb_parts.append(parts[-1])
                    elif step.get("element", {}).get("label"):
                        label = step["element"]["label"]
                        if label not in breadcrumb_parts:
                            breadcrumb_parts.append(label)

                    # Check if this step matches the target query
                    if normalized_target and normalized_target.strip():
                        step_label = step.get("element", {}).get("label", "")
                        normalized_label = unidecode(step_label.lower()).strip()

                        # Split target into words for flexible matching
                        target_words = normalized_target.split()

                        logger.debug(f"Checking step {len(steps)}: label='{step_label}' (normalized='{normalized_label}') against target words={target_words}")

                        # Check if any target word matches the label
                        match_found = False
                        for word in target_words:
                            if len(word) >= 3:  # Only match words with 3+ characters
                                if word in normalized_label or normalized_label in word:
                                    match_found = True
                                    logger.debug(f"  -> Match found! word='{word}' in label='{normalized_label}'")
                                    break

                        if match_found:
                            target_found = True
                            logger.info(f"Target element '{step_label}' found at step {len(steps)}, stopping extraction")
                            break

            if not steps:
                return None

            # Build breadcrumb
            breadcrumb = self._build_breadcrumb(steps)

            # Target element is the last step's label
            target_element = steps[-1].get("element", {}).get("label", "")

            return {
                "breadcrumb": breadcrumb,
                "steps": steps,
                "target_element": target_element
            }

        except Exception as e:
            logger.error(f"Failed to extract navigation path: {e}")
            return None

    def _parse_step(self, passo: Dict) -> Optional[Dict]:
        """
        Parse a single passo to extract navigation information.
        
        Returns:
            dict | None: {
                "step_id": int,
                "action": str,  # "clique", "hover", etc.
                "element": {
                    "label": str,
                    "selector_hint": str,
                    "description": str,
                    "coordinates": dict
                },
                "tooltip": str,
                "wait_for_dom": bool,
                "timeout_ms": int
            }
        """
        try:
            # Only extract navigation-relevant steps (tipo_passo == "navigation" or has clique action)
            tipo_passo = passo.get("tipo_passo", "")
            acoes = passo.get("acoes_tecnicas", [])

            if not acoes:
                return None

            # Get first action (usually the main navigation action)
            acao = acoes[0]
            acao_tipo = acao.get("acao", "")

            # Only include navigation actions (clique, hover)
            if acao_tipo not in ["clique", "hover"]:
                return None

            # Extract element information
            elemento_alvo = acao.get("elemento_alvo", {})
            label = elemento_alvo.get("label_curto", "") or elemento_alvo.get("descricao_visual", "")

            if not label:
                return None

            # Extract selector hint
            selector_hint = (
                acao.get("seletor_css", "") or
                elemento_alvo.get("seletor_hint", "") or
                elemento_alvo.get("html_hint", "")
            )

            # Extract coordinates
            coords = elemento_alvo.get("coordenadas_relativas", {})

            # Extract tooltip from pedagogia
            tooltip = passo.get("pedagogia", {}).get("tooltip_dap", "")

            return {
                "step_id": passo.get("id_passo"),
                "action": acao_tipo,
                "element": {
                    "label": label,
                    "selector_hint": selector_hint,
                    "description": elemento_alvo.get("contexto_tela", ""),
                    "coordinates": coords
                },
                "tooltip": tooltip,
                "wait_for_dom": True,  # Always wait for DOM changes after navigation
                "timeout_ms": NAVIGATION_STEP_TIMEOUT_MS
            }

        except Exception as e:
            logger.error(f"Failed to parse step: {e}")
            return None

    def _build_breadcrumb(self, steps: List[Dict]) -> str:
        """
        Build human-readable breadcrumb from navigation steps.
        Example: "Senior Flow > SIGN > Nova Gestão"
        
        Args:
            steps: List of navigation steps
            
        Returns:
            str: Breadcrumb path
        """
        breadcrumb_parts = []

        for step in steps:
            # Try to extract from tooltip first (most reliable)
            tooltip = step.get("tooltip", "")
            if tooltip and " > " in tooltip:
                # Use the full tooltip as it contains the hierarchical path
                return tooltip

            # Fallback to element label
            label = step.get("element", {}).get("label", "")
            if label and label not in breadcrumb_parts:
                breadcrumb_parts.append(label)

        return " > ".join(breadcrumb_parts)


class GuidedNavigationExecutor:
    """
    Executes step-by-step guided navigation with visual highlights.
    
    Features:
    - Step-by-step execution with DOM stabilization waiting
    - Visual element highlighting via extension
    - Error detection and recovery
    - Partial progress tracking
    """

    def __init__(self):
        """Initialize the GuidedNavigationExecutor."""
        self.current_step = 0
        self.navigation_state = "idle"  # "idle" | "executing" | "waiting" | "completed" | "failed"
        self.completed_steps = []

    async def execute_navigation(
        self,
        navigation_path: List[Dict],
        dom_context: str
    ) -> Dict:
        """
        Execute the complete navigation sequence.
        
        Args:
            navigation_path: List of navigation steps
            dom_context: Current DOM context
            
        Returns:
            dict: {
                "success": bool,
                "completed_steps": int,
                "failed_step": int | None,
                "error_message": str | None,
                "partial_path": list[str]
            }
        """
        self.navigation_state = "executing"
        self.current_step = 0
        self.completed_steps = []

        try:
            for i, step in enumerate(navigation_path):
                self.current_step = i + 1

                # Execute step
                result = await self.execute_step(step, dom_context)

                if not result["success"]:
                    self.navigation_state = "failed"
                    return {
                        "success": False,
                        "completed_steps": len(self.completed_steps),
                        "failed_step": self.current_step,
                        "error_message": result.get("error", "Unknown error"),
                        "partial_path": self.completed_steps
                    }

                # Track completed step
                step_label = step.get("element", {}).get("label", f"Step {self.current_step}")
                self.completed_steps.append(step_label)

                # Wait for DOM stabilization if needed
                if step.get("wait_for_dom", True):
                    self.navigation_state = "waiting"
                    await self._wait_for_dom_stabilization(step.get("timeout_ms", NAVIGATION_STEP_TIMEOUT_MS))

            self.navigation_state = "completed"
            return {
                "success": True,
                "completed_steps": len(self.completed_steps),
                "failed_step": None,
                "error_message": None,
                "partial_path": self.completed_steps
            }

        except Exception as e:
            logger.error(f"Navigation execution failed: {e}")
            self.navigation_state = "failed"
            return {
                "success": False,
                "completed_steps": len(self.completed_steps),
                "failed_step": self.current_step,
                "error_message": str(e),
                "partial_path": self.completed_steps
            }

    async def execute_step(
        self,
        step: Dict,
        dom_context: str
    ) -> Dict:
        """
        Execute a single navigation step.
        
        Args:
            step: Navigation step data
            dom_context: Current DOM context
            
        Returns:
            dict: {
                "success": bool,
                "element_found": bool,
                "dom_changed": bool,
                "error": str | None
            }
        """
        try:
            element = step.get("element", {})
            label = element.get("label", "")
            selector_hint = element.get("selector_hint", "")

            # Check if element exists in DOM
            element_found = False
            if selector_hint:
                # Simple check if selector hint appears in DOM context
                element_found = selector_hint in dom_context
            elif label:
                # Fallback to label search
                element_found = label.lower() in dom_context.lower()

            if not element_found:
                return {
                    "success": False,
                    "element_found": False,
                    "dom_changed": False,
                    "error": f"Element '{label}' not found in DOM"
                }

            # Highlight element (send command to extension)
            self._highlight_element(element)

            # In a real implementation, this would trigger the actual click
            # For now, we just simulate success
            logger.info(f"Executed step {self.current_step}: {label}")

            return {
                "success": True,
                "element_found": True,
                "dom_changed": True,
                "error": None
            }

        except Exception as e:
            logger.error(f"Step execution failed: {e}")
            return {
                "success": False,
                "element_found": False,
                "dom_changed": False,
                "error": str(e)
            }

    async def _wait_for_dom_stabilization(self, timeout_ms: int = 2000) -> bool:
        """
        Wait for DOM changes to stabilize after an interaction.
        
        Args:
            timeout_ms: Maximum time to wait in milliseconds
            
        Returns:
            bool: True if DOM stabilized, False if timeout
        """
        # Simple implementation: wait for a fixed duration
        # In a real implementation, this would monitor DOM mutations
        await asyncio.sleep(timeout_ms / 1000.0)
        return True

    def _highlight_element(self, element: Dict) -> None:
        """
        Send highlight command to extension for current step element.
        
        Args:
            element: Element data with selector and label
        """
        # This would send a message to the extension via WebSocket or HTTP
        # For now, just log the action
        logger.debug(f"Highlighting element: {element.get('label', 'Unknown')}")


class NavigationFallbackEngine:
    """
    Main orchestrator for the navigation fallback strategy.
    
    Coordinates between:
    - RoteiroIndexer for path lookup
    - NavigationPathExtractor for roteiro parsing
    - GuidedNavigationExecutor for step-by-step navigation
    
    Implements the hierarchical fallback strategy:
    1. Check if element is visible in DOM
    2. If not, search roteiros for navigation path
    3. Format conversational offer
    4. Execute guided navigation on user confirmation
    """

    def __init__(self, roteiro_indexer: Optional[RoteiroIndexer] = None):
        """
        Initialize the NavigationFallbackEngine.
        
        Args:
            roteiro_indexer: RoteiroIndexer instance (creates new if None)
        """
        self.indexer = roteiro_indexer or RoteiroIndexer()
        self.path_extractor = NavigationPathExtractor()
        self.executor = GuidedNavigationExecutor()
        self.file_observer = None

        logger.info("NavigationFallbackEngine initialized")

    async def handle_invisible_element(
        self,
        user_query: str,
        dom_context: str,
        tenant_id: str = "senior_default"
    ) -> Dict:
        """
        Main entry point for navigation fallback.
        
        Args:
            user_query: User's question or request
            dom_context: Current DOM context
            tenant_id: Tenant identifier
            
        Returns:
            dict: {
                "mensagem": str,
                "navigation_path": list[dict] | None,
                "requires_confirmation": bool,
                "fallback_type": str,  # "navigation" | "general"
                "confidence_score": float,
                "roteiro_name": str | None
            }
        """
        try:
            # Record fallback activation
            metrics = get_navigation_metrics()
            metrics.record_fallback_activation()

            # Log event
            log_navigation_event(
                event_type="fallback_activation",
                tenant_id=tenant_id,
                user_query=user_query
            )

            # Search for navigation paths
            results = self.indexer.search(user_query, tenant_id, top_k=3)

            if not results:
                # No navigation path found - fall back to general response
                log_navigation_event(
                    event_type="no_path_found",
                    tenant_id=tenant_id,
                    user_query=user_query
                )

                return {
                    "mensagem": "Não encontrei um caminho específico para isso nos manuais. Posso tentar ajudar de outra forma?",
                    "navigation_path": None,
                    "requires_confirmation": False,
                    "fallback_type": "general",
                    "confidence_score": 0.0,
                    "roteiro_name": None
                }

            # Get best match
            best_match = results[0]
            roteiro_name = best_match["roteiro_name"]
            confidence = best_match["confidence_score"]

            # Re-extract navigation path from roteiro with target query to limit steps
            roteiro_path = Path("roteiros_salvos") / f"{roteiro_name}.json"
            if roteiro_path.exists():
                try:
                    with open(roteiro_path, 'r', encoding='utf-8') as f:
                        roteiro_data = json.load(f)

                    # Extract path with target query to stop at the target element
                    nav_path = self.path_extractor.extract_navigation_path(roteiro_data, target_query=user_query)

                    if nav_path and nav_path.get("steps"):
                        breadcrumb = nav_path["breadcrumb"]
                        navigation_path = nav_path["steps"]

                        logger.info(f"Re-extracted navigation path with {len(navigation_path)} steps (limited to target)")
                    else:
                        # Fallback to indexed path if re-extraction fails
                        breadcrumb = best_match["breadcrumb"]
                        navigation_path = best_match["navigation_path"]
                        logger.warning("Re-extraction failed, using indexed path")
                except Exception as e:
                    logger.error(f"Failed to re-extract navigation path: {e}")
                    # Fallback to indexed path
                    breadcrumb = best_match["breadcrumb"]
                    navigation_path = best_match["navigation_path"]
            else:
                # Roteiro file not found, use indexed path
                breadcrumb = best_match["breadcrumb"]
                navigation_path = best_match["navigation_path"]

            # Log path found
            log_navigation_event(
                event_type="path_found",
                tenant_id=tenant_id,
                user_query=user_query,
                roteiro_name=roteiro_name,
                confidence_score=confidence
            )

            # Format conversational offer
            mensagem = f"Ele fica dentro do {breadcrumb}, quer que eu te guie para lá?"

            return {
                "mensagem": mensagem,
                "navigation_path": navigation_path,
                "requires_confirmation": True,
                "fallback_type": "navigation",
                "confidence_score": confidence,
                "roteiro_name": roteiro_name
            }

        except Exception as e:
            logger.error(f"Navigation fallback failed: {e}")
            log_navigation_event(
                event_type="fallback_error",
                tenant_id=tenant_id,
                user_query=user_query,
                error_message=str(e)
            )

            return {
                "mensagem": "Desculpe, tive um problema ao procurar o caminho. Pode tentar de novo?",
                "navigation_path": None,
                "requires_confirmation": False,
                "fallback_type": "general",
                "confidence_score": 0.0,
                "roteiro_name": None
            }

    async def execute_guided_navigation(
        self,
        navigation_path: List[Dict],
        dom_context: str,
        confirmation: bool = True,
        tenant_id: str = "senior_default",
        roteiro_name: str = None
    ) -> Dict:
        """
        Execute step-by-step guided navigation.
        
        Args:
            navigation_path: List of navigation steps
            dom_context: Current DOM context
            confirmation: Whether user confirmed (should be True to execute)
            tenant_id: Tenant identifier
            roteiro_name: Name of the roteiro being executed
            
        Returns:
            dict: {
                "success": bool,
                "completed_steps": int,
                "failed_step": int | None,
                "error_message": str | None
            }
        """
        if not confirmation:
            return {
                "success": False,
                "completed_steps": 0,
                "failed_step": None,
                "error_message": "User declined guided navigation"
            }

        start_time = time.time()
        metrics = get_navigation_metrics()

        try:
            result = await self.executor.execute_navigation(navigation_path, dom_context)
            duration_ms = (time.time() - start_time) * 1000

            if result["success"]:
                # Record success
                metrics.record_navigation_success(duration_ms)

                log_navigation_event(
                    event_type="navigation_success",
                    tenant_id=tenant_id,
                    roteiro_name=roteiro_name,
                    success=True,
                    duration_ms=duration_ms,
                    completed_steps=result["completed_steps"]
                )
            else:
                # Record failure
                metrics.record_navigation_failure()

                log_navigation_event(
                    event_type="navigation_failure",
                    tenant_id=tenant_id,
                    roteiro_name=roteiro_name,
                    success=False,
                    error_message=result.get("error_message"),
                    duration_ms=duration_ms,
                    completed_steps=result["completed_steps"],
                    failed_step=result.get("failed_step")
                )

            return result

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"Guided navigation execution failed: {e}")

            metrics.record_navigation_failure()

            log_navigation_event(
                event_type="navigation_error",
                tenant_id=tenant_id,
                roteiro_name=roteiro_name,
                success=False,
                error_message=str(e),
                duration_ms=duration_ms
            )

            return {
                "success": False,
                "completed_steps": 0,
                "failed_step": None,
                "error_message": str(e)
            }

    def start_file_watcher(self) -> bool:
        """
        Start file watcher for automatic index updates.
        
        Returns:
            bool: True if watcher started successfully, False otherwise
        """
        if self.file_observer:
            logger.warning("File watcher already running")
            return True

        self.file_observer = self.indexer.watch_roteiros_directory()
        return self.file_observer is not None

    def stop_file_watcher(self) -> None:
        """
        Stop file watcher gracefully.
        """
        if self.file_observer:
            self.file_observer.stop()
            self.file_observer.join()
            self.file_observer = None
            logger.info("File watcher stopped")


# Global instance (initialized on app startup)
_navigation_fallback_engine: Optional[NavigationFallbackEngine] = None


def get_navigation_fallback_engine() -> Optional[NavigationFallbackEngine]:
    """
    Get the global NavigationFallbackEngine instance.
    
    Returns:
        NavigationFallbackEngine instance or None if not initialized
    """
    return _navigation_fallback_engine


def initialize_navigation_fallback_engine(roteiros_dir: str = "roteiros_salvos") -> NavigationFallbackEngine:
    """
    Initialize the global NavigationFallbackEngine instance.
    
    Args:
        roteiros_dir: Directory containing roteiro JSON files
        
    Returns:
        NavigationFallbackEngine instance
    """
    global _navigation_fallback_engine

    if not NAVIGATION_FALLBACK_ENABLED:
        logger.info("Navigation fallback is disabled")
        return None

    try:
        indexer = RoteiroIndexer(roteiros_dir=roteiros_dir)
        _navigation_fallback_engine = NavigationFallbackEngine(indexer)

        # Build initial index
        logger.info("Building initial navigation index...")
        result = indexer.build_index()
        logger.info(f"Index build result: {result}")

        # Start file watcher
        if _navigation_fallback_engine.start_file_watcher():
            logger.info("File watcher started successfully")
        else:
            logger.warning("File watcher not available - index updates will be manual")

        return _navigation_fallback_engine

    except Exception as e:
        logger.error(f"Failed to initialize navigation fallback engine: {e}")
        return None



# =========================================================
# USER CONFIRMATION PARSING
# =========================================================

def parse_confirmation_response(user_response: str) -> Optional[bool]:
    """
    Parse user response to determine if they confirmed or declined navigation.
    
    Args:
        user_response: User's response text
        
    Returns:
        True if affirmative, False if negative, None if ambiguous
    """
    response_lower = user_response.lower().strip()

    # Affirmative responses
    affirmative_patterns = [
        'sim', 'yes', 'pode', 'quero', 'vamos', 'ok', 'okay',
        'claro', 'com certeza', 'por favor', 'me guie', 'guia',
        'aceito', 'confirmo', 'vá em frente', 'vai'
    ]

    # Negative responses
    negative_patterns = [
        'não', 'nao', 'no', 'agora não', 'agora nao', 'depois',
        'não quero', 'nao quero', 'deixa', 'cancela', 'cancelar',
        'não precisa', 'nao precisa', 'obrigado', 'obrigada'
    ]

    # Check affirmative
    for pattern in affirmative_patterns:
        if pattern in response_lower:
            return True

    # Check negative
    for pattern in negative_patterns:
        if pattern in response_lower:
            return False

    # Ambiguous
    return None


# =========================================================
# NAVIGATION METRICS TRACKING
# =========================================================

class NavigationMetrics:
    """
    Track navigation fallback metrics for monitoring and optimization.
    """

    def __init__(self):
        self.fallback_activations = 0
        self.navigation_successes = 0
        self.navigation_failures = 0
        self.navigation_times_ms = []
        self.cache_hits = 0
        self.cache_misses = 0
        self.index_size = 0

    def record_fallback_activation(self):
        """Record a fallback activation."""
        self.fallback_activations += 1

    def record_navigation_success(self, duration_ms: float):
        """Record a successful navigation."""
        self.navigation_successes += 1
        self.navigation_times_ms.append(duration_ms)

    def record_navigation_failure(self):
        """Record a failed navigation."""
        self.navigation_failures += 1

    def record_cache_hit(self):
        """Record a cache hit."""
        self.cache_hits += 1

    def record_cache_miss(self):
        """Record a cache miss."""
        self.cache_misses += 1

    def update_index_size(self, size: int):
        """Update the index size."""
        self.index_size = size

    def get_metrics(self) -> Dict:
        """
        Get current metrics as a dictionary.
        
        Returns:
            dict: Current metrics
        """
        avg_time = sum(self.navigation_times_ms) / len(self.navigation_times_ms) if self.navigation_times_ms else 0
        cache_total = self.cache_hits + self.cache_misses
        cache_hit_rate = self.cache_hits / cache_total if cache_total > 0 else 0

        return {
            "fallback_activations": self.fallback_activations,
            "navigation_successes": self.navigation_successes,
            "navigation_failures": self.navigation_failures,
            "success_rate": self.navigation_successes / (self.navigation_successes + self.navigation_failures) if (self.navigation_successes + self.navigation_failures) > 0 else 0,
            "average_navigation_time_ms": avg_time,
            "cache_hit_rate": cache_hit_rate,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "index_size": self.index_size
        }

    def reset(self):
        """Reset all metrics."""
        self.__init__()


# Global metrics instance
_navigation_metrics = NavigationMetrics()


def get_navigation_metrics() -> NavigationMetrics:
    """
    Get the global NavigationMetrics instance.
    
    Returns:
        NavigationMetrics instance
    """
    return _navigation_metrics


# =========================================================
# STRUCTURED LOGGING FOR NAVIGATION EVENTS
# =========================================================

def log_navigation_event(
    event_type: str,
    tenant_id: str,
    user_query: str = None,
    roteiro_name: str = None,
    confidence_score: float = None,
    success: bool = None,
    error_message: str = None,
    duration_ms: float = None,
    completed_steps: int = None,
    failed_step: int = None
):
    """
    Log structured navigation events for monitoring and debugging.
    
    Args:
        event_type: Type of event ("fallback_activation", "navigation_success", "navigation_failure", etc.)
        tenant_id: Tenant identifier
        user_query: User's query (optional)
        roteiro_name: Name of the roteiro used (optional)
        confidence_score: Confidence score of the match (optional)
        success: Whether the navigation succeeded (optional)
        error_message: Error message if failed (optional)
        duration_ms: Duration of the navigation (optional)
        completed_steps: Number of completed steps (optional)
        failed_step: Step number that failed (optional)
    """
    log_data = {
        "event_type": event_type,
        "tenant_id": tenant_id,
        "timestamp": time.time()
    }

    if user_query:
        log_data["user_query"] = user_query
    if roteiro_name:
        log_data["roteiro_name"] = roteiro_name
    if confidence_score is not None:
        log_data["confidence_score"] = confidence_score
    if success is not None:
        log_data["success"] = success
    if error_message:
        log_data["error_message"] = error_message
    if duration_ms is not None:
        log_data["duration_ms"] = duration_ms
    if completed_steps is not None:
        log_data["completed_steps"] = completed_steps
    if failed_step is not None:
        log_data["failed_step"] = failed_step

    logger.info(f"[NavigationEvent] {json.dumps(log_data, ensure_ascii=False)}")
