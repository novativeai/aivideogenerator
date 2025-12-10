"""
Tests for Pydantic model validation.
These tests recreate the models to avoid importing main.py which triggers Firebase initialization.
"""
import pytest
from pydantic import ValidationError, BaseModel, Field, validator, EmailStr
from typing import Literal


# Recreate the Pydantic models for isolated testing
# This avoids importing main.py which triggers Firebase initialization

class PaymentRequest(BaseModel):
    """Payment request model for testing."""
    userId: str
    customAmount: int = Field(..., ge=1, le=1000)

    @validator('customAmount')
    def validate_amount(cls, v):
        if v < 1 or v > 1000:
            raise ValueError('Amount must be between 1 and 1000')
        return v


class SubscriptionRequest(BaseModel):
    """Subscription request model for testing."""
    userId: str
    planId: Literal['creator', 'pro']

    @validator('planId')
    def validate_plan(cls, v):
        if v not in ['creator', 'pro']:
            raise ValueError('Invalid plan ID')
        return v


class AdminUserCreateRequest(BaseModel):
    """Admin user creation model for testing."""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class GenerationRequest(BaseModel):
    """Generation request model for testing."""
    prompt: str = Field(..., min_length=1, max_length=5000)
    aspect_ratio: Literal['16:9', '9:16', '1:1'] = '16:9'
    duration: int = Field(default=5, ge=1, le=10)
    model: Literal['video', 'image'] = 'video'

    @validator('prompt')
    def validate_prompt(cls, v):
        if not v.strip():
            raise ValueError('Prompt cannot be empty')
        return v


class TestPaymentRequestValidation:
    """Tests for PaymentRequest model validation."""

    def test_valid_payment_request(self):
        """Test that valid payment requests pass validation."""
        request = PaymentRequest(
            userId='user_123',
            customAmount=50
        )
        assert request.userId == 'user_123'
        assert request.customAmount == 50

    def test_payment_amount_minimum(self):
        """Test that amounts below minimum are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            PaymentRequest(
                userId='user_123',
                customAmount=0
            )

        errors = str(exc_info.value).lower()
        assert 'greater than or equal to 1' in errors or 'amount must be between' in errors

    def test_payment_amount_maximum(self):
        """Test that amounts above maximum are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            PaymentRequest(
                userId='user_123',
                customAmount=1001
            )

        errors = str(exc_info.value).lower()
        assert 'less than or equal to 1000' in errors or 'amount must be between' in errors

    def test_payment_amount_boundary_min(self):
        """Test minimum boundary value (1) is accepted."""
        request = PaymentRequest(
            userId='user_123',
            customAmount=1
        )
        assert request.customAmount == 1

    def test_payment_amount_boundary_max(self):
        """Test maximum boundary value (1000) is accepted."""
        request = PaymentRequest(
            userId='user_123',
            customAmount=1000
        )
        assert request.customAmount == 1000

    def test_payment_negative_amount(self):
        """Test that negative amounts are rejected."""
        with pytest.raises(ValidationError):
            PaymentRequest(
                userId='user_123',
                customAmount=-10
            )


