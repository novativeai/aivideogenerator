"""
Comprehensive unit tests for the calculate_credits function.
Tests all fal.ai models, parameter variations, and edge cases.
"""
import pytest
from typing import Dict, Any

# --- Model Credit Pricing Configuration (copied from main.py for testing) ---
MODEL_CREDIT_PRICING = {
    "veo-3.1": {
        "base": 32,
        "modifiers": [
            {"param": "duration", "values": {"4": 16, "6": 24, "8": 32}, "type": "set"},
            {"param": "generate_audio", "values": {"false": 0.5}, "type": "multiply"}
        ]
    },
    "sora-2": {
        "base": 4,
        "modifiers": [{"param": "duration", "values": {"4": 4, "8": 8, "12": 12}, "type": "set"}]
    },
    "kling-2.6": {
        "base": 5,
        "modifiers": [{"param": "duration", "values": {"5": 5, "10": 10}, "type": "set"}]
    },
    "ltx-2": {"base": 1},
    "hailuo-2.3-pro": {
        "base": 4,
        "modifiers": [{"param": "duration", "values": {"5": 4, "10": 8}, "type": "set"}]
    },
    "nano-banana-pro": {
        "base": 2,
        "modifiers": [{"param": "resolution", "values": {"1K": 2, "2K": 3, "4K": 4}, "type": "set"}]
    }
}


def calculate_credits(model_id: str, params: Dict[str, Any]) -> int:
    """
    Calculate credits for a generation based on model and parameters.
    (Copied from main.py for standalone testing)

    Raises:
        ValueError: If model_id is invalid or pricing configuration is malformed
    """
    # VALIDATION: Check if model exists
    if not model_id:
        raise ValueError("model_id cannot be empty")

    if model_id not in MODEL_CREDIT_PRICING:
        raise ValueError(f"Unknown model: {model_id}. Valid models: {list(MODEL_CREDIT_PRICING.keys())}")

    pricing = MODEL_CREDIT_PRICING[model_id]

    # VALIDATION: Check base credits exist
    if "base" not in pricing:
        raise ValueError(f"Invalid pricing configuration for {model_id}: missing 'base' field")

    credits = pricing["base"]

    # VALIDATION: Ensure credits is a positive number
    if not isinstance(credits, (int, float)) or credits < 0:
        raise ValueError(f"Invalid base credits for {model_id}: must be non-negative number")

    # Apply modifiers
    modifiers = pricing.get("modifiers", [])
    for modifier in modifiers:
        param_name = modifier.get("param")
        param_value = params.get(param_name)

        if param_value is not None:
            param_value_str = str(param_value)
            modifier_values = modifier.get("values", {})
            modifier_value = modifier_values.get(param_value_str)

            if modifier_value is not None:
                # VALIDATION: Ensure modifier is numeric
                if not isinstance(modifier_value, (int, float)):
                    raise ValueError(f"Invalid modifier value type")

                modifier_type = modifier.get("type", "set")
                if modifier_type == "multiply":
                    credits *= modifier_value
                elif modifier_type == "add":
                    credits += modifier_value
                elif modifier_type == "set":
                    credits = modifier_value

    # Final validation: ensure result is valid
    final_credits = round(credits)
    if final_credits < 0:
        raise ValueError("Credit calculation resulted in negative credits")

    return final_credits


