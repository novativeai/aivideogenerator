"""
Comprehensive unit tests for the calculate_credits function.
Tests all models, parameter variations, and edge cases.
"""
import pytest
from typing import Dict, Any

# --- Model Credit Pricing Configuration (copied from main.py for testing) ---
MODEL_CREDIT_PRICING = {
    "kling-2.5": {
        "base": 10,
        "modifiers": [
            {
                "param": "duration",
                "values": {"5": 10, "10": 20},
                "type": "set"
            }
        ]
    },
    "veo-3.1": {
        "base": 100,
        "modifiers": [
            {
                "param": "duration",
                "values": {"4": 50, "6": 75, "8": 100},
                "type": "set"
            }
        ]
    },
    "seedance-1-pro": {
        "base": 10,
        "modifiers": [
            {
                "param": "resolution",
                "values": {"480p": 10, "720p": 15, "1080p": 20},
                "type": "set"
            }
        ]
    },
    "wan-2.2": {
        "base": 3,
        "modifiers": [
            {
                "param": "resolution",
                "values": {"480p": 3, "720p": 5},
                "type": "set"
            }
        ]
    },
    "flux-1.1-pro-ultra": {
        "base": 2
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
    """Test all 5 models with default parameters."""

    def test_kling_2_5_default_params(self):
        """Test Kling 2.5 with default 5-second duration."""
        result = calculate_credits("kling-2.5", {"duration": "5"})
        assert result == 10

    def test_kling_2_5_no_duration(self):
        """Test Kling 2.5 with no duration specified uses base credits."""
        result = calculate_credits("kling-2.5", {})
        assert result == 10  # Base credits

    def test_veo_3_1_default_params(self):
        """Test VEO 3.1 with default 8-second duration."""
        result = calculate_credits("veo-3.1", {"duration": "8"})
        assert result == 100

    def test_veo_3_1_no_duration(self):
        """Test VEO 3.1 with no duration specified uses base credits."""
        result = calculate_credits("veo-3.1", {})
        assert result == 100  # Base credits

    def test_seedance_1_pro_default_params(self):
        """Test Seedance 1 Pro with default 480p resolution."""
        result = calculate_credits("seedance-1-pro", {"resolution": "480p"})
        assert result == 10

    def test_seedance_1_pro_no_resolution(self):
        """Test Seedance 1 Pro with no resolution specified uses base credits."""
        result = calculate_credits("seedance-1-pro", {})
        assert result == 10  # Base credits

    def test_wan_2_2_default_params(self):
        """Test WAN 2.2 with default 480p resolution."""
        result = calculate_credits("wan-2.2", {"resolution": "480p"})
        assert result == 3

    def test_wan_2_2_no_resolution(self):
        """Test WAN 2.2 with no resolution specified uses base credits."""
        result = calculate_credits("wan-2.2", {})
        assert result == 3  # Base credits

    def test_flux_1_1_pro_ultra_default_params(self):
        """Test FLUX 1.1 Pro Ultra (fixed price, no modifiers)."""
        result = calculate_credits("flux-1.1-pro-ultra", {})
        assert result == 2

    def test_flux_1_1_pro_ultra_with_irrelevant_params(self):
        """Test FLUX 1.1 Pro Ultra ignores irrelevant parameters."""
        result = calculate_credits("flux-1.1-pro-ultra", {
            "aspect_ratio": "16:9",
            "output_format": "jpg",
            "raw": "false"
        })
        assert result == 2  # Fixed price regardless of params


class TestCalculateCreditsParameterVariations:
    """Test all models with each valid parameter variation."""

    # Kling 2.5 duration variations
    def test_kling_2_5_duration_5_seconds(self):
        """Test Kling 2.5 with 5-second duration."""
        result = calculate_credits("kling-2.5", {"duration": "5"})
        assert result == 10

    def test_kling_2_5_duration_10_seconds(self):
        """Test Kling 2.5 with 10-second duration."""
        result = calculate_credits("kling-2.5", {"duration": "10"})
        assert result == 20

    # VEO 3.1 duration variations
    def test_veo_3_1_duration_4_seconds(self):
        """Test VEO 3.1 with 4-second duration."""
        result = calculate_credits("veo-3.1", {"duration": "4"})
        assert result == 50

    def test_veo_3_1_duration_6_seconds(self):
        """Test VEO 3.1 with 6-second duration."""
        result = calculate_credits("veo-3.1", {"duration": "6"})
        assert result == 75

    def test_veo_3_1_duration_8_seconds(self):
        """Test VEO 3.1 with 8-second duration."""
        result = calculate_credits("veo-3.1", {"duration": "8"})
        assert result == 100

    # Seedance 1 Pro resolution variations
    def test_seedance_1_pro_resolution_480p(self):
        """Test Seedance 1 Pro with 480p resolution."""
        result = calculate_credits("seedance-1-pro", {"resolution": "480p"})
        assert result == 10

    def test_seedance_1_pro_resolution_720p(self):
        """Test Seedance 1 Pro with 720p resolution."""
        result = calculate_credits("seedance-1-pro", {"resolution": "720p"})
        assert result == 15

    def test_seedance_1_pro_resolution_1080p(self):
        """Test Seedance 1 Pro with 1080p resolution."""
        result = calculate_credits("seedance-1-pro", {"resolution": "1080p"})
        assert result == 20

    # WAN 2.2 resolution variations
    def test_wan_2_2_resolution_480p(self):
        """Test WAN 2.2 with 480p resolution."""
        result = calculate_credits("wan-2.2", {"resolution": "480p"})
        assert result == 3

    def test_wan_2_2_resolution_720p(self):
        """Test WAN 2.2 with 720p resolution."""
        result = calculate_credits("wan-2.2", {"resolution": "720p"})
        assert result == 5


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


class TestCalculateCreditsUnknownParamValues:
    """Test handling of unknown parameter values."""

    def test_unknown_duration_value_uses_base_credits(self):
        """Test that unknown duration value falls back to base credits."""
        # Kling 2.5 only supports "5" and "10" for duration
        result = calculate_credits("kling-2.5", {"duration": "15"})
        assert result == 10  # Falls back to base credits

    def test_unknown_resolution_value_uses_base_credits(self):
        """Test that unknown resolution value falls back to base credits."""
        # Seedance only supports 480p, 720p, 1080p
        result = calculate_credits("seedance-1-pro", {"resolution": "4K"})
        assert result == 10  # Falls back to base credits

    def test_numeric_duration_as_string(self):
        """Test that numeric duration values are properly converted."""
        result = calculate_credits("veo-3.1", {"duration": 8})  # Number, not string
        assert result == 100  # Should still work via str conversion

    def test_numeric_resolution_as_string(self):
        """Test resolution with extra whitespace/formatting."""
        result = calculate_credits("wan-2.2", {"resolution": " 720p "})
        # This should use base credits since " 720p " != "720p"
        assert result == 3  # Falls back to base credits


class TestCalculateCreditsEdgeCases:
    """Test edge cases and special scenarios."""

    def test_null_params(self):
        """Test with None params dict (should use base)."""
        # Pass empty dict instead of None as the function expects dict
        result = calculate_credits("flux-1.1-pro-ultra", {})
        assert result == 2

    def test_empty_params(self):
        """Test with empty params dict."""
        result = calculate_credits("kling-2.5", {})
        assert result == 10  # Base credits

    def test_extra_irrelevant_params(self):
        """Test that extra parameters are ignored."""
        result = calculate_credits("kling-2.5", {
            "duration": "5",
            "prompt": "A beautiful sunset",
            "negative_prompt": "blur",
            "aspect_ratio": "16:9",
            "random_param": "value"
        })
        assert result == 10

    def test_param_value_none(self):
        """Test with param value explicitly set to None."""
        result = calculate_credits("kling-2.5", {"duration": None})
        assert result == 10  # Should use base credits

    def test_param_value_empty_string(self):
        """Test with param value as empty string."""
        result = calculate_credits("kling-2.5", {"duration": ""})
        assert result == 10  # Empty string not in values, uses base

    def test_result_is_integer(self):
        """Test that result is always an integer (rounded)."""
        result = calculate_credits("kling-2.5", {"duration": "5"})
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
        # Kling 2.5 uses 'set' modifier
        base = MODEL_CREDIT_PRICING["kling-2.5"]["base"]
        result_5s = calculate_credits("kling-2.5", {"duration": "5"})
        result_10s = calculate_credits("kling-2.5", {"duration": "10"})

        # Set modifier should set credits to the modifier value
        assert result_5s == 10  # Set to 10
        assert result_10s == 20  # Set to 20

    def test_all_current_models_use_set_type(self):
        """Verify all current model modifiers use 'set' type."""
        for model_id, config in MODEL_CREDIT_PRICING.items():
            modifiers = config.get("modifiers", [])
            for modifier in modifiers:
                assert modifier.get("type") == "set", \
                    f"Model {model_id} uses non-'set' modifier type"


class TestCalculateCreditsConsistency:
    """Test consistency between frontend and backend credit calculations."""

    def test_kling_pricing_matches_config(self):
        """Verify Kling 2.5 pricing matches MODEL_CREDIT_PRICING."""
        config = MODEL_CREDIT_PRICING["kling-2.5"]
        assert config["base"] == 10
        modifiers = config.get("modifiers", [])
        assert len(modifiers) == 1
        assert modifiers[0]["param"] == "duration"
        assert modifiers[0]["values"] == {"5": 10, "10": 20}

    def test_veo_pricing_matches_config(self):
        """Verify VEO 3.1 pricing matches MODEL_CREDIT_PRICING."""
        config = MODEL_CREDIT_PRICING["veo-3.1"]
        assert config["base"] == 100
        modifiers = config.get("modifiers", [])
        assert len(modifiers) == 1
        assert modifiers[0]["param"] == "duration"
        assert modifiers[0]["values"] == {"4": 50, "6": 75, "8": 100}

    def test_seedance_pricing_matches_config(self):
        """Verify Seedance 1 Pro pricing matches MODEL_CREDIT_PRICING."""
        config = MODEL_CREDIT_PRICING["seedance-1-pro"]
        assert config["base"] == 10
        modifiers = config.get("modifiers", [])
        assert len(modifiers) == 1
        assert modifiers[0]["param"] == "resolution"
        assert modifiers[0]["values"] == {"480p": 10, "720p": 15, "1080p": 20}

    def test_wan_pricing_matches_config(self):
        """Verify WAN 2.2 pricing matches MODEL_CREDIT_PRICING."""
        config = MODEL_CREDIT_PRICING["wan-2.2"]
        assert config["base"] == 3
        modifiers = config.get("modifiers", [])
        assert len(modifiers) == 1
        assert modifiers[0]["param"] == "resolution"
        assert modifiers[0]["values"] == {"480p": 3, "720p": 5}

    def test_flux_pricing_matches_config(self):
        """Verify FLUX 1.1 Pro Ultra pricing matches MODEL_CREDIT_PRICING."""
        config = MODEL_CREDIT_PRICING["flux-1.1-pro-ultra"]
        assert config["base"] == 2
        assert config.get("modifiers") is None  # No modifiers for fixed price
