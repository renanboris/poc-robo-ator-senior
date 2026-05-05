"""
next_integration.py — Senior Training OS · Next Integration Wiring
===================================================================
End-to-end wiring of all Next-Legacy Diamond Integration components.

This module provides the NextIntegration facade that connects:
  - Triage_Pipeline  ← reads and classifies shadow JSONL
  - LegacyBridge     ← maps events to ObservedAction + comparative context
  - ObservedAction_Adapter (via LegacyBridge)
  - ScreenObserver   ← enriches screen_family / component_family
  - Promotion_Gate_Engine ← evaluates promotion readiness
  - SkillMemory      ← stores and retrieves KnownSkill records
  - ShadowModeRunner (optional) ← receives comparative context

Requirements: 14.1–14.4
"""

import logging
from pathlib import Path

from legacy_bridge import LegacyBridge
from observed_action_models import ObservedAction
from promotion_engine import Promotion_Gate_Engine
from screen_observer import ScreenObserver
from skill_memory import SkillMemory
from triage_models import IngestionReport
from triage_pipeline import Triage_Pipeline

logger = logging.getLogger(__name__)


class NextIntegration:
    """
    Facade that wires all integration components together.

    Usage::

        ni = NextIntegration()
        report = ni.ingest_file("shadow_exports/capture.jsonl")
        skills = ni.skill_memory.retrieve(mode="family", screen_family="ged_list", ...)
    """

    def __init__(self) -> None:
        # 14.1 — LegacyBridge + Triage_Pipeline
        self.triage          = Triage_Pipeline()
        self.bridge          = LegacyBridge()

        # 14.2 — ScreenObserver wired into adapter via bridge
        self.screen_observer = ScreenObserver()

        # 14.3 — Promotion_Gate_Engine + SkillMemory
        self.gate_engine     = Promotion_Gate_Engine()
        self.skill_memory    = SkillMemory()

    # ──────────────────────────────────────────────────────────
    # 14.1 — Ingest a shadow JSONL file through triage + bridge
    # ──────────────────────────────────────────────────────────

    def ingest_file(
        self,
        path: str,
        shadow_mode_runner=None,
    ) -> IngestionReport:
        """
        Full ingestion pipeline for a single shadow JSONL file.

        Steps:
          1. Triage_Pipeline classifies events (accepted / review / rejected).
          2. Accepted events are read by LegacyBridge and mapped to ObservedAction.
          3. ScreenObserver enriches screen_family / component_family when missing.
          4. Promotion_Gate_Engine evaluates each ObservedAction.
          5. Comparative context is delivered to ShadowModeRunner (if provided).

        Args:
            path:               Path to the shadow JSONL file.
            shadow_mode_runner: Optional ShadowModeRunner instance.

        Returns:
            IngestionReport from the triage step.
        """
        # Step 1 — triage
        report = self.triage.ingest_shadow_file(path)
        logger.info("Triage complete: %s", report.summary())

        # Step 2 — read accepted events via bridge
        try:
            events = self.bridge.read_shadow_file(path)
        except FileNotFoundError:
            logger.error("File not found during bridge read: %s", path)
            return report

        accepted_ids = {ev["identifier"] for ev in report.review_events}  # review ids
        rejected_ids = {ev["identifier"] for ev in report.rejected_events}

        for event in events:
            event_id = str(event.get("id_acao", ""))
            if event_id in rejected_ids:
                continue  # already rejected by triage

            # Step 3 — enrich screen/component family via ScreenObserver (14.2)
            if not event.get("screen_family") or event.get("screen_family") == "unknown":
                sf, review = self.screen_observer.classify_screen(
                    page_title=event.get("page_title", ""),
                    url_hint=event.get("url_hint", ""),
                )
                event["screen_family"] = sf
                if review:
                    event["review_required"] = True

            elem = event.get("elemento_alvo", {})
            if not event.get("component_family") or event.get("component_family") == "unknown":
                cf = self.screen_observer.infer_component_family(
                    seletor_hint=elem.get("seletor_hint", ""),
                    tag=elem.get("tipo_elemento", ""),
                    label=event.get("business_target", ""),
                )
                event["component_family"] = cf

            # Step 4 — map to ObservedAction
            obs: ObservedAction = self.bridge.map_to_observed_action(event, source_file=path)

            # Step 4b — evaluate promotion readiness (14.3)
            level, state = self.gate_engine.evaluate_promotion_readiness(event)
            logger.debug(
                "Event promotion level: %d (%s)",
                level,
                state,
                extra={"id_acao": event.get("id_acao")},
            )

            # Step 5 — deliver comparative context to ShadowModeRunner (14.4)
            if shadow_mode_runner is not None:
                ctx = self.bridge.deliver_comparative_context(
                    event, mapped_action=obs, source_file=path
                )
                try:
                    shadow_mode_runner.receive_context(ctx)
                except AttributeError:
                    logger.debug("ShadowModeRunner has no receive_context method — skipping")

        return report

    def ingest_directory(
        self,
        directory: str,
        shadow_mode_runner=None,
    ) -> list[IngestionReport]:
        """
        Ingest all shadow JSONL files in a directory.

        Args:
            directory:          Path to the directory.
            shadow_mode_runner: Optional ShadowModeRunner instance.

        Returns:
            List of IngestionReport, one per file.
        """
        dir_path = Path(directory)
        reports: list[IngestionReport] = []
        for jsonl_file in sorted(dir_path.glob("*.jsonl")):
            try:
                report = self.ingest_file(str(jsonl_file), shadow_mode_runner)
                reports.append(report)
            except Exception as exc:
                logger.error("Failed to ingest %s: %s", jsonl_file, exc)
        return reports
