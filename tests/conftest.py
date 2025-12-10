"""
Test configuration and fixtures for backend tests.
"""
import pytest
import os
import sys
from unittest.mock import MagicMock, patch

# Set test environment variables before importing the app
os.environ['ENV'] = 'test'
os.environ['FIREBASE_SERVICE_ACCOUNT_BASE64'] = ''
os.environ['PAYTRUST_API_KEY'] = 'test_api_key'
os.environ['PAYTRUST_PROJECT_ID'] = 'test_project'
os.environ['PAYTRUST_SIGNING_KEY'] = 'test_signing_key_12345'
os.environ['REPLICATE_API_TOKEN'] = 'test_replicate_token'


@pytest.fixture
def mock_db():
    """Create a mock Firestore database client."""
    db = MagicMock()

    # Mock collection/document structure
    mock_doc = MagicMock()
    mock_doc.exists = True
    mock_doc.id = 'test_doc_id'
    mock_doc.to_dict.return_value = {
        'credits': 100,
        'email': 'test@example.com',
        'uid': 'test_user_id'
    }

    mock_doc_ref = MagicMock()
    mock_doc_ref.get.return_value = mock_doc
    mock_doc_ref.id = 'test_doc_id'

    mock_collection = MagicMock()
    mock_collection.document.return_value = mock_doc_ref
    mock_collection.add.return_value = (None, mock_doc_ref)

    db.collection.return_value = mock_collection

    return db


@pytest.fixture
def mock_user():
    """Create a mock authenticated user."""
    return {
        'uid': 'test_user_id',
        'email': 'test@example.com',
        'displayName': 'Test User'
    }


@pytest.fixture
def valid_webhook_signature():
    """Generate a valid webhook signature for testing."""
    import hmac
    import hashlib

    signing_key = os.environ.get('PAYTRUST_SIGNING_KEY', 'test_signing_key_12345')

    def generate(body: bytes) -> str:
        return hmac.new(
            signing_key.encode(),
            body,
            hashlib.sha256
        ).hexdigest()

    return generate


@pytest.fixture
def sample_webhook_payload():
    """Sample PayTrust webhook payload."""
    return {
        'event': 'payment.completed',
        'data': {
            'id': 'pay_test_123',
            'amount': 1000,
            'currency': 'EUR',
            'status': 'completed',
            'metadata': {
                'userId': 'test_user_id',
                'customAmount': 10
            }
        }
    }


@pytest.fixture
def sample_subscription_webhook_payload():
    """Sample subscription webhook payload."""
    return {
        'event': 'subscription.created',
        'data': {
            'id': 'sub_test_123',
            'customerId': 'cust_test_123',
            'priceId': 'price_test',
            'status': 'active',
            'metadata': {
                'userId': 'test_user_id'
            }
        }
    }