class TestSubscriptionRequestValidation:
    """Tests for SubscriptionRequest model validation."""

    def test_valid_subscription_request(self):
        """Test that valid subscription requests pass validation."""
        request = SubscriptionRequest(
            userId='user_123',
            planId='creator'
        )
        assert request.userId == 'user_123'
        assert request.planId == 'creator'

    def test_subscription_valid_plan_ids(self):
        """Test that valid plan IDs are accepted."""
        valid_plans = ['creator', 'pro']
        for plan in valid_plans:
            request = SubscriptionRequest(
                userId='user_123',
                planId=plan
            )
            assert request.planId == plan

    def test_subscription_invalid_plan_id(self):
        """Test that invalid plan IDs are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            SubscriptionRequest(
                userId='user_123',
                planId='invalid_plan'
            )

        assert 'plan' in str(exc_info.value).lower()


class TestAdminUserCreateRequestValidation:
    """Tests for AdminUserCreateRequest model validation."""

    def test_valid_admin_user_request(self):
        """Test that valid admin user requests pass validation."""
        request = AdminUserCreateRequest(
            email='admin@example.com',
            password='SecurePass123!'
        )
        assert request.email == 'admin@example.com'

    def test_admin_user_invalid_email(self):
        """Test that invalid emails are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            AdminUserCreateRequest(
                email='not-an-email',
                password='SecurePass123!'
            )

        assert 'email' in str(exc_info.value).lower()

    def test_admin_user_short_password(self):
        """Test that short passwords are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            AdminUserCreateRequest(
                email='admin@example.com',
                password='Short1'
            )

        errors = str(exc_info.value).lower()
        assert 'password' in errors or 'characters' in errors or 'string' in errors

    def test_admin_user_long_password(self):
        """Test that excessively long passwords are rejected."""
        with pytest.raises(ValidationError):
            AdminUserCreateRequest(
                email='admin@example.com',
                password='a' * 129  # 129 characters, over 128 limit
            )


class TestGenerationRequestValidation:
    """Tests for video/image generation request validation."""

    def test_valid_generation_request(self):
        """Test that valid generation requests pass validation."""
        request = GenerationRequest(
            prompt='A beautiful sunset over the ocean',
            aspect_ratio='16:9',
            duration=5,
            model='video'
        )
        assert request.prompt == 'A beautiful sunset over the ocean'

    def test_generation_empty_prompt(self):
        """Test that empty prompts are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            GenerationRequest(
                prompt='',
                aspect_ratio='16:9',
                duration=5,
                model='video'
            )

        assert 'prompt' in str(exc_info.value).lower()

    def test_generation_whitespace_prompt(self):
        """Test that whitespace-only prompts are rejected."""
        with pytest.raises(ValidationError):
            GenerationRequest(
                prompt='   ',
                aspect_ratio='16:9',
                duration=5,
                model='video'
            )

    def test_generation_prompt_too_long(self):
        """Test that excessively long prompts are rejected."""
        with pytest.raises(ValidationError):
            GenerationRequest(
                prompt='a' * 5001,  # Over 5000 character limit
                aspect_ratio='16:9',
                duration=5,
                model='video'
            )

    def test_generation_valid_aspect_ratios(self):
        """Test that valid aspect ratios are accepted."""
        valid_ratios = ['16:9', '9:16', '1:1']
        for ratio in valid_ratios:
            request = GenerationRequest(
                prompt='Test prompt',
                aspect_ratio=ratio,
                duration=5,
                model='video'
            )
            assert request.aspect_ratio == ratio

    def test_generation_invalid_aspect_ratio(self):
        """Test that invalid aspect ratios are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            GenerationRequest(
                prompt='Test prompt',
                aspect_ratio='4:3',  # Not in allowed list
                duration=5,
                model='video'
            )

        assert 'aspect_ratio' in str(exc_info.value).lower()

    def test_generation_valid_duration(self):
        """Test that valid durations are accepted."""
        request = GenerationRequest(
            prompt='Test prompt',
            aspect_ratio='16:9',
            duration=5,
            model='video'
        )
        assert request.duration == 5

    def test_generation_duration_boundary_min(self):
        """Test minimum duration boundary (1) is accepted."""
        request = GenerationRequest(
            prompt='Test prompt',
            aspect_ratio='16:9',
            duration=1,
            model='video'
        )
        assert request.duration == 1

    def test_generation_duration_boundary_max(self):
        """Test maximum duration boundary (10) is accepted."""
        request = GenerationRequest(
            prompt='Test prompt',
            aspect_ratio='16:9',
            duration=10,
            model='video'
        )
        assert request.duration == 10

    def test_generation_invalid_duration(self):
        """Test that invalid durations are rejected."""
        with pytest.raises(ValidationError):
            GenerationRequest(
                prompt='Test prompt',
                aspect_ratio='16:9',
                duration=15,  # Over limit
                model='video'
            )

    def test_generation_valid_models(self):
        """Test that valid models are accepted."""
        valid_models = ['video', 'image']
        for model in valid_models:
            request = GenerationRequest(
                prompt='Test prompt',
                aspect_ratio='16:9',
                duration=5,
                model=model
            )
            assert request.model == model

    def test_generation_invalid_model(self):
        """Test that invalid models are rejected."""
        with pytest.raises(ValidationError):
            GenerationRequest(
                prompt='Test prompt',
                aspect_ratio='16:9',
                duration=5,
                model='invalid'
            )


class TestWebhookSignatureHelpers:
    """Tests for webhook signature generation and verification."""

    def test_hmac_signature_generation(self):
        """Test that HMAC signatures can be generated correctly."""
        import hmac
        import hashlib

        signing_key = 'test_key_12345'
        body = b'{"event": "test"}'

        signature = hmac.new(
            signing_key.encode(),
            body,
            hashlib.sha256
        ).hexdigest()

        assert len(signature) == 64  # SHA256 produces 64 hex characters
        assert signature == hmac.new(
            signing_key.encode(),
            body,
            hashlib.sha256
        ).hexdigest()

    def test_timing_safe_compare(self):
        """Test that hmac.compare_digest works for secure comparison."""
        import hmac

        # Same strings should match
        assert hmac.compare_digest('abc123', 'abc123')

        # Different strings should not match
        assert not hmac.compare_digest('abc123', 'abc124')

        # Different lengths should not match
        assert not hmac.compare_digest('abc', 'abcd')