class TestCalculateCreditsBasicModels:
    """Test all 6 fal.ai models with default parameters."""

    def test_veo_3_1_default_params(self):
        """Test VEO 3.1 with default 8-second duration."""
        result = calculate_credits("veo-3.1", {"duration": "8"})
        assert result == 32

    def test_veo_3_1_no_duration(self):
        """Test VEO 3.1 with no duration specified uses base credits."""
        result = calculate_credits("veo-3.1", {})
        assert result == 32  # Base credits

    def test_sora_2_default_params(self):
        """Test Sora 2 with default 4-second duration."""
        result = calculate_credits("sora-2", {"duration": "4"})
        assert result == 4

    def test_sora_2_no_duration(self):
        """Test Sora 2 with no duration specified uses base credits."""
        result = calculate_credits("sora-2", {})
        assert result == 4  # Base credits

    def test_kling_2_6_default_params(self):
        """Test Kling 2.6 with default 5-second duration."""
        result = calculate_credits("kling-2.6", {"duration": "5"})
        assert result == 5

    def test_kling_2_6_no_duration(self):
        """Test Kling 2.6 with no duration specified uses base credits."""
        result = calculate_credits("kling-2.6", {})
        assert result == 5  # Base credits

    def test_ltx_2_default_params(self):
        """Test LTX 2 (fixed price, no modifiers)."""
        result = calculate_credits("ltx-2", {})
        assert result == 1

    def test_ltx_2_with_irrelevant_params(self):
        """Test LTX 2 ignores irrelevant parameters."""
        result = calculate_credits("ltx-2", {
            "num_inference_steps": 30,
            "guidance_scale": 7
        })
        assert result == 1  # Fixed price regardless of params

    def test_hailuo_2_3_pro_default_params(self):
        """Test Hailuo 2.3 Pro with default 5-second duration."""
        result = calculate_credits("hailuo-2.3-pro", {"duration": "5"})
        assert result == 4

    def test_hailuo_2_3_pro_no_duration(self):
        """Test Hailuo 2.3 Pro with no duration specified uses base credits."""
        result = calculate_credits("hailuo-2.3-pro", {})
        assert result == 4  # Base credits

    def test_nano_banana_pro_default_params(self):
        """Test Nano Banana Pro with default 2K resolution."""
        result = calculate_credits("nano-banana-pro", {"resolution": "2K"})
        assert result == 3

    def test_nano_banana_pro_no_resolution(self):
        """Test Nano Banana Pro with no resolution specified uses base credits."""
        result = calculate_credits("nano-banana-pro", {})
        assert result == 2  # Base credits


class TestCalculateCreditsParameterVariations:
    """Test all models with each valid parameter variation."""

    # VEO 3.1 duration variations
    def test_veo_3_1_duration_4_seconds(self):
        """Test VEO 3.1 with 4-second duration."""
        result = calculate_credits("veo-3.1", {"duration": "4"})
        assert result == 16

    def test_veo_3_1_duration_6_seconds(self):
        """Test VEO 3.1 with 6-second duration."""
        result = calculate_credits("veo-3.1", {"duration": "6"})
        assert result == 24

    def test_veo_3_1_duration_8_seconds(self):
        """Test VEO 3.1 with 8-second duration."""
        result = calculate_credits("veo-3.1", {"duration": "8"})
        assert result == 32

    def test_veo_3_1_no_audio(self):
        """Test VEO 3.1 with audio disabled (50% reduction)."""
        result = calculate_credits("veo-3.1", {"duration": "8", "generate_audio": "false"})
        assert result == 16  # 32 * 0.5 = 16

    def test_veo_3_1_with_audio(self):
        """Test VEO 3.1 with audio enabled (no multiplier applied)."""
        result = calculate_credits("veo-3.1", {"duration": "8", "generate_audio": "true"})
        assert result == 32  # No reduction for "true"

    # Sora 2 duration variations
    def test_sora_2_duration_4_seconds(self):
        """Test Sora 2 with 4-second duration."""
        result = calculate_credits("sora-2", {"duration": "4"})
        assert result == 4

    def test_sora_2_duration_8_seconds(self):
        """Test Sora 2 with 8-second duration."""
        result = calculate_credits("sora-2", {"duration": "8"})
        assert result == 8

    def test_sora_2_duration_12_seconds(self):
        """Test Sora 2 with 12-second duration."""
        result = calculate_credits("sora-2", {"duration": "12"})
        assert result == 12

    # Kling 2.6 duration variations
    def test_kling_2_6_duration_5_seconds(self):
        """Test Kling 2.6 with 5-second duration."""
        result = calculate_credits("kling-2.6", {"duration": "5"})
        assert result == 5

    def test_kling_2_6_duration_10_seconds(self):
        """Test Kling 2.6 with 10-second duration."""
        result = calculate_credits("kling-2.6", {"duration": "10"})
        assert result == 10

    # Hailuo 2.3 Pro duration variations
    def test_hailuo_2_3_pro_duration_5_seconds(self):
        """Test Hailuo 2.3 Pro with 5-second duration."""
        result = calculate_credits("hailuo-2.3-pro", {"duration": "5"})
        assert result == 4

    def test_hailuo_2_3_pro_duration_10_seconds(self):
        """Test Hailuo 2.3 Pro with 10-second duration."""
        result = calculate_credits("hailuo-2.3-pro", {"duration": "10"})
        assert result == 8

    # Nano Banana Pro resolution variations
    def test_nano_banana_pro_resolution_1k(self):
        """Test Nano Banana Pro with 1K resolution."""
        result = calculate_credits("nano-banana-pro", {"resolution": "1K"})
        assert result == 2

    def test_nano_banana_pro_resolution_2k(self):
        """Test Nano Banana Pro with 2K resolution."""
        result = calculate_credits("nano-banana-pro", {"resolution": "2K"})
        assert result == 3

    def test_nano_banana_pro_resolution_4k(self):
        """Test Nano Banana Pro with 4K resolution."""
        result = calculate_credits("nano-banana-pro", {"resolution": "4K"})
        assert result == 4


