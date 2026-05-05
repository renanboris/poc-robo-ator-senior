"""
Aura Security Guardrails Module

This module provides comprehensive security controls for the Aura DAP system.
It validates user prompts against multiple security threats including:
- SQL injection attempts
- Prompt injection attacks
- Offensive content
- Competitor mentions

All guardrails execute in parallel to preserve performance (<200ms overhead).
Configuration is loaded from environment variables for runtime control.
"""

import asyncio
import hashlib
import json
import logging
import os
import re
import sqlite3
import time
import urllib.parse
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

# Configure logger for guardrails module
logger = logging.getLogger(__name__)


@dataclass
class GuardrailResult:
    """
    Result of a guardrail security check.
    
    Attributes:
        passed: Whether the guardrail check passed (True) or failed (False)
        guardrail_name: Name of the guardrail that performed the check
        severity: Severity level of the violation ("low", "medium", "high", "critical")
        message: Optional user-friendly error message to display
        details: Optional dictionary with additional context about the violation
    """
    passed: bool
    guardrail_name: str
    severity: str  # "low", "medium", "high", "critical"
    message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class GuardrailConfig:
    """
    Configuration for the guardrail system loaded from environment variables.
    
    All guardrails are enabled by default. Set environment variables to "false"
    to disable specific checks.
    
    Environment Variables:
        ENABLE_SQL_INJECTION_CHECK: Enable SQL injection detection (default: true)
        ENABLE_PROMPT_INJECTION_CHECK: Enable prompt injection detection (default: true)
        ENABLE_OFFENSIVE_CONTENT_FILTER: Enable offensive content filtering (default: true)
        ENABLE_COMPETITOR_FILTER: Enable competitor mention detection (default: true)
        ENABLE_VECTOR_STORE_ONLY: Enforce vector store content restriction (default: true)
    """

    def __init__(
        self,
        enable_sql_injection: bool,
        enable_prompt_injection: bool,
        enable_offensive_content: bool,
        enable_competitor_filter: bool,
        enable_vector_store_only: bool
    ):
        self.enable_sql_injection = enable_sql_injection
        self.enable_prompt_injection = enable_prompt_injection
        self.enable_offensive_content = enable_offensive_content
        self.enable_competitor_filter = enable_competitor_filter
        self.enable_vector_store_only = enable_vector_store_only

    @classmethod
    def from_env(cls) -> "GuardrailConfig":
        """
        Load guardrail configuration from environment variables.
        
        All checks are enabled by default. Set environment variable to "false"
        (case-insensitive) to disable a specific guardrail.
        
        Returns:
            GuardrailConfig instance with settings loaded from environment
        """
        return cls(
            enable_sql_injection=os.getenv("ENABLE_SQL_INJECTION_CHECK", "true").lower() == "true",
            enable_prompt_injection=os.getenv("ENABLE_PROMPT_INJECTION_CHECK", "true").lower() == "true",
            enable_offensive_content=os.getenv("ENABLE_OFFENSIVE_CONTENT_FILTER", "true").lower() == "true",
            enable_competitor_filter=os.getenv("ENABLE_COMPETITOR_FILTER", "true").lower() == "true",
            enable_vector_store_only=os.getenv("ENABLE_VECTOR_STORE_ONLY", "true").lower() == "true",
        )


def _get_user_message(guardrail_name: str) -> str:
    """
    Map guardrail names to user-friendly error messages.
    
    Args:
        guardrail_name: Name of the triggered guardrail
        
    Returns:
        User-friendly error message
    """
    messages = {
        "sql_injection": "Your request contains patterns that cannot be processed. Please rephrase your question.",
        "prompt_injection": "I can only help with Senior X questions. Please ask about specific features or tasks.",
        "offensive_content": "Please keep your questions professional. How can I help you with Senior X?",
        "competitor_mention": "I can help you with Senior X features. What would you like to accomplish?"
    }
    return messages.get(guardrail_name, "Your request cannot be processed. Please try rephrasing.")


