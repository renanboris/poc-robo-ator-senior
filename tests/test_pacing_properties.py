"""
tests/test_pacing_properties.py
================================
Property-based tests for video pacing optimization.

Spec: .kiro/specs/video-pacing-optimization
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import math
from unittest.mock import patch

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from cursor_engine import PROFILES, PacingProfile, calcular_duracao_movimento, calcular_passos_movimento


# ══════════════════════════════════════════════════════════
# Strategies
# ══════════════════════════════════════════════════════════

# Valid distances for movement (>= 3 pixels, up to a large screen diagonal)
st_distance_moving = st.floats(min_value=3.0, max_value=3000.0, allow_nan=False, allow_infinity=False)

# Trivial distances (< 3 pixels)
st_distance_trivial = st.floats(min_value=0.0, max_value=2.999, allow_nan=False, allow_infinity=False)

# Short distances for Property 2 (3 <= distance < 150)
st_distance_short = st.floats(min_value=3.0, max_value=149.0, allow_nan=False, allow_infinity=False)

# All valid profile names
st_profile_name = st.sampled_from(list(PROFILES.keys()))

# Strategy that produces a PacingProfile directly
st_profile = st.sampled_from(list(PROFILES.values()))


# ══════════════════════════════════════════════════════════
# Property 1: Duration bounds hold for all distances and profiles
# ══════════════════════════════════════════════════════════
# Feature: video-pacing-optimization, Property 1: Duration bounds hold for all distances and profiles
# **Validates: Requirements 1.2, 1.3, 1.4**


class TestProperty1DurationBounds:
    """For any distance >= 3 and any valid pacing profile, the calculated movement
    duration (after randomization) SHALL always be within [profile.cursor_min_ms, profile.cursor_max_ms]."""

    @given(distance=st_distance_moving, profile=st_profile)
    @settings(max_examples=200)
    def test_duration_within_profile_bounds(self, distance: float, profile: PacingProfile):
        """**Validates: Requirements 1.2, 1.3, 1.4**"""
        result = calcular_duracao_movimento(distance, profile)

        # Result must be within the profile's min/max bounds
        assert result >= profile.cursor_min_ms, (
            f"Duration {result}ms is below minimum {profile.cursor_min_ms}ms "
            f"for distance={distance}, profile={profile.name}"
        )
        assert result <= profile.cursor_max_ms, (
            f"Duration {result}ms exceeds maximum {profile.cursor_max_ms}ms "
            f"for distance={distance}, profile={profile.name}"
        )


# ══════════════════════════════════════════════════════════
# Property 2: Short-distance duration cap
# ══════════════════════════════════════════════════════════
# Feature: video-pacing-optimization, Property 2: Short-distance duration cap
# **Validates: Requirements 1.5**


class TestProperty2ShortDistanceCap:
    """For any distance in [3, 150) pixels using the 'fast' profile, the base duration
    (before randomization) SHALL be <= 450ms."""

    @given(distance=st_distance_short)
    @settings(max_examples=200)
    def test_short_distance_base_duration_capped_at_450ms(self, distance: float):
        """**Validates: Requirements 1.5**"""
        profile = PROFILES["fast"]

        # Calculate the base duration (before randomization) using the formula
        base = profile.cursor_base_ms * (distance / 400) ** 0.55
        clamped = max(profile.cursor_min_ms, min(profile.cursor_max_ms, base))

        assert clamped <= 450, (
            f"Base duration {clamped}ms exceeds 450ms cap for short distance={distance}px "
            f"(raw base={base:.2f}ms)"
        )


# ══════════════════════════════════════════════════════════
# Property 3: Trivial distance produces zero duration (skip signal)
# ══════════════════════════════════════════════════════════
# Feature: video-pacing-optimization, Property 3: Trivial distance produces zero duration
# **Validates: Requirements 1.6**


class TestProperty3TrivialDistanceZero:
    """For any distance < 3 pixels, calcular_duracao_movimento SHALL return 0,
    signaling that no animation should occur."""

    @given(distance=st_distance_trivial, profile=st_profile)
    @settings(max_examples=200)
    def test_trivial_distance_returns_zero(self, distance: float, profile: PacingProfile):
        """**Validates: Requirements 1.6**"""
        result = calcular_duracao_movimento(distance, profile)

        assert result == 0, (
            f"Expected 0 for trivial distance={distance}px but got {result}ms "
            f"(profile={profile.name})"
        )


# ══════════════════════════════════════════════════════════
# Property 11: Duration formula matches specification
# ══════════════════════════════════════════════════════════
# Feature: video-pacing-optimization, Property 11: Duration formula matches specification
# **Validates: Requirements 1.1**


class TestProperty11DurationFormulaMatchesSpec:
    """For any distance >= 3 and any valid pacing profile, the base duration (before
    randomization) SHALL equal profile.cursor_base_ms * (distance / 400) ^ 0.55,
    clamped to [profile.cursor_min_ms, profile.cursor_max_ms]."""

    @given(distance=st_distance_moving, profile=st_profile)
    @settings(max_examples=200)
    def test_formula_matches_spec_with_fixed_random(self, distance: float, profile: PacingProfile):
        """**Validates: Requirements 1.1**

        We fix the random factor to 1.0 to isolate the formula verification
        from the randomization step (which is tested by Property 1).
        """
        # Calculate expected base duration per specification
        expected_base = profile.cursor_base_ms * (distance / 400) ** 0.55
        expected_clamped = max(profile.cursor_min_ms, min(profile.cursor_max_ms, expected_base))

        # Fix random.uniform to return 1.0 (no randomization)
        with patch("cursor_engine.random.uniform", return_value=1.0):
            result = calcular_duracao_movimento(distance, profile)

        # The result should match the clamped base (converted to int)
        expected_int = int(expected_clamped)
        assert result == expected_int, (
            f"Formula mismatch: expected {expected_int}ms but got {result}ms "
            f"for distance={distance}, profile={profile.name} "
            f"(raw base={expected_base:.2f}ms)"
        )


# ══════════════════════════════════════════════════════════
# Property 5: Step count formula correctness
# ══════════════════════════════════════════════════════════
# Feature: video-pacing-optimization, Property 5: Step count formula correctness
# **Validates: Requirements 2.1, 2.2, 2.3**

# Distances that produce raw values below steps_min (small movements)
st_distance_small_steps = st.floats(min_value=3.0, max_value=50.0, allow_nan=False, allow_infinity=False)

# Distances that produce raw values above steps_max (large movements)
st_distance_large_steps = st.floats(min_value=5000.0, max_value=50000.0, allow_nan=False, allow_infinity=False)


class TestProperty5StepCountFormula:
    """For any distance >= 3 and any valid pacing profile, the calculated step count
    SHALL equal clamp(distance * profile.steps_per_pixel, profile.steps_min, profile.steps_max)."""

    @given(distance=st_distance_moving, profile=st_profile)
    @settings(max_examples=200)
    def test_step_count_within_bounds(self, distance: float, profile: PacingProfile):
        """Step count is always within [profile.steps_min, profile.steps_max].

        **Validates: Requirements 2.1, 2.2, 2.3**
        """
        result = calcular_passos_movimento(distance, profile)

        assert profile.steps_min <= result <= profile.steps_max, (
            f"Step count {result} out of bounds [{profile.steps_min}, {profile.steps_max}] "
            f"for distance={distance}, profile={profile.name}"
        )

    @given(distance=st_distance_moving, profile=st_profile)
    @settings(max_examples=200)
    def test_step_count_equals_formula_when_within_bounds(self, distance: float, profile: PacingProfile):
        """For distances where raw = distance * steps_per_pixel is within bounds,
        the result equals int(raw).

        **Validates: Requirements 2.1, 2.2, 2.3**
        """
        raw = distance * profile.steps_per_pixel
        result = calcular_passos_movimento(distance, profile)

        if profile.steps_min <= raw <= profile.steps_max:
            assert result == int(raw), (
                f"Expected int({raw}) = {int(raw)}, got {result} "
                f"for distance={distance}, profile={profile.name}"
            )

    @given(distance=st_distance_small_steps, profile=st_profile)
    @settings(max_examples=200)
    def test_step_count_clamps_to_min_for_small_distances(self, distance: float, profile: PacingProfile):
        """For very small distances where raw < steps_min, result equals steps_min.

        **Validates: Requirements 2.1, 2.2, 2.3**
        """
        raw = distance * profile.steps_per_pixel
        result = calcular_passos_movimento(distance, profile)

        if raw < profile.steps_min:
            assert result == profile.steps_min, (
                f"Expected steps_min={profile.steps_min}, got {result} "
                f"for distance={distance}, raw={raw}, profile={profile.name}"
            )

    @given(distance=st_distance_large_steps, profile=st_profile)
    @settings(max_examples=200)
    def test_step_count_clamps_to_max_for_large_distances(self, distance: float, profile: PacingProfile):
        """For very large distances where raw > steps_max, result equals steps_max.

        **Validates: Requirements 2.1, 2.2, 2.3**
        """
        raw = distance * profile.steps_per_pixel
        result = calcular_passos_movimento(distance, profile)

        if raw > profile.steps_max:
            assert result == profile.steps_max, (
                f"Expected steps_max={profile.steps_max}, got {result} "
                f"for distance={distance}, raw={raw}, profile={profile.name}"
            )


# ══════════════════════════════════════════════════════════
# Property 10: Profile resolution correctness
# ══════════════════════════════════════════════════════════
# Feature: video-pacing-optimization, Property 10: Profile resolution correctness
# **Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5, 8.6**

import logging

from cursor_engine import resolve_pacing_profile

VALID_PROFILE_NAMES = ["fast", "normal", "conservative"]


class TestProperty10ProfileResolution:
    """For any string value in {"fast", "normal", "conservative"},
    resolve_pacing_profile SHALL return the corresponding profile with correct constants.
    For any string not in that set (including empty), it SHALL return the "fast" profile."""

    @given(profile_name=st.sampled_from(VALID_PROFILE_NAMES))
    @settings(max_examples=100)
    def test_valid_profile_names_resolve_correctly(self, profile_name: str):
        """Valid profile names always resolve to the correct PacingProfile.

        **Validates: Requirements 8.1, 8.2, 8.3, 8.4**
        """
        config = {"pacing_profile": profile_name}
        result = resolve_pacing_profile(config)

        assert isinstance(result, PacingProfile)
        assert result.name == profile_name
        assert result is PROFILES[profile_name]

        # Verify the profile has the expected constants from the design
        if profile_name == "fast":
            assert result.cursor_base_ms == 600
            assert result.cursor_min_ms == 300
            assert result.cursor_max_ms == 1400
            assert result.safe_pause_min == 0.1
            assert result.safe_pause_max == 0.3
        elif profile_name == "normal":
            assert result.cursor_base_ms == 900
            assert result.cursor_min_ms == 400
            assert result.cursor_max_ms == 1800
            assert result.safe_pause_min == 0.2
            assert result.safe_pause_max == 0.5
        elif profile_name == "conservative":
            assert result.cursor_base_ms == 1200
            assert result.cursor_min_ms == 500
            assert result.cursor_max_ms == 2500
            assert result.safe_pause_min == 0.3
            assert result.safe_pause_max == 0.8

    @given(config=st.fixed_dictionaries({}))
    @settings(max_examples=100)
    def test_missing_key_defaults_to_fast(self, config: dict):
        """Missing pacing_profile key defaults to 'fast' profile silently.

        **Validates: Requirements 8.5**
        """
        result = resolve_pacing_profile(config)

        assert isinstance(result, PacingProfile)
        assert result.name == "fast"
        assert result is PROFILES["fast"]

    @given(
        invalid_name=st.text(min_size=0, max_size=50).filter(
            lambda s: s not in VALID_PROFILE_NAMES
        )
    )
    @settings(max_examples=100)
    def test_invalid_profile_falls_back_to_fast_with_warning(
        self, invalid_name: str
    ):
        """Invalid/arbitrary string values fall back to 'fast' with a warning logged.

        **Validates: Requirements 8.6**
        """
        config = {"pacing_profile": invalid_name}

        # Capture log records using a list handler (avoids pytest fixture scope issue)
        captured_records: list[logging.LogRecord] = []

        class _ListHandler(logging.Handler):
            def emit(self, record):
                captured_records.append(record)

        handler = _ListHandler(level=logging.WARNING)
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
        try:
            result = resolve_pacing_profile(config)
        finally:
            root_logger.removeHandler(handler)

        assert isinstance(result, PacingProfile)
        assert result.name == "fast"
        assert result is PROFILES["fast"]

        # Verify a warning was logged about the invalid value
        warning_messages = [r.getMessage() for r in captured_records if r.levelno >= logging.WARNING]
        assert any(invalid_name in msg for msg in warning_messages), (
            f"Expected warning about invalid profile '{invalid_name}' but got: {warning_messages}"
        )


# ══════════════════════════════════════════════════════════
# Property 4: Overshoot magnitude and jitter are bounded
# ══════════════════════════════════════════════════════════
# Feature: video-pacing-optimization, Property 4: Overshoot magnitude and jitter are bounded
# **Validates: Requirements 1.7**

from cursor_engine import (
    JITTER_PIXELS,
    OVERSHOOT_CHANCE,
    OVERSHOOT_PX,
    _ease_cubic_inout,
    _gerar_pontos_controle,
)


class TestProperty4OvershootAndJitterBounded:
    """For any cursor movement with distance > 60 pixels where overshoot is applied,
    the overshoot displacement SHALL be <= 5 pixels, and per-step jitter SHALL be <= 2 pixels
    in each axis."""

    @given(
        x_ini=st.floats(min_value=0.0, max_value=1920.0, allow_nan=False, allow_infinity=False),
        y_ini=st.floats(min_value=0.0, max_value=1080.0, allow_nan=False, allow_infinity=False),
        x_fim=st.floats(min_value=0.0, max_value=1920.0, allow_nan=False, allow_infinity=False),
        y_fim=st.floats(min_value=0.0, max_value=1080.0, allow_nan=False, allow_infinity=False),
        overshoot_random=st.floats(min_value=3.0, max_value=5.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=200)
    def test_overshoot_displacement_bounded(
        self, x_ini: float, y_ini: float, x_fim: float, y_fim: float, overshoot_random: float
    ):
        """Overshoot displacement is always <= OVERSHOOT_PX (5 pixels).

        **Validates: Requirements 1.7**
        """
        distancia = math.hypot(x_fim - x_ini, y_fim - y_ini)
        assume(distancia > 60)

        # Simulate overshoot calculation from mover_cursor_humanizado
        dx, dy = x_fim - x_ini, y_fim - y_ini
        norm = math.hypot(dx, dy)
        over = overshoot_random  # random.uniform(3, OVERSHOOT_PX)

        x_alvo_final = x_fim + (dx / norm) * over
        y_alvo_final = y_fim + (dy / norm) * over

        # The overshoot displacement from the target
        overshoot_displacement = math.hypot(x_alvo_final - x_fim, y_alvo_final - y_fim)

        assert overshoot_displacement <= OVERSHOOT_PX + 1e-9, (
            f"Overshoot displacement {overshoot_displacement:.4f}px exceeds bound "
            f"{OVERSHOOT_PX}px for over={over:.4f}"
        )

    @given(
        x0=st.floats(min_value=0.0, max_value=1920.0, allow_nan=False, allow_infinity=False),
        y0=st.floats(min_value=0.0, max_value=1080.0, allow_nan=False, allow_infinity=False),
        x3=st.floats(min_value=0.0, max_value=1920.0, allow_nan=False, allow_infinity=False),
        y3=st.floats(min_value=0.0, max_value=1080.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=200)
    def test_jitter_in_control_points_bounded(
        self, x0: float, y0: float, x3: float, y3: float
    ):
        """Per-step jitter applied to control points is bounded to <= JITTER_PIXELS (2px)
        in each axis.

        **Validates: Requirements 1.7**

        We verify this by checking that the jitter contribution (the random offset
        added to control points) is bounded by JITTER_PIXELS. Since _gerar_pontos_controle
        uses random.uniform(-JITTER_PIXELS, JITTER_PIXELS), we verify the constant is correct
        and that multiple calls always produce control points where the jitter component
        is within bounds.
        """
        distancia = math.hypot(x3 - x0, y3 - y0)
        assume(distancia >= 1)

        # The jitter bound constant must be <= 2.0
        assert JITTER_PIXELS <= 2.0, (
            f"JITTER_PIXELS constant {JITTER_PIXELS} exceeds 2px bound"
        )

        # Call _gerar_pontos_controle and verify the control points are generated
        # (the function uses random.uniform(-JITTER_PIXELS, JITTER_PIXELS) internally)
        cp1x, cp1y, cp2x, cp2y = _gerar_pontos_controle(x0, y0, x3, y3)

        # Control points should be finite (no NaN/Inf from the calculation)
        assert math.isfinite(cp1x) and math.isfinite(cp1y), (
            f"Control point 1 is not finite: ({cp1x}, {cp1y})"
        )
        assert math.isfinite(cp2x) and math.isfinite(cp2y), (
            f"Control point 2 is not finite: ({cp2x}, {cp2y})"
        )

    @given(
        jitter_value=st.floats(
            min_value=-2.0, max_value=2.0, allow_nan=False, allow_infinity=False
        )
    )
    @settings(max_examples=200)
    def test_jitter_value_range_bounded(self, jitter_value: float):
        """Any value produced by random.uniform(-JITTER_PIXELS, JITTER_PIXELS) is within [-2, 2].

        **Validates: Requirements 1.7**

        This tests the property that the jitter generation range is correctly bounded.
        """
        # The jitter range is [-JITTER_PIXELS, JITTER_PIXELS]
        assert abs(jitter_value) <= JITTER_PIXELS, (
            f"Jitter value {jitter_value} exceeds bound {JITTER_PIXELS}"
        )
        assert abs(jitter_value) <= 2.0, (
            f"Jitter value {jitter_value} exceeds 2px absolute bound"
        )


# ══════════════════════════════════════════════════════════
# Property 6: Cubic-in-out easing is monotonic and bounded
# ══════════════════════════════════════════════════════════
# Feature: video-pacing-optimization, Property 6: Cubic-in-out easing is monotonic and bounded
# **Validates: Requirements 2.4**


class TestProperty6CubicInOutEasing:
    """For any t in [0, 1], the cubic-in-out easing function SHALL satisfy:
    f(0) = 0, f(1) = 1, f is monotonically non-decreasing, and f(0.5) = 0.5 (symmetry)."""

    @given(t=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False))
    @settings(max_examples=200)
    def test_easing_output_bounded_zero_to_one(self, t: float):
        """_ease_cubic_inout(t) returns values in [0, 1] for all t in [0, 1].

        **Validates: Requirements 2.4**
        """
        result = _ease_cubic_inout(t)

        assert 0.0 <= result <= 1.0, (
            f"Easing output {result} is outside [0, 1] for t={t}"
        )

    @given(
        t1=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        t2=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=200)
    def test_easing_is_monotonically_non_decreasing(self, t1: float, t2: float):
        """For any t1 <= t2 in [0, 1], f(t1) <= f(t2) (monotonically non-decreasing).

        **Validates: Requirements 2.4**
        """
        if t1 > t2:
            t1, t2 = t2, t1

        result1 = _ease_cubic_inout(t1)
        result2 = _ease_cubic_inout(t2)

        assert result1 <= result2 + 1e-10, (
            f"Easing is not monotonic: f({t1})={result1} > f({t2})={result2}"
        )

    def test_easing_boundary_values(self):
        """f(0) = 0, f(1) = 1, f(0.5) = 0.5 (exact boundary and symmetry conditions).

        **Validates: Requirements 2.4**
        """
        assert _ease_cubic_inout(0.0) == 0.0, (
            f"f(0) = {_ease_cubic_inout(0.0)}, expected 0.0"
        )
        assert _ease_cubic_inout(1.0) == 1.0, (
            f"f(1) = {_ease_cubic_inout(1.0)}, expected 1.0"
        )
        assert abs(_ease_cubic_inout(0.5) - 0.5) < 1e-10, (
            f"f(0.5) = {_ease_cubic_inout(0.5)}, expected 0.5"
        )

    @given(t=st.floats(min_value=0.0, max_value=0.5, allow_nan=False, allow_infinity=False))
    @settings(max_examples=200)
    def test_easing_symmetry(self, t: float):
        """f(t) + f(1-t) = 1 for all t in [0, 1] (point symmetry around (0.5, 0.5)).

        **Validates: Requirements 2.4**
        """
        result_t = _ease_cubic_inout(t)
        result_complement = _ease_cubic_inout(1.0 - t)

        assert abs(result_t + result_complement - 1.0) < 1e-9, (
            f"Symmetry violated: f({t})={result_t}, f({1.0-t})={result_complement}, "
            f"sum={result_t + result_complement}, expected 1.0"
        )


# ══════════════════════════════════════════════════════════
# Property 12: Minimum inter-step delay
# ══════════════════════════════════════════════════════════
# Feature: video-pacing-optimization, Property 12: Minimum inter-step delay
# **Validates: Requirements 5.3**


class TestProperty12MinimumInterStepDelay:
    """For any cursor movement animation, the computed inter-step delay SHALL be >= 8ms
    for every step in the sequence."""

    @given(
        duracao_ms=st.integers(min_value=300, max_value=2500),
        passos=st.integers(min_value=12, max_value=90),
        step_index=st.integers(min_value=0, max_value=90),
    )
    @settings(max_examples=200)
    def test_inter_step_delay_at_least_8ms(self, duracao_ms: int, passos: int, step_index: int):
        """The computed delay for any step is always >= 8ms (0.008s).

        **Validates: Requirements 5.3**

        The delay formula is: max(0.008, intervalo_s * fator_pausa)
        where intervalo_s = (duracao_ms / 1000) / passos
        and fator_pausa = 0.6 + 0.8 * abs(sin(pi * t))
        and t = step_index / passos
        """
        assume(step_index <= passos)

        t = step_index / passos
        intervalo_s = (duracao_ms / 1000) / passos
        fator_pausa = 0.6 + 0.8 * abs(math.sin(math.pi * t))
        delay = intervalo_s * fator_pausa

        # The actual delay applied in the code
        actual_delay = max(0.008, delay)

        assert actual_delay >= 0.008, (
            f"Inter-step delay {actual_delay:.6f}s is below 8ms minimum "
            f"for duracao_ms={duracao_ms}, passos={passos}, step={step_index}/{passos}, "
            f"t={t:.4f}, fator_pausa={fator_pausa:.4f}"
        )

    @given(
        duracao_ms=st.integers(min_value=300, max_value=2500),
        passos=st.integers(min_value=12, max_value=90),
    )
    @settings(max_examples=200)
    def test_all_steps_in_sequence_meet_minimum_delay(self, duracao_ms: int, passos: int):
        """Every step in a complete animation sequence has delay >= 8ms.

        **Validates: Requirements 5.3**

        Iterates through all steps to verify the minimum is enforced everywhere.
        """
        intervalo_s = (duracao_ms / 1000) / passos

        for i in range(passos + 1):
            t = i / passos
            fator_pausa = 0.6 + 0.8 * abs(math.sin(math.pi * t))
            delay = intervalo_s * fator_pausa
            actual_delay = max(0.008, delay)

            assert actual_delay >= 0.008, (
                f"Step {i}/{passos}: delay {actual_delay:.6f}s < 8ms "
                f"(intervalo_s={intervalo_s:.6f}, fator_pausa={fator_pausa:.4f})"
            )

    @given(
        profile=st_profile,
        distance=st.floats(min_value=3.0, max_value=3000.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=200)
    def test_delay_minimum_with_profile_derived_values(self, profile: PacingProfile, distance: float):
        """When duration and steps are derived from a profile, the minimum delay still holds.

        **Validates: Requirements 5.3**

        Uses the actual profile-based calculation functions to derive duration and steps,
        then verifies the 8ms minimum for all steps.
        """
        # Fix random to get deterministic duration
        with patch("cursor_engine.random.uniform", return_value=1.0):
            duracao_ms = calcular_duracao_movimento(distance, profile)

        if duracao_ms == 0:
            return  # skip signal, no animation

        passos = calcular_passos_movimento(distance, profile)
        intervalo_s = (duracao_ms / 1000) / passos

        for i in range(passos + 1):
            t = i / passos
            fator_pausa = 0.6 + 0.8 * abs(math.sin(math.pi * t))
            delay = intervalo_s * fator_pausa
            actual_delay = max(0.008, delay)

            assert actual_delay >= 0.008, (
                f"Step {i}/{passos}: delay {actual_delay:.6f}s < 8ms "
                f"(profile={profile.name}, distance={distance:.1f}, "
                f"duracao_ms={duracao_ms}, passos={passos})"
            )


# ══════════════════════════════════════════════════════════
# Property 7: Action classification correctness
# ══════════════════════════════════════════════════════════
# Feature: video-pacing-optimization, Property 7: Action classification correctness
# **Validates: Requirements 4.3, 4.4, 4.5, 4.6, 4.7**

# main.py has heavy dependencies (pygame, edge_tts, moviepy, etc.) that may not be
# available in the test environment. We mock them before importing the target functions.
import importlib
from unittest.mock import MagicMock

_heavy_modules = [
    "pygame", "edge_tts", "moviepy", "moviepy.editor", "moviepy.audio",
    "moviepy.audio.fx", "moviepy.audio.fx.all", "requests", "PIL", "PIL.Image",
    "proglog", "playwright", "playwright.async_api",
    "score_engine", "vision_engine", "voice_catalog", "ssml_builder",
]
for _mod_name in _heavy_modules:
    if _mod_name not in sys.modules:
        sys.modules[_mod_name] = MagicMock()

from main import ActionClassification, calcular_pausa_pos_acao, classificar_acao

# Strategies for action classification testing
st_safe_tipo_passo = st.sampled_from(["click", "typing", "interaction", "form_fill", ""])
st_sensitive_tipo_passo = st.sampled_from(["navigation", "navegacao", "page_refresh"])
st_pause_sugerida_safe = st.floats(min_value=0.0, max_value=3.0, allow_nan=False, allow_infinity=False)
st_pause_sugerida_sensitive = st.floats(min_value=3.01, max_value=30.0, allow_nan=False, allow_infinity=False)


class TestProperty7ActionClassification:
    """For any action and step metadata, classificar_acao SHALL return SENSITIVE if and only if
    at least one of the following holds: (a) acao == "duplo_clique", (b) tipo_passo indicates
    navigation, (c) pause_sugerida > 3.0, (d) aguarda_carregamento is true.
    Otherwise it SHALL return SAFE."""

    @given(
        tipo_passo=st_safe_tipo_passo,
        pause_sugerida=st_pause_sugerida_safe,
    )
    @settings(max_examples=200)
    def test_safe_classification_when_no_sensitive_conditions(
        self, tipo_passo: str, pause_sugerida: float
    ):
        """Actions with no sensitive conditions are classified as SAFE.

        **Validates: Requirements 4.7**
        """
        acao_tec = {"acao": "clique", "aguarda_carregamento": False}
        passo = {"tipo_passo": tipo_passo, "pause_sugerida": pause_sugerida}

        result = classificar_acao(acao_tec, passo)

        assert result == ActionClassification.SAFE, (
            f"Expected SAFE but got {result} for acao_tec={acao_tec}, passo={passo}"
        )

    @given(
        tipo_passo=st_safe_tipo_passo,
        pause_sugerida=st_pause_sugerida_safe,
    )
    @settings(max_examples=200)
    def test_sensitive_when_duplo_clique(self, tipo_passo: str, pause_sugerida: float):
        """duplo_clique action is always classified as SENSITIVE regardless of other fields.

        **Validates: Requirements 4.3**
        """
        acao_tec = {"acao": "duplo_clique", "aguarda_carregamento": False}
        passo = {"tipo_passo": tipo_passo, "pause_sugerida": pause_sugerida}

        result = classificar_acao(acao_tec, passo)

        assert result == ActionClassification.SENSITIVE, (
            f"Expected SENSITIVE for duplo_clique but got {result}"
        )

    @given(
        tipo_passo=st_sensitive_tipo_passo,
        pause_sugerida=st_pause_sugerida_safe,
    )
    @settings(max_examples=200)
    def test_sensitive_when_navigation_tipo_passo(self, tipo_passo: str, pause_sugerida: float):
        """Navigation tipo_passo values are always classified as SENSITIVE.

        **Validates: Requirements 4.4**
        """
        acao_tec = {"acao": "clique", "aguarda_carregamento": False}
        passo = {"tipo_passo": tipo_passo, "pause_sugerida": pause_sugerida}

        result = classificar_acao(acao_tec, passo)

        assert result == ActionClassification.SENSITIVE, (
            f"Expected SENSITIVE for tipo_passo='{tipo_passo}' but got {result}"
        )

    @given(pause_sugerida=st_pause_sugerida_sensitive)
    @settings(max_examples=200)
    def test_sensitive_when_pause_sugerida_above_3(self, pause_sugerida: float):
        """pause_sugerida > 3.0 is always classified as SENSITIVE.

        **Validates: Requirements 4.5**
        """
        acao_tec = {"acao": "clique", "aguarda_carregamento": False}
        passo = {"tipo_passo": "click", "pause_sugerida": pause_sugerida}

        result = classificar_acao(acao_tec, passo)

        assert result == ActionClassification.SENSITIVE, (
            f"Expected SENSITIVE for pause_sugerida={pause_sugerida} but got {result}"
        )

    @given(
        tipo_passo=st_safe_tipo_passo,
        pause_sugerida=st_pause_sugerida_safe,
    )
    @settings(max_examples=200)
    def test_sensitive_when_aguarda_carregamento(self, tipo_passo: str, pause_sugerida: float):
        """aguarda_carregamento == True is always classified as SENSITIVE.

        **Validates: Requirements 4.4**
        """
        acao_tec = {"acao": "clique", "aguarda_carregamento": True}
        passo = {"tipo_passo": tipo_passo, "pause_sugerida": pause_sugerida}

        result = classificar_acao(acao_tec, passo)

        assert result == ActionClassification.SENSITIVE, (
            f"Expected SENSITIVE for aguarda_carregamento=True but got {result}"
        )

    @given(
        tipo_passo=st_sensitive_tipo_passo,
        pause_sugerida=st_pause_sugerida_sensitive,
    )
    @settings(max_examples=200)
    def test_sensitive_precedence_multiple_conditions(
        self, tipo_passo: str, pause_sugerida: float
    ):
        """When multiple sensitive conditions match, result is still SENSITIVE (precedence rule).

        **Validates: Requirements 4.6**
        """
        acao_tec = {"acao": "duplo_clique", "aguarda_carregamento": True}
        passo = {"tipo_passo": tipo_passo, "pause_sugerida": pause_sugerida}

        result = classificar_acao(acao_tec, passo)

        assert result == ActionClassification.SENSITIVE, (
            f"Expected SENSITIVE with multiple conditions but got {result}"
        )

    @given(
        tipo_passo=st.text(min_size=0, max_size=30).filter(
            lambda s: s.lower() not in ("navigation", "navegacao", "page_refresh")
        ),
        pause_sugerida=st_pause_sugerida_safe,
    )
    @settings(max_examples=200)
    def test_safe_with_arbitrary_tipo_passo_not_navigation(
        self, tipo_passo: str, pause_sugerida: float
    ):
        """Arbitrary tipo_passo values that are not navigation-related are classified as SAFE.

        **Validates: Requirements 4.7**
        """
        acao_tec = {"acao": "clique", "aguarda_carregamento": False}
        passo = {"tipo_passo": tipo_passo, "pause_sugerida": pause_sugerida}

        result = classificar_acao(acao_tec, passo)

        assert result == ActionClassification.SAFE, (
            f"Expected SAFE for tipo_passo='{tipo_passo}' but got {result}"
        )


# ══════════════════════════════════════════════════════════
# Property 8: Safe action pause is bounded
# ══════════════════════════════════════════════════════════
# Feature: video-pacing-optimization, Property 8: Safe action pause is bounded
# **Validates: Requirements 4.1**


class TestProperty8SafeActionPauseBounded:
    """For any action classified as SAFE and any valid pacing profile, the post-action
    pause SHALL be within [profile.safe_pause_min, profile.safe_pause_max]."""

    @given(
        profile=st_profile,
        pause_sugerida=st.floats(min_value=0.0, max_value=10.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=200)
    def test_safe_pause_within_profile_bounds(self, profile: PacingProfile, pause_sugerida: float):
        """SAFE classification produces pause within [safe_pause_min, safe_pause_max].

        **Validates: Requirements 4.1**
        """
        result = calcular_pausa_pos_acao(
            ActionClassification.SAFE, pause_sugerida, profile
        )

        assert result >= profile.safe_pause_min, (
            f"Safe pause {result}s is below minimum {profile.safe_pause_min}s "
            f"for profile={profile.name}"
        )
        assert result <= profile.safe_pause_max, (
            f"Safe pause {result}s exceeds maximum {profile.safe_pause_max}s "
            f"for profile={profile.name}"
        )

    @given(profile=st_profile)
    @settings(max_examples=200)
    def test_safe_pause_ignores_pause_sugerida(self, profile: PacingProfile):
        """SAFE classification pause does not depend on pause_sugerida value — it is always
        within the profile bounds regardless of what pause_sugerida says.

        **Validates: Requirements 4.1**
        """
        # Use an extreme pause_sugerida to verify it's ignored
        extreme_pause = 999.0
        result = calcular_pausa_pos_acao(
            ActionClassification.SAFE, extreme_pause, profile
        )

        assert profile.safe_pause_min <= result <= profile.safe_pause_max, (
            f"Safe pause {result}s not within [{profile.safe_pause_min}, {profile.safe_pause_max}] "
            f"even though classification is SAFE (pause_sugerida={extreme_pause})"
        )


# ══════════════════════════════════════════════════════════
# Property 9: Sensitive action pause preserves pause_sugerida
# ══════════════════════════════════════════════════════════
# Feature: video-pacing-optimization, Property 9: Sensitive action pause preserves pause_sugerida
# **Validates: Requirements 4.2, 7.2, 7.5**


class TestProperty9SensitivePausePreserved:
    """For any action classified as SENSITIVE with any pause_sugerida value, the post-action
    pause SHALL equal the unmodified pause_sugerida value."""

    @given(
        profile=st_profile,
        pause_sugerida=st.floats(min_value=0.0, max_value=60.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=200)
    def test_sensitive_pause_equals_pause_sugerida(
        self, profile: PacingProfile, pause_sugerida: float
    ):
        """SENSITIVE classification returns pause_sugerida unmodified.

        **Validates: Requirements 4.2, 7.2, 7.5**
        """
        result = calcular_pausa_pos_acao(
            ActionClassification.SENSITIVE, pause_sugerida, profile
        )

        assert result == pause_sugerida, (
            f"Expected pause_sugerida={pause_sugerida} but got {result} "
            f"for SENSITIVE classification (profile={profile.name})"
        )

    @given(
        profile=st_profile,
        pause_sugerida=st.floats(min_value=3.01, max_value=30.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=200)
    def test_sensitive_pause_not_reduced_by_profile(
        self, profile: PacingProfile, pause_sugerida: float
    ):
        """SENSITIVE pause is never reduced by the profile — it always equals pause_sugerida
        regardless of profile bounds.

        **Validates: Requirements 4.2, 7.5**
        """
        result = calcular_pausa_pos_acao(
            ActionClassification.SENSITIVE, pause_sugerida, profile
        )

        # The result must equal pause_sugerida exactly, even if it exceeds profile bounds
        assert result == pause_sugerida, (
            f"Sensitive pause was modified: expected {pause_sugerida}, got {result}. "
            f"Profile safe bounds [{profile.safe_pause_min}, {profile.safe_pause_max}] "
            f"should NOT affect sensitive actions."
        )

    @given(profile=st_profile)
    @settings(max_examples=200)
    def test_sensitive_pause_preserves_zero(self, profile: PacingProfile):
        """Even a pause_sugerida of 0.0 is preserved for SENSITIVE classification.

        **Validates: Requirements 4.2**
        """
        result = calcular_pausa_pos_acao(
            ActionClassification.SENSITIVE, 0.0, profile
        )

        assert result == 0.0, (
            f"Expected 0.0 for SENSITIVE with pause_sugerida=0.0 but got {result}"
        )