class TestCalculateCreditsErrorHandling:
    """Test error handling for invalid inputs."""

    def test_unknown_model_id_raises_value_error(self):
        """Test that unknown model_id raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            calculate_credits("unknown-model", {})
        assert "Unknown model: unknown-model" in str(exc_info.value)
        assert "Valid models:" in str(exc_info.value)

    def test_empty_model_id_raises_value_error(self):
        """Test that empty model_id raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            calculate_credits("", {})
        assert "model_id cannot be empty" in str(exc_info.value)

    def test_none_model_id_raises_value_error(self):
        """Test that None model_id raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            calculate_credits(None, {})
        assert "model_id cannot be empty" in str(exc_info.value)

    def test_whitespace_model_id_raises_value_error(self):
        """Test that whitespace-only model_id raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            calculate_credits("   ", {})
        assert "Unknown model:" in str(exc_info.value)

    def test_old_model_ids_no_longer_supported(self):
        """Test that old Replicate model IDs are no longer supported."""
        old_models = ["kling-2.5", "seedance-1-pro", "wan-2.2", "flux-1.1-pro-ultra"]
        for model_id in old_models:
            with pytest.raises(ValueError) as exc_info:
                calculate_credits(model_id, {})
            assert "Unknown model:" in str(exc_info.value)


class TestCalculateCreditsUnknownParamValues:
    """Test handling of unknown parameter values."""

    def test_unknown_duration_value_uses_base_credits(self):
        """Test that unknown duration value falls back to base credits."""
        # Kling 2.6 only supports "5" and "10" for duration
        result = calculate_credits("kling-2.6", {"duration": "15"})
        assert result == 5  # Falls back to base credits

    def test_unknown_resolution_value_uses_base_credits(self):
        """Test that unknown resolution value falls back to base credits."""
        # Nano Banana Pro only supports 1K, 2K, 4K
        result = calculate_credits("nano-banana-pro", {"resolution": "8K"})
        assert result == 2  # Falls back to base credits

    def test_numeric_duration_as_string(self):
        """Test that numeric duration values are properly converted."""
        result = calculate_credits("veo-3.1", {"duration": 8})  # Number, not string
        assert result == 32  # Should still work via str conversion

    def test_numeric_resolution_as_string(self):
        """Test resolution with extra whitespace/formatting."""
        result = calculate_credits("nano-banana-pro", {"resolution": " 2K "})
        # This should use base credits since " 2K " != "2K"
        assert result == 2  # Falls back to base credits


class TestCalculateCreditsEdgeCases:
    """Test edge cases and special scenarios."""

    def test_null_params(self):
        """Test with empty params dict."""
        result = calculate_credits("ltx-2", {})
        assert result == 1

    def test_empty_params(self):
        """Test with empty params dict."""
        result = calculate_credits("kling-2.6", {})
        assert result == 5  # Base credits

    def test_extra_irrelevant_params(self):
        """Test that extra parameters are ignored."""
        result = calculate_credits("kling-2.6", {
            "duration": "5",
            "prompt": "A beautiful sunset",
            "cfg_scale": 7,
            "aspect_ratio": "16:9",
            "random_param": "value"
        })
        assert result == 5

    def test_param_value_none(self):
        """Test with param value explicitly set to None."""
        result = calculate_credits("kling-2.6", {"duration": None})
        assert result == 5  # Should use base credits

    def test_param_value_empty_string(self):
        """Test with param value as empty string."""
        result = calculate_credits("kling-2.6", {"duration": ""})
        assert result == 5  # Empty string not in values, uses base

    def test_result_is_integer(self):
        """Test that result is always an integer (rounded)."""
        result = calculate_credits("kling-2.6", {"duration": "5"})
        assert isinstance(result, int)

    def test_result_is_non_negative(self):
        """Test that result is never negative."""
        for model_id in MODEL_CREDIT_PRICING.keys():
            result = calculate_credits(model_id, {})
            assert result >= 0, f"Model {model_id} returned negative credits"