class GuardrailEngine:
    """
    Main guardrail validation engine.
    
    Executes all enabled guardrails in parallel to validate user prompts
    before they reach the AI generation layer.
    """

    def __init__(self, config: GuardrailConfig):
        """
        Initialize the guardrail engine with configuration.
        
        Args:
            config: GuardrailConfig instance with enabled/disabled flags
        """
        self.config = config
        self.sql_patterns = self._load_sql_patterns()
        self.prompt_injection_patterns = self._load_prompt_injection_patterns()
        self.offensive_terms = self._load_offensive_terms()
        self.competitor_names = self._load_competitor_names()

    def _load_sql_patterns(self) -> List[re.Pattern]:
        """
        Load SQL injection detection patterns.
        
        Detects SQL keywords combined with special characters that indicate
        potential SQL injection attempts.
        
        Returns:
            List of compiled regex patterns for SQL injection detection
        """
        patterns = [
            # SQL keywords with FROM/INTO/TABLE/DATABASE
            re.compile(r'(?i)(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER|CREATE|EXEC)\s+.*(FROM|INTO|TABLE|DATABASE)', re.IGNORECASE),

            # OR/AND with numeric equality (e.g., OR 1=1)
            re.compile(r'(?i)(OR|AND)\s+\d+\s*=\s*\d+', re.IGNORECASE),

            # OR/AND with string equality (e.g., OR '1'='1')
            re.compile(r'(?i)(OR|AND)\s+[\'"][^\'"]*[\'"]\s*=\s*[\'"][^\'"]*[\'"]', re.IGNORECASE),

            # Quote followed by OR/AND (common injection pattern)
            re.compile(r'[\'\"]\s+(OR|AND)\s+', re.IGNORECASE),

            # SQL comment sequences
            re.compile(r'--|\*\/|\/\*', re.IGNORECASE),

            # UNION SELECT attacks
            re.compile(r'(?i)UNION\s+SELECT', re.IGNORECASE),

            # SQL keywords with semicolon (statement termination)
            re.compile(r'(?i)(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER|CREATE|EXEC).*;', re.IGNORECASE),

            # SQL keywords with quotes (string manipulation)
            re.compile(r'(?i)(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER|CREATE|EXEC).*[\'"]', re.IGNORECASE),
        ]
        return patterns

    def _load_prompt_injection_patterns(self) -> List[re.Pattern]:
        """
        Load prompt injection detection patterns.
        
        Detects attempts to manipulate AI behavior through instruction override,
        role switching, or system prompt revelation.
        
        Returns:
            List of compiled regex patterns for prompt injection detection
        """
        patterns = [
            # Ignore previous instructions variations
            re.compile(r'(?i)ignore\s+(previous|all|prior)\s+(instructions|rules|prompts)', re.IGNORECASE),

            # Ignore all/prior without specific noun
            re.compile(r'(?i)ignore\s+(all|prior)\s+\w+', re.IGNORECASE),

            # Disregard rules variations
            re.compile(r'(?i)disregard\s+(all|previous|prior)', re.IGNORECASE),

            # Reveal prompt/instructions
            re.compile(r'(?i)reveal\s+(your|the)\s+(prompt|instructions|system)', re.IGNORECASE),

            # Show me system/instructions
            re.compile(r'(?i)show\s+me\s+(your|the)\s+(system|instructions|prompt)', re.IGNORECASE),

            # What is your prompt/instructions
            re.compile(r'(?i)what\s+(is|are)\s+(your|the)\s+(prompt|instructions|system)', re.IGNORECASE),

            # Tell me the prompt/instructions
            re.compile(r'(?i)tell\s+me\s+(your|the)\s+(prompt|instructions|system)', re.IGNORECASE),

            # Role switching
            re.compile(r'(?i)you\s+are\s+now\s+(a|an)', re.IGNORECASE),

            # System/Assistant/User role markers
            re.compile(r'(?i)(system|assistant|user)\s*:', re.IGNORECASE),

            # Forget instructions - with "all your"
            re.compile(r'(?i)forget\s+(all|previous)\s+(your\s+)?(instructions|rules)', re.IGNORECASE),

            # Act as variations
            re.compile(r'(?i)act\s+as\s+(if|a|an)', re.IGNORECASE),

            # Pretend to be
            re.compile(r'(?i)pretend\s+(to\s+be|you\s+are)', re.IGNORECASE),
        ]
        return patterns

    def _load_offensive_terms(self) -> Dict[str, Set[str]]:
        """
        Load offensive terms from configuration file with fallback to hardcoded list.
        
        Loads from offensive_terms.json if available, otherwise uses a minimal
        hardcoded fallback list. Terms are stored in lowercase for case-insensitive
        matching.
        
        Returns:
            Dictionary with language codes as keys and sets of offensive terms as values
        """
        try:
            with open("offensive_terms.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                # Convert lists to sets and lowercase all terms
                return {
                    lang: {term.lower() for term in terms}
                    for lang, terms in data.items()
                }
        except (FileNotFoundError, json.JSONDecodeError) as e:
            # Log warning and use fallback
            print(f"[WARNING] Could not load offensive_terms.json: {e}. Using fallback list.")

            # Minimal fallback list for Portuguese and English
            # In production, this should be loaded from configuration
            return {
                "pt": {
                    "merda", "porra", "caralho", "foda", "cu", "puta", "viado",
                    "buceta", "cacete", "desgraça", "idiota", "imbecil"
                },
                "en": {
                    "fuck", "shit", "damn", "bitch", "asshole", "bastard",
                    "crap", "hell", "dick", "pussy"
                }
            }

    def _load_competitor_names(self) -> List[Dict[str, Any]]:
        """
        Load competitor names from configuration file with fallback to hardcoded list.
        
        Loads from competitor_names.json if available, otherwise uses a default
        list of known ERP competitors.
        
        Returns:
            List of competitor dictionaries with 'name' and 'variants' fields
        """
        try:
            with open("competitor_names.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("competitors", [])
        except (FileNotFoundError, json.JSONDecodeError) as e:
            # Log warning and use fallback
            print(f"[WARNING] Could not load competitor_names.json: {e}. Using fallback list.")

            # Default competitor list
            return [
                {"name": "SAP", "variants": ["SAP S/4HANA", "SAP ERP", "SAP Business One", "S/4HANA"]},
                {"name": "Oracle", "variants": ["Oracle EBS", "Oracle Cloud", "Oracle Fusion", "Oracle E-Business Suite"]},
                {"name": "Totvs", "variants": ["Protheus", "RM", "Datasul", "TOTVS Protheus"]},
                {"name": "Sankhya", "variants": ["Sankhya W"]},
                {"name": "Microsiga", "variants": []}
            ]

    async def _check_sql_injection(self, prompt: str) -> GuardrailResult:
        """
        Detect SQL injection patterns in user prompt.
        
        Checks for SQL keywords combined with special characters, encoded
        variations, and suspicious syntax patterns.
        
        Args:
            prompt: User input to validate
            
        Returns:
            GuardrailResult indicating pass/fail with details
        """
        # Check URL-decoded version to catch encoded attacks
        decoded_prompt = urllib.parse.unquote(prompt)

        # Check both original and decoded versions
        for text in [prompt, decoded_prompt]:
            for pattern in self.sql_patterns:
                match = pattern.search(text)
                if match:
                    return GuardrailResult(
                        passed=False,
                        guardrail_name="sql_injection",
                        severity="critical",
                        message=_get_user_message("sql_injection"),
                        details={
                            "pattern_matched": pattern.pattern,
                            "matched_text": match.group(0)
                        }
                    )

        return GuardrailResult(
            passed=True,
            guardrail_name="sql_injection",
            severity="critical"
        )

    async def _check_prompt_injection(self, prompt: str) -> GuardrailResult:
        """
        Detect prompt injection attempts in user prompt.
        
        Checks for manipulation phrases, role switching instructions,
        and attempts to reveal system prompts.
        
        Args:
            prompt: User input to validate
            
        Returns:
            GuardrailResult indicating pass/fail with details
        """
        # Check URL-decoded version to catch encoded attacks
        decoded_prompt = urllib.parse.unquote(prompt)

        # Check both original and decoded versions
        for text in [prompt, decoded_prompt]:
            for pattern in self.prompt_injection_patterns:
                match = pattern.search(text)
                if match:
                    return GuardrailResult(
                        passed=False,
                        guardrail_name="prompt_injection",
                        severity="high",
                        message=_get_user_message("prompt_injection"),
                        details={
                            "pattern_matched": pattern.pattern,
                            "matched_text": match.group(0)
                        }
                    )

        return GuardrailResult(
            passed=True,
            guardrail_name="prompt_injection",
            severity="high"
        )

    async def _check_offensive_content(self, prompt: str) -> GuardrailResult:
        """
        Detect offensive language in user prompt.
        
        Checks for profanity and inappropriate content in multiple languages
        (Portuguese and English). Uses fuzzy matching for common misspellings.
        
        Args:
            prompt: User input to validate
            
        Returns:
            GuardrailResult indicating pass/fail with details
        """
        # Normalize prompt for matching (lowercase, URL decode)
        decoded_prompt = urllib.parse.unquote(prompt)
        normalized_prompt = decoded_prompt.lower()

        # Check all languages
        detected_terms = []
        for lang, terms in self.offensive_terms.items():
            for term in terms:
                # Direct match
                if term in normalized_prompt:
                    detected_terms.append(term)
                    continue

                # Fuzzy match for common character substitutions
                # (e.g., @ for a, 0 for o, 1 for i, 3 for e, $ for s)
                fuzzy_term = term
                fuzzy_term = fuzzy_term.replace('a', '[a@4]')
                fuzzy_term = fuzzy_term.replace('e', '[e3]')
                fuzzy_term = fuzzy_term.replace('i', '[i1!]')
                fuzzy_term = fuzzy_term.replace('o', '[o0]')
                fuzzy_term = fuzzy_term.replace('s', '[s$5]')

                fuzzy_pattern = re.compile(fuzzy_term, re.IGNORECASE)
                if fuzzy_pattern.search(normalized_prompt):
                    detected_terms.append(term)

        if detected_terms:
            # Sanitize prompt for logging (replace offensive words with [REDACTED])
            sanitized_prompt = prompt
            for term in detected_terms:
                sanitized_prompt = re.sub(
                    re.escape(term),
                    "[REDACTED]",
                    sanitized_prompt,
                    flags=re.IGNORECASE
                )

            return GuardrailResult(
                passed=False,
                guardrail_name="offensive_content",
                severity="medium",
                message=_get_user_message("offensive_content"),
                details={
                    "detected_terms_count": len(detected_terms),
                    "sanitized_prompt": sanitized_prompt
                }
            )

        return GuardrailResult(
            passed=True,
            guardrail_name="offensive_content",
            severity="medium"
        )

    async def _check_competitor_mention(self, prompt: str) -> GuardrailResult:
        """
        Detect competitor product or company mentions in user prompt.
        
        Checks for mentions of competitor ERP systems and their product variants.
        Uses case-insensitive matching.
        
        Args:
            prompt: User input to validate
            
        Returns:
            GuardrailResult indicating pass/fail with details
        """
        # Normalize prompt for matching (lowercase, URL decode)
        decoded_prompt = urllib.parse.unquote(prompt)
        normalized_prompt = decoded_prompt.lower()

        detected_competitors = []

        for competitor in self.competitor_names:
            competitor_name = competitor["name"]
            variants = competitor.get("variants", [])

            # Check main competitor name
            if competitor_name.lower() in normalized_prompt:
                detected_competitors.append(competitor_name)
                continue

            # Check product variants
            for variant in variants:
                if variant.lower() in normalized_prompt:
                    detected_competitors.append(f"{competitor_name} ({variant})")
                    break

        if detected_competitors:
            return GuardrailResult(
                passed=False,
                guardrail_name="competitor_mention",
                severity="low",
                message=_get_user_message("competitor_mention"),
                details={
                    "detected_competitors": detected_competitors
                }
            )

        return GuardrailResult(
            passed=True,
            guardrail_name="competitor_mention",
            severity="low"
        )

    async def _execute_guardrail_with_timeout(
        self,
        guardrail_coro,
        guardrail_name: str,
        timeout_ms: float = 100.0
    ) -> Optional[GuardrailResult]:
        """
        Execute a single guardrail check with timeout monitoring.
        
        Logs a warning if the check takes longer than the specified timeout.
        If the check raises an exception, logs a warning and returns None
        (allowing other guardrails to continue).
        
        Args:
            guardrail_coro: Coroutine for the guardrail check
            guardrail_name: Name of the guardrail for logging
            timeout_ms: Timeout threshold in milliseconds (default: 100ms)
            
        Returns:
            GuardrailResult if successful, None if failed with exception
        """
        start_time = time.time()

        try:
            result = await guardrail_coro

            # Check execution time and log warning if exceeded
            elapsed_ms = (time.time() - start_time) * 1000
            if elapsed_ms > timeout_ms:
                logger.warning(
                    f"[GUARDRAIL] {guardrail_name} took {elapsed_ms:.2f}ms "
                    f"(threshold: {timeout_ms}ms)"
                )

            return result

        except Exception as e:
            # Log error but don't raise - allow other guardrails to continue
            elapsed_ms = (time.time() - start_time) * 1000
            logger.warning(
                f"[GUARDRAIL] {guardrail_name} failed after {elapsed_ms:.2f}ms: {e}",
                exc_info=True
            )
            return None

    async def validate_prompt(
        self,
        prompt: str,
        tenant_id: str
    ) -> List[GuardrailResult]:
        """
        Validate prompt against all enabled guardrails in parallel.
        
        Executes all enabled guardrail checks concurrently with error handling
        and timeout monitoring. Individual guardrail failures are logged but
        do not prevent other guardrails from executing.
        
        Timeout warnings are logged for checks exceeding 100ms.
        
        Args:
            prompt: User input to validate
            tenant_id: Tenant identifier for multi-tenant isolation
            
        Returns:
            List of failed GuardrailResult objects (empty if all passed)
        """
        start_time = time.time()
        tasks = []
        guardrail_names = []

        # Build list of enabled guardrail tasks with their names
        if self.config.enable_sql_injection:
            tasks.append(
                self._execute_guardrail_with_timeout(
                    self._check_sql_injection(prompt),
                    "sql_injection"
                )
            )
            guardrail_names.append("sql_injection")

        if self.config.enable_prompt_injection:
            tasks.append(
                self._execute_guardrail_with_timeout(
                    self._check_prompt_injection(prompt),
                    "prompt_injection"
                )
            )
            guardrail_names.append("prompt_injection")

        if self.config.enable_offensive_content:
            tasks.append(
                self._execute_guardrail_with_timeout(
                    self._check_offensive_content(prompt),
                    "offensive_content"
                )
            )
            guardrail_names.append("offensive_content")

        if self.config.enable_competitor_filter:
            tasks.append(
                self._execute_guardrail_with_timeout(
                    self._check_competitor_mention(prompt),
                    "competitor_mention"
                )
            )
            guardrail_names.append("competitor_mention")

        # Execute all guardrails in parallel
        # gather with return_exceptions=False since we handle exceptions in wrapper
        results = await asyncio.gather(*tasks)

        # Calculate total execution time
        total_elapsed_ms = (time.time() - start_time) * 1000

        # Log warning if total execution time exceeds 200ms
        if total_elapsed_ms > 200.0:
            logger.warning(
                f"[GUARDRAIL] Total validation took {total_elapsed_ms:.2f}ms "
                f"(threshold: 200ms) for {len(tasks)} guardrails"
            )

        # Filter out None results (failed guardrails) and return only violations
        # None results are from guardrails that raised exceptions
        valid_results = [r for r in results if r is not None]

        # Return only failed guardrails (passed=False)
        return [r for r in valid_results if not r.passed]



class SecurityEventLogger:
    """
    Logs security events to brain.db for audit trail and threat analysis.
    
    All security events are persisted asynchronously to avoid blocking request
    processing. Prompts are hashed (SHA-256) for privacy compliance.
    
    Database Schema:
        aura_security_events table with columns:
        - id: INTEGER PRIMARY KEY AUTOINCREMENT
        - event_type: TEXT NOT NULL (e.g., "guardrail_blocked")
        - timestamp: INTEGER NOT NULL (milliseconds since epoch)
        - tenant_id: TEXT NOT NULL
        - user_id: TEXT (anonymized user identifier)
        - prompt_hash: TEXT NOT NULL (SHA-256 hash of prompt)
        - guardrail_triggered: TEXT NOT NULL (name of guardrail)
        - severity_level: TEXT NOT NULL ("low", "medium", "high", "critical")
        - details: TEXT (JSON-encoded additional context)
    """

    def __init__(self, db_path: str = "brain.db"):
        """
        Initialize the security event logger.
        
        Args:
            db_path: Path to SQLite database file (default: "brain.db")
        """
        self.db_path = db_path
        self._init_table()

    def _init_table(self):
        """
        Create aura_security_events table and indexes if they don't exist.
        
        This method is idempotent and safe to call multiple times.
        Creates:
        - aura_security_events table with full schema
        - idx_security_events_tenant index for tenant-based queries
        - idx_security_events_type index for event type queries
        """
        try:
            with sqlite3.connect(self.db_path, timeout=5) as conn:
                # Create main security events table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS aura_security_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_type TEXT NOT NULL,
                        timestamp INTEGER NOT NULL,
                        tenant_id TEXT NOT NULL,
                        user_id TEXT,
                        prompt_hash TEXT NOT NULL,
                        guardrail_triggered TEXT NOT NULL,
                        severity_level TEXT NOT NULL,
                        details TEXT
                    )
                """)

                # Create index for tenant-based queries
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_security_events_tenant
                    ON aura_security_events (tenant_id, timestamp)
                """)

                # Create index for event type queries
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_security_events_type
                    ON aura_security_events (event_type, timestamp)
                """)

                conn.commit()
                logger.info("[SECURITY] aura_security_events table initialized successfully")

        except Exception as e:
            # Log error but don't raise - table initialization failure should not
            # prevent application startup
            logger.warning(
                f"[SECURITY] Failed to initialize aura_security_events table: {e}",
                exc_info=True
            )

    async def log_event(
        self,
        event_type: str,
        tenant_id: str,
        prompt: str,
        guardrail_name: str,
        severity: str,
        user_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log a security event asynchronously.
        
        Prompts are hashed (SHA-256) for privacy - full prompts are never stored.
        The write operation is executed in a thread pool to avoid blocking the
        async event loop.
        
        Args:
            event_type: Type of security event (e.g., "guardrail_blocked")
            tenant_id: Tenant identifier for multi-tenant isolation
            prompt: User prompt to hash (never stored in plaintext)
            guardrail_name: Name of the guardrail that triggered
            severity: Severity level ("low", "medium", "high", "critical")
            user_id: Optional anonymized user identifier
            details: Optional dictionary with additional context
            
        Note:
            This method does not raise exceptions. Database write failures are
            logged but do not block request processing (Requirement 7.3).
        """
        # Hash the prompt for privacy (SHA-256)
        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()

        # Generate timestamp in milliseconds since epoch
        timestamp = int(time.time() * 1000)

        # Serialize details to JSON if provided
        details_json = json.dumps(details) if details else None

        # Define the database write operation
        def _write():
            try:
                with sqlite3.connect(self.db_path, timeout=5) as conn:
                    conn.execute("""
                        INSERT INTO aura_security_events 
                        (event_type, timestamp, tenant_id, user_id, prompt_hash, 
                         guardrail_triggered, severity_level, details)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        event_type, timestamp, tenant_id, user_id, prompt_hash,
                        guardrail_name, severity, details_json
                    ))
                    conn.commit()

                    # Log successful event recording
                    logger.info(
                        f"[SECURITY] {event_type} blocked for tenant {tenant_id} - "
                        f"{guardrail_name} ({severity})"
                    )

            except Exception as e:
                # Log error but don't raise - logging failures should not block
                # request processing (Requirement 7.3)
                logger.warning(
                    f"[SECURITY] Failed to log security event: {e}",
                    exc_info=True
                )

        # Execute database write in thread pool to avoid blocking async loop
        # This ensures logging completes within 100ms requirement (Requirement 7.3)
        await asyncio.to_thread(_write)