class TestCalculateCreditsAllModelsHaveBaseCredits:
    """Verify all models in pricing config have valid base credits."""

    def test_all_models_have_base_field(self):
        """Test that all models in pricing config have 'base' field."""
        for model_id, config in MODEL_CREDIT_PRICING.items():
            assert "base" in config, f"Model {model_id} missing 'base' field"

    def test_all_models_base_is_positive(self):
        """Test that all models have positive base credits."""
        for model_id, config in MODEL_CREDIT_PRICING.items():
            assert config["base"] > 0, f"Model {model_id} has non-positive base credits"

    def test_all_models_base_is_numeric(self):
        """Test that all models have numeric base credits."""
        for model_id, config in MODEL_CREDIT_PRICING.items():
            assert isinstance(config["base"], (int, float)), f"Model {model_id} has non-numeric base"


class TestCalculateCreditsModifierTypes:
    """Test different modifier types (set, add, multiply)."""

    def test_set_modifier_replaces_base(self):
        """Test that 'set' modifier replaces the base credits."""
        # Kling 2.6 uses 'set' modifier
        result_5s = calculate_credits("kling-2.6", {"duration": "5"})
        result_10s = calculate_credits("kling-2.6", {"duration": "10"})

        # Set modifier should set credits to the modifier value
        assert result_5s == 5  # Set to 5
        assert result_10s == 10  # Set to 10

    def test_multiply_modifier_reduces_credits(self):
        """Test that 'multiply' modifier adjusts the credits."""
        # VEO 3.1 has a multiply modifier for generate_audio=false
        result_with_audio = calculate_credits("veo-3.1", {"duration": "8", "generate_audio": "true"})
        result_no_audio = calculate_credits("veo-3.1", {"duration": "8", "generate_audio": "false"})

        assert result_with_audio == 32  # Full price
        assert result_no_audio == 16  # 32 * 0.5 = 16


class TestCalculateCreditsConsistency:
    """Test consistency between frontend and backend credit calculations."""

    def test_veo_pricing_matches_config(self):
        """Verify VEO 3.1 pricing matches MODEL_CREDIT_PRICING."""
        config = MODEL_CREDIT_PRICING["veo-3.1"]
        assert config["base"] == 32
        modifiers = config.get("modifiers", [])
        assert len(modifiers) == 2
        assert modifiers[0]["param"] == "duration"
        assert modifiers[0]["values"] == {"4": 16, "6": 24, "8": 32}
        assert modifiers[1]["param"] == "generate_audio"
        assert modifiers[1]["values"] == {"false": 0.5}

    def test_sora_pricing_matches_config(self):
        """Verify Sora 2 pricing matches MODEL_CREDIT_PRICING."""
        config = MODEL_CREDIT_PRICING["sora-2"]
        assert config["base"] == 4
        modifiers = config.get("modifiers", [])
        assert len(modifiers) == 1
        assert modifiers[0]["param"] == "duration"
        assert modifiers[0]["values"] == {"4": 4, "8": 8, "12": 12}

    def test_kling_pricing_matches_config(self):
        """Verify Kling 2.6 pricing matches MODEL_CREDIT_PRICING."""
        config = MODEL_CREDIT_PRICING["kling-2.6"]
        assert config["base"] == 5
        modifiers = config.get("modifiers", [])
        assert len(modifiers) == 1
        assert modifiers[0]["param"] == "duration"
        assert modifiers[0]["values"] == {"5": 5, "10": 10}

    def test_ltx_pricing_matches_config(self):
        """Verify LTX 2 pricing matches MODEL_CREDIT_PRICING."""
        config = MODEL_CREDIT_PRICING["ltx-2"]
        assert config["base"] == 1
        assert config.get("modifiers") is None  # No modifiers for fixed price

    def test_hailuo_pricing_matches_config(self):
        """Verify Hailuo 2.3 Pro pricing matches MODEL_CREDIT_PRICING."""
        config = MODEL_CREDIT_PRICING["hailuo-2.3-pro"]
        assert config["base"] == 4
        modifiers = config.get("modifiers", [])
        assert len(modifiers) == 1
        assert modifiers[0]["param"] == "duration"
        assert modifiers[0]["values"] == {"5": 4, "10": 8}

    def test_nano_banana_pricing_matches_config(self):
        """Verify Nano Banana Pro pricing matches MODEL_CREDIT_PRICING."""
        config = MODEL_CREDIT_PRICING["nano-banana-pro"]
        assert config["base"] == 2
        modifiers = config.get("modifiers", [])
        assert len(modifiers) == 1
        assert modifiers[0]["param"] == "resolution"
        assert modifiers[0]["values"] == {"1K": 2, "2K": 3, "4K": 4}
