# Wagtail AI 3.0 Integration Best Practices

**Research Date**: November 9, 2025
**Document Version**: 1.0.0
**Wagtail AI Version**: 3.0.0 (Released October 9, 2025)

## Executive Summary

This document provides comprehensive best practices for integrating Wagtail AI 3.0 into production environments. Based on official documentation, real-world implementations, and 2025 industry standards, this guide covers installation, configuration, security, cost optimization, and testing strategies.

**Key Findings**:
- Wagtail AI 3.0 is production-ready with multi-provider LLM support
- Supports OpenAI, Anthropic Claude, Mistral, and local models via `llm` library
- Breaking changes from 2.x require migration planning
- No dedicated GDPR documentation - privacy compliance depends on chosen AI provider
- Estimated cost: ~$0.003 per 1000-word content correction (GPT-3.5 Turbo)

---

## Table of Contents

1. [Requirements & Compatibility](#requirements--compatibility)
2. [Installation & Configuration](#installation--configuration)
3. [AI Provider Setup](#ai-provider-setup)
4. [Production Deployment](#production-deployment)
5. [Security & Privacy](#security--privacy)
6. [Cost Optimization](#cost-optimization)
7. [Error Handling & Fallbacks](#error-handling--fallbacks)
8. [Testing Strategies](#testing-strategies)
9. [Real-World Examples](#real-world-examples)
10. [Troubleshooting](#troubleshooting)
11. [Migration from 2.x to 3.0](#migration-from-2x-to-30)
12. [Resources](#resources)

---

## Requirements & Compatibility

### Minimum Requirements

**Official Requirements** (Source: [Wagtail AI GitHub](https://github.com/wagtail/wagtail-ai)):
- **Python**: 3.11+ (increased from 3.8 in v2.x)
- **Django**: 4.2+ (LTS recommended)
- **Wagtail**: 7.1+ (Wagtail 7.0 LTS minimum for production)

### Recommended Stack

For production environments:
```python
# Recommended versions (as of Nov 2025)
wagtail==7.2         # Latest stable
django==5.2          # Latest stable LTS
wagtail-ai==3.0.0    # Latest stable
python==3.11.x       # Balance of compatibility and features
```

### Browser Compatibility

Wagtail AI's admin interface requires:
- Modern browsers (Chrome, Firefox, Safari, Edge)
- JavaScript enabled
- Cookies enabled for authentication

---

## Installation & Configuration

### 1. Basic Installation

**Install with default backends** (includes OpenAI support):
```bash
pip install wagtail-ai
```

**For Claude/Anthropic support**, install the LLM plugin:
```bash
# Install LLM library with Anthropic plugin
pip install llm-anthropic

# Set API key
llm keys set anthropic
# (Enter your Anthropic API key when prompted)
```

**For local models** (Ollama, llama.cpp):
```bash
pip install llm-ollama  # For Ollama support
```

### 2. Django Settings Configuration

**Add to `INSTALLED_APPS`**:
```python
INSTALLED_APPS = [
    # ... other apps
    "wagtail_ai",  # Add near other Wagtail apps
]
```

**Basic Configuration** (OpenAI with GPT-3.5):
```python
# settings.py

WAGTAIL_AI = {
    "PROVIDERS": {  # NOTE: Changed from "BACKENDS" in 3.0
        "default": {
            "CLASS": "wagtail_ai.ai.llm.LLMBackend",
            "CONFIG": {
                "MODEL_ID": "gpt-3.5-turbo",
                "TOKEN_LIMIT": 16385,  # GPT-3.5 Turbo 16K context window
            },
        }
    }
}
```

### 3. Environment Variables

**CRITICAL: Never commit API keys to version control!**

Create `.env` file:
```bash
# .env
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Load in `settings.py`:
```python
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Access keys
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
```

**Add to `.gitignore`**:
```bash
# .gitignore
.env
*.env
.env.local
```

### 4. RichText Field Configuration

**Enable AI features in RichText fields**:

If you've restricted RichText features, explicitly add `"ai"`:
```python
# models.py
from wagtail.fields import RichTextField

class BlogPost(Page):
    body = RichTextField(
        features=[
            'bold', 'italic', 'link',
            'h2', 'h3', 'ul', 'ol',
            'ai',  # REQUIRED: Enable AI button in editor
        ]
    )
```

**Default behavior**: If no `features` list is specified, all registered features (including `ai`) are included automatically.

---

## AI Provider Setup

### OpenAI Backend (Default)

**Best for**: General content generation, cost-effective for high volume

**Configuration**:
```python
WAGTAIL_AI = {
    "PROVIDERS": {
        "default": {
            "CLASS": "wagtail_ai.ai.openai.OpenAIBackend",
            "CONFIG": {
                "MODEL_ID": "gpt-4o",  # Latest GPT-4 Omni model
                "TOKEN_LIMIT": 128000,  # GPT-4 Turbo context window
            },
        }
    }
}
```

**Environment Variable**:
```bash
export OPENAI_API_KEY="sk-proj-your-key-here"
```

**Supported Features**:
- Text completion
- Image description generation
- Title and meta description suggestions

**Cost Estimate** (as of Nov 2025):
- GPT-3.5 Turbo: $0.0005 input / $0.0015 output per 1K tokens
- GPT-4 Omni: $0.005 input / $0.015 output per 1K tokens
- 1000-word correction: ~$0.003 (GPT-3.5) or ~$0.026 (GPT-4)

### Anthropic Claude Backend (LLM Plugin)

**Best for**: Complex reasoning, long-form content, latest features

**Prerequisites**:
```bash
pip install llm-anthropic
llm keys set anthropic
```

**Configuration**:
```python
WAGTAIL_AI = {
    "PROVIDERS": {
        "default": {
            "CLASS": "wagtail_ai.ai.llm.LLMBackend",
            "CONFIG": {
                "MODEL_ID": "claude-3-5-sonnet-20241022",  # Latest Sonnet
                "TOKEN_LIMIT": 200000,  # Claude 3.5 Sonnet context window
                "INIT_KWARGS": {
                    "key": os.getenv("ANTHROPIC_API_KEY"),  # Explicit key
                },
                "PROMPT_KWARGS": {
                    "system": "You are a helpful content editor focused on clarity and accessibility.",
                },
            },
        }
    }
}
```

**Supported Models** (via `llm-anthropic` 0.19+):
- `claude-opus-4-1` - Most capable, highest cost
- `claude-sonnet-4-5` - Balanced performance/cost
- `claude-3-5-sonnet-20241022` - Proven production model
- `claude-3-5-haiku` - Fast, cost-effective
- `claude-haiku-4-5` - Ultra-fast

**Cost Estimate** (as of Nov 2025):
- Claude Haiku: $0.25 input / $1.25 output per 1M tokens
- Claude Sonnet: $3 input / $15 output per 1M tokens
- Claude Opus: $15 input / $75 output per 1M tokens

**Advanced Features**:
```python
# Extended thinking mode (Claude 3.7+)
"PROMPT_KWARGS": {
    "thinking": 1,  # Enable extended reasoning
}

# Prefill responses
"PROMPT_KWARGS": {
    "prefill": "Here is a concise",  # Start responses with this
}
```

### Mistral Backend (LLM Plugin)

**Best for**: European data residency, cost-effective alternative to OpenAI

**Configuration**:
```python
WAGTAIL_AI = {
    "PROVIDERS": {
        "default": {
            "CLASS": "wagtail_ai.ai.llm.LLMBackend",
            "CONFIG": {
                "MODEL_ID": "mistral-large-latest",
                "TOKEN_LIMIT": 128000,
            },
        }
    }
}
```

### Local Models (Ollama)

**Best for**: Privacy-sensitive content, no API costs, offline capability

**Prerequisites**:
```bash
# Install Ollama (macOS)
brew install ollama

# Pull model
ollama pull llama2

# Install LLM plugin
pip install llm-ollama
```

**Configuration**:
```python
WAGTAIL_AI = {
    "PROVIDERS": {
        "default": {
            "CLASS": "wagtail_ai.ai.llm.LLMBackend",
            "CONFIG": {
                "MODEL_ID": "llama2",  # Local model
                "TOKEN_LIMIT": 4096,
            },
        }
    }
}
```

**Advantages**:
- No API costs
- Complete privacy (no data leaves your server)
- No rate limits
- Works offline

**Disadvantages**:
- Requires significant compute resources (GPU recommended)
- Lower quality than GPT-4/Claude for complex tasks
- Slower response times

### Multi-Provider Setup

**Use case**: Fallback providers for high availability

```python
WAGTAIL_AI = {
    "PROVIDERS": {
        "default": {
            "CLASS": "wagtail_ai.ai.openai.OpenAIBackend",
            "CONFIG": {
                "MODEL_ID": "gpt-4o",
            },
        },
        "fallback": {
            "CLASS": "wagtail_ai.ai.llm.LLMBackend",
            "CONFIG": {
                "MODEL_ID": "claude-3-5-sonnet-20241022",
            },
        },
        "local": {
            "CLASS": "wagtail_ai.ai.llm.LLMBackend",
            "CONFIG": {
                "MODEL_ID": "llama2",
            },
        },
    }
}
```

**Note**: As of v3.0.0, Wagtail AI does not have built-in automatic failover. You must implement custom logic to switch providers.

---

## Production Deployment

### Django Settings Checklist

**CRITICAL: Production settings must differ from development!**

```python
# settings/production.py

# 1. Disable debug mode
DEBUG = False

# 2. Set secure secret key
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY')  # NEVER hardcode!
if not SECRET_KEY or len(SECRET_KEY) < 50:
    raise ImproperlyConfigured("SECRET_KEY must be set and at least 50 characters")

# 3. Configure allowed hosts
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '').split(',')

# 4. Enable HTTPS enforcement
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# 5. Configure CORS for frontend
CORS_ALLOWED_ORIGINS = [
    "https://yourdomain.com",
    "https://www.yourdomain.com",
]

# 6. Set Content Security Policy
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'", "https://cdn.jsdelivr.net")  # Wagtail AI uses CDN
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'")  # Required for Wagtail admin
```

### API Key Rotation Strategy

**Recommended Schedule**:
- **Development**: Rotate every 90 days
- **Production**: Rotate every 30-60 days
- **Breach**: Rotate immediately

**Rotation Process**:
1. Generate new API key from provider (OpenAI/Anthropic)
2. Add new key to environment variables (keep old key active)
3. Update staging environment
4. Test thoroughly
5. Update production environment
6. Revoke old key after 24-hour grace period

**Implementation**:
```python
# Support multiple keys for zero-downtime rotation
OPENAI_API_KEYS = [
    os.getenv('OPENAI_API_KEY_PRIMARY'),
    os.getenv('OPENAI_API_KEY_SECONDARY'),  # During rotation only
]

# Use primary, fall back to secondary
OPENAI_API_KEY = next(key for key in OPENAI_API_KEYS if key)
```

### Monitoring & Logging

**Track API Usage**:
```python
# settings.py
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'ai_usage': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/var/log/wagtail/ai_usage.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
        },
    },
    'loggers': {
        'wagtail_ai': {
            'handlers': ['ai_usage'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
```

**Monitor Key Metrics**:
- API request count (track against provider limits)
- Average response time (detect performance degradation)
- Error rate (API failures, timeouts)
- Token usage (cost monitoring)
- User adoption (which features are used)

### Performance Optimization

**1. Implement Request Caching**

Cache AI responses to reduce duplicate API calls:
```python
# Custom middleware or view logic
from django.core.cache import cache
import hashlib

def get_ai_completion(prompt):
    # Generate cache key from prompt
    cache_key = f"ai_completion:{hashlib.sha256(prompt.encode()).hexdigest()[:16]}"

    # Check cache first
    result = cache.get(cache_key)
    if result:
        return result

    # Call AI API
    result = wagtail_ai_backend.complete(prompt)

    # Cache for 1 hour
    cache.set(cache_key, result, 3600)

    return result
```

**2. Async Processing for Long Tasks**

Use Celery for background AI processing:
```python
# tasks.py
from celery import shared_task
from wagtail_ai.ai import get_ai_backend

@shared_task
def generate_image_alt_text(image_id):
    image = Image.objects.get(id=image_id)
    backend = get_ai_backend()

    alt_text = backend.describe_image(image.file.path)

    image.alt_text = alt_text
    image.save()

    return alt_text
```

**3. Rate Limiting**

Prevent API quota exhaustion:
```python
# Install django-ratelimit
pip install django-ratelimit

# Apply to Wagtail AI views (if exposing via custom views)
from django_ratelimit.decorators import ratelimit

@ratelimit(key='user', rate='10/h', method='POST')
def ai_content_suggestion(request):
    # AI processing logic
    pass
```

### Database Migrations

Run before deployment:
```bash
python manage.py migrate wagtail_ai
python manage.py migrate  # Run all pending migrations
```

**v3.0.0 introduces new models** for prompt management - ensure migrations are applied!

---

## Security & Privacy

### API Key Security

**MUST DO**:
1. Store keys in environment variables (`.env` file)
2. Add `.env` to `.gitignore`
3. Use secrets management in production (AWS Secrets Manager, HashiCorp Vault)
4. Rotate keys regularly (every 30-60 days)
5. Monitor for leaked keys (use GitGuardian, TruffleHog)

**Example: AWS Secrets Manager Integration**:
```python
# settings/production.py
import boto3
from botocore.exceptions import ClientError

def get_secret(secret_name):
    client = boto3.client('secretsmanager', region_name='us-east-1')
    try:
        response = client.get_secret_value(SecretId=secret_name)
        return response['SecretString']
    except ClientError as e:
        raise Exception(f"Could not retrieve secret: {e}")

OPENAI_API_KEY = get_secret('production/openai-api-key')
```

### Data Privacy & GDPR Compliance

**CRITICAL: No dedicated Wagtail AI privacy documentation exists!**

**What Happens to Your Data**:
- Content is sent to third-party AI providers (OpenAI, Anthropic, etc.)
- Providers process data according to their terms of service
- No data is stored by Wagtail AI itself (it's a passthrough)

**Compliance Responsibility**:
You must ensure your AI provider has appropriate data processing agreements:

**OpenAI**:
- Offers Business Associate Agreement (BAA) for HIPAA compliance
- Enterprise tier: Zero data retention
- API data retention: 30 days by default (can opt out)
- Privacy policy: https://openai.com/privacy/

**Anthropic**:
- Offers Data Processing Addendum (DPA) for GDPR
- Does not train on API data
- Zero data retention option available
- Privacy policy: https://www.anthropic.com/legal/privacy

**Recommendations**:
1. **Review provider terms**: Ensure GDPR/CCPA/HIPAA compliance
2. **Data Processing Agreement**: Sign DPA with your AI provider
3. **User consent**: Inform users that AI processes their content
4. **PII filtering**: Sanitize user-generated content before AI processing
5. **Audit trail**: Log all AI requests for compliance review

**Example: PII Sanitization**:
```python
# Custom pre-processing hook
import re

def sanitize_for_ai(content):
    """Remove PII before sending to AI provider."""
    # Remove email addresses
    content = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]', content)

    # Remove phone numbers (basic US format)
    content = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[PHONE]', content)

    # Remove SSNs
    content = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '[SSN]', content)

    return content
```

### Content Security Policy (CSP)

Wagtail AI may load resources from CDNs. Configure CSP:
```python
# settings.py
CSP_SCRIPT_SRC = [
    "'self'",
    "https://cdn.jsdelivr.net",  # Wagtail admin dependencies
]

CSP_STYLE_SRC = [
    "'self'",
    "'unsafe-inline'",  # Required for Wagtail admin
]

CSP_CONNECT_SRC = [
    "'self'",
    "https://api.openai.com",      # If using OpenAI backend
    "https://api.anthropic.com",   # If using Anthropic backend
]
```

---

## Cost Optimization

### Understanding Token Usage

**Token Basics**:
- 1 token ≈ 4 characters ≈ 0.75 words (English)
- 1000 words ≈ 1333 tokens
- Pricing varies by model and provider

**Example Calculation**:
```
Task: Correct 1000-word blog post
Input: 1000 words (1333 tokens) + 30-word prompt (40 tokens) = 1373 tokens
Output: 1000 words (1333 tokens)

GPT-3.5 Turbo:
  Input: 1373 tokens × $0.0005/1K = $0.0007
  Output: 1333 tokens × $0.0015/1K = $0.0020
  Total: $0.0027 per correction

GPT-4:
  Input: 1373 tokens × $0.005/1K = $0.0069
  Output: 1333 tokens × $0.015/1K = $0.0200
  Total: $0.0269 per correction
```

### Optimization Strategies

**1. Prompt Engineering**

**Bad** (verbose, expensive):
```python
PROMPT_KWARGS = {
    "system": """You are an expert content editor. Please carefully review
    the following text and make improvements to grammar, spelling, clarity,
    and readability. Ensure the tone is professional but accessible.
    Make sure to check for common errors like comma splices, run-on sentences,
    and subject-verb agreement issues. Also improve word choice where appropriate."""
}
# 67 tokens
```

**Good** (concise, cost-effective):
```python
PROMPT_KWARGS = {
    "system": "Fix grammar, improve clarity, maintain professional tone."
}
# 11 tokens (6x cheaper on every request!)
```

**2. Model Selection by Use Case**

| Use Case | Recommended Model | Rationale |
|----------|------------------|-----------|
| Grammar/spelling checks | GPT-3.5 Turbo / Claude Haiku | Simple task, fast, cheap |
| Meta descriptions | GPT-3.5 Turbo | Short outputs, high volume |
| Alt text generation | GPT-4 Vision / Claude Opus | Image understanding critical |
| Long-form content | Claude Sonnet | Better coherence |
| Real-time suggestions | Claude Haiku | <1s latency |

**3. Implement Token Limits**

Prevent runaway costs:
```python
WAGTAIL_AI = {
    "PROVIDERS": {
        "default": {
            "CLASS": "wagtail_ai.ai.llm.LLMBackend",
            "CONFIG": {
                "MODEL_ID": "gpt-3.5-turbo",
                "TOKEN_LIMIT": 4096,  # Hard cap on context window
                "PROMPT_KWARGS": {
                    "max_tokens": 500,  # Limit output length
                },
            },
        }
    }
}
```

**4. Caching Identical Requests**

See [Performance Optimization](#performance-optimization) section.

**5. Batch Processing**

Process multiple items in one API call when possible:
```python
# Inefficient: 10 API calls
for post in posts:
    ai_backend.generate_title(post.body)

# Efficient: 1 API call
batch_content = "\n\n---\n\n".join([post.body for post in posts])
titles = ai_backend.generate_titles_batch(batch_content)
```

**6. Monitoring & Alerts**

Set up cost alerts:
```python
# Example: CloudWatch alarm for AWS costs
# Or use provider dashboards (OpenAI Usage Dashboard)

# Log token usage
import logging

logger = logging.getLogger('wagtail_ai.usage')

def track_token_usage(prompt_tokens, completion_tokens, model):
    cost = calculate_cost(prompt_tokens, completion_tokens, model)
    logger.info(f"[AI_USAGE] Model: {model}, Tokens: {prompt_tokens + completion_tokens}, Cost: ${cost:.4f}")
```

---

## Error Handling & Fallbacks

### Common Error Scenarios

1. **API Rate Limits** - Provider returns 429 Too Many Requests
2. **API Timeouts** - Request takes >30s (provider timeout)
3. **Invalid API Key** - 401 Unauthorized
4. **Model Not Found** - 404 or invalid MODEL_ID
5. **Content Policy Violation** - Provider rejects unsafe content
6. **Network Failures** - DNS, connection errors

### Implementing Graceful Degradation

**Pattern 1: Try-Except with Fallback**

```python
# Custom view or service
from wagtail_ai.ai import get_ai_backend
import logging

logger = logging.getLogger(__name__)

def generate_meta_description(page_content):
    """Generate meta description with fallback."""
    try:
        backend = get_ai_backend()
        description = backend.complete(
            f"Write a 150-character meta description: {page_content[:500]}"
        )
        return description.strip()

    except Exception as e:
        # Log error with context
        logger.error(f"[AI_ERROR] Failed to generate meta: {e}")

        # Fallback: Extract first sentence
        fallback = page_content.split('.')[0][:150]
        logger.info(f"[AI_FALLBACK] Using extracted content")
        return fallback
```

**Pattern 2: Timeout Protection**

```python
from requests.exceptions import Timeout
import signal

class TimeoutError(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutError("AI request timed out")

def generate_with_timeout(prompt, timeout_seconds=10):
    """Execute AI request with timeout."""
    # Set alarm
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(timeout_seconds)

    try:
        backend = get_ai_backend()
        result = backend.complete(prompt)
        signal.alarm(0)  # Cancel alarm
        return result

    except TimeoutError:
        signal.alarm(0)
        logger.warning("[AI_TIMEOUT] Request exceeded timeout")
        return None
```

**Pattern 3: Circuit Breaker**

```python
# Install: pip install pybreaker
from pybreaker import CircuitBreaker

# Configure circuit breaker
ai_breaker = CircuitBreaker(
    fail_max=5,           # Open after 5 failures
    timeout_duration=60,  # Stay open for 60 seconds
)

@ai_breaker
def call_ai_with_breaker(prompt):
    """Call AI with circuit breaker protection."""
    backend = get_ai_backend()
    return backend.complete(prompt)

# Usage
try:
    result = call_ai_with_breaker("Generate title...")
except CircuitBreakerError:
    logger.error("[CIRCUIT_OPEN] AI service is unavailable")
    result = None  # Use fallback
```

**Pattern 4: Retry with Exponential Backoff**

```python
import time
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10)
)
def generate_with_retry(prompt):
    """Retry AI request with exponential backoff."""
    backend = get_ai_backend()
    return backend.complete(prompt)

# Usage
try:
    result = generate_with_retry("Fix grammar...")
    # Will retry up to 3 times: wait 2s, 4s, 8s
except Exception as e:
    logger.error(f"[AI_RETRY_FAILED] All retries exhausted: {e}")
```

### Provider-Specific Error Handling

**OpenAI Errors**:
```python
from openai import (
    RateLimitError,
    APIError,
    Timeout,
    AuthenticationError
)

def handle_openai_errors(prompt):
    try:
        backend = get_ai_backend()
        return backend.complete(prompt)

    except RateLimitError:
        logger.warning("[OPENAI_RATE_LIMIT] Waiting 60s...")
        time.sleep(60)
        return handle_openai_errors(prompt)  # Retry

    except AuthenticationError:
        logger.error("[OPENAI_AUTH] Invalid API key")
        raise  # Critical - don't retry

    except Timeout:
        logger.warning("[OPENAI_TIMEOUT] Request timed out")
        return None  # Fallback

    except APIError as e:
        logger.error(f"[OPENAI_API_ERROR] {e}")
        return None
```

**Anthropic Errors**:
```python
from anthropic import (
    RateLimitError,
    APIError,
    AuthenticationError
)

# Similar pattern to OpenAI
```

---

## Testing Strategies

### Unit Testing AI Integrations

**Challenge**: External API calls make tests slow and non-deterministic.

**Solution**: Mock AI responses.

**Example: Mocking AI Backend**

```python
# tests/test_ai_features.py
from unittest.mock import patch, MagicMock
from django.test import TestCase
from myapp.services import generate_meta_description

class AIMetaDescriptionTests(TestCase):

    @patch('myapp.services.get_ai_backend')
    def test_meta_description_generation(self, mock_backend):
        """Test AI meta description with mocked response."""
        # Arrange
        mock_ai = MagicMock()
        mock_ai.complete.return_value = "This is a test meta description."
        mock_backend.return_value = mock_ai

        # Act
        result = generate_meta_description("Sample page content here.")

        # Assert
        self.assertEqual(result, "This is a test meta description.")
        mock_ai.complete.assert_called_once()

    @patch('myapp.services.get_ai_backend')
    def test_fallback_on_error(self, mock_backend):
        """Test fallback when AI fails."""
        # Arrange
        mock_ai = MagicMock()
        mock_ai.complete.side_effect = Exception("API error")
        mock_backend.return_value = mock_ai

        # Act
        result = generate_meta_description("Sample page content here.")

        # Assert
        self.assertIn("Sample page content", result)  # Fallback used
```

### Integration Testing

**Test with real API** (use test API keys):

```python
# tests/integration/test_ai_integration.py
import pytest
from wagtail_ai.ai import get_ai_backend

@pytest.mark.skipif(
    not os.getenv('RUN_AI_TESTS'),
    reason="Set RUN_AI_TESTS=1 to run integration tests"
)
class TestAIIntegration:

    def test_openai_completion(self):
        """Test actual OpenAI API call."""
        backend = get_ai_backend()
        result = backend.complete("Say 'test passed'")

        assert "test passed" in result.lower()

    def test_token_limit_respected(self):
        """Test TOKEN_LIMIT prevents overflow."""
        backend = get_ai_backend()

        # Request exceeds token limit
        long_prompt = "x" * 100000

        with pytest.raises(Exception):  # Should fail gracefully
            backend.complete(long_prompt)
```

**Run integration tests**:
```bash
# Set flag to enable real API tests
export RUN_AI_TESTS=1
export OPENAI_API_KEY=sk-test-xxx

pytest tests/integration/
```

### Manual Testing Checklist

Test these scenarios in Wagtail admin:

- [ ] RichText editor shows AI button
- [ ] Clicking AI button opens prompt dialog
- [ ] Submitting prompt generates content
- [ ] Generated content appears in editor
- [ ] Error messages display on failure
- [ ] Image alt text generation works
- [ ] Title/meta description generation works
- [ ] Related pages suggestions appear
- [ ] Content feedback displays correctly

---

## Real-World Examples

### Organizations Using Wagtail AI

**1. The Motley Fool**
- **Use Case**: Financial content generation and editing
- **Contact**: Brady Moe, Tech Manager
- **Key Benefits**: Faster content production, consistency
- **Source**: [Wagtail AI Webinar](https://wagtail.org/blog/wagtail-ai-webinar/)

**2. Royal National Institute for the Blind (RNIB)**
- **Use Case**: Accessibility improvements (alt text, content simplification)
- **Contact**: Aidan Forman, Director of Technology
- **Key Benefits**: Improved accessibility, reduced manual alt text writing
- **Source**: [Wagtail AI Webinar](https://wagtail.org/blog/wagtail-ai-webinar/)

### Open Source Examples

**Wagtail Bakerydemo**
- **URL**: https://github.com/wagtail/bakerydemo
- **Description**: Official Wagtail demo site (may include AI features in future)
- **Status**: Check for Wagtail AI integration examples

**Community Implementations**
- Search GitHub: `wagtail-ai` topic
- Check Django Packages: https://djangopackages.org/packages/p/wagtail-ai/

---

## Troubleshooting

### AI Button Not Appearing

**Symptom**: No AI button in RichText editor

**Causes & Solutions**:

1. **`wagtail_ai` not in `INSTALLED_APPS`**
   ```python
   # Fix: Add to settings.py
   INSTALLED_APPS = [
       # ...
       "wagtail_ai",
   ]
   ```

2. **`features` list excludes `"ai"`**
   ```python
   # Fix: Add to field definition
   body = RichTextField(features=['bold', 'italic', 'ai'])
   ```

3. **JavaScript not loaded**
   ```bash
   # Fix: Collect static files
   python manage.py collectstatic --noinput
   ```

4. **Browser cache**
   ```
   Fix: Hard refresh (Cmd+Shift+R / Ctrl+Shift+F5)
   ```

### API Authentication Errors

**Symptom**: "Invalid API key" or 401 errors

**Solutions**:

1. **Check environment variable**
   ```bash
   echo $OPENAI_API_KEY  # Should output your key
   ```

2. **Verify key in settings**
   ```python
   # Debug print (remove after testing!)
   print(f"API Key: {os.getenv('OPENAI_API_KEY')[:10]}...")
   ```

3. **Test key directly**
   ```bash
   curl https://api.openai.com/v1/models \
     -H "Authorization: Bearer $OPENAI_API_KEY"
   ```

4. **Check provider dashboard**
   - OpenAI: https://platform.openai.com/account/api-keys
   - Anthropic: https://console.anthropic.com/account/keys

### Rate Limit Errors

**Symptom**: "Rate limit exceeded" or 429 errors

**Solutions**:

1. **Check provider limits**
   - OpenAI Free Tier: 3 requests/min
   - OpenAI Paid Tier: 3,500 requests/min

2. **Implement exponential backoff** (see [Error Handling](#error-handling--fallbacks))

3. **Upgrade provider tier**

4. **Implement request queuing**
   ```python
   from celery import shared_task

   @shared_task(rate_limit='10/m')  # 10 per minute
   def process_ai_request(content):
       # AI processing
       pass
   ```

### Slow Response Times

**Symptom**: AI requests take >10 seconds

**Solutions**:

1. **Switch to faster model**
   - GPT-3.5 Turbo: ~2s
   - Claude Haiku: <1s
   - GPT-4: 5-10s (slower but higher quality)

2. **Reduce prompt size**
   ```python
   # Limit content sent to AI
   content = page.body[:2000]  # First 2000 chars only
   ```

3. **Use async processing**
   ```python
   # Process in background, notify on completion
   from django.core.mail import send_mail

   @shared_task
   def generate_async(content, user_email):
       result = ai_backend.complete(content)
       send_mail('AI Result Ready', result, 'noreply@example.com', [user_email])
   ```

4. **Check network latency**
   ```bash
   ping api.openai.com
   ```

### Migration Issues (2.x to 3.0)

See [Migration Guide](#migration-from-2x-to-30) below.

---

## Migration from 2.x to 3.0

### Breaking Changes

**1. `BACKENDS` renamed to `PROVIDERS`**

Before (v2.x):
```python
WAGTAIL_AI = {
    "BACKENDS": {  # Old key
        "default": {...}
    }
}
```

After (v3.0):
```python
WAGTAIL_AI = {
    "PROVIDERS": {  # New key
        "default": {...}
    }
}
```

**2. `IMAGE_DESCRIPTION_BACKEND` renamed**

Before (v2.x):
```python
WAGTAIL_AI = {
    "IMAGE_DESCRIPTION_BACKEND": "default"
}
```

After (v3.0):
```python
WAGTAIL_AI = {
    "IMAGE_DESCRIPTION_PROVIDER": "default"  # Renamed
}
```

**3. Prompts now managed in admin**

Before (v2.x):
```python
WAGTAIL_AI_PROMPTS = {
    "correct": "Fix grammar and spelling in this text:",
}
```

After (v3.0):
```
# Remove WAGTAIL_AI_PROMPTS from settings.py
# Configure prompts in Wagtail admin: Settings > Prompts
```

**4. Langchain dependency removed**

Before (v2.x):
```bash
pip install wagtail-ai langchain
```

After (v3.0):
```bash
pip install wagtail-ai  # Langchain no longer required
```

**5. Minimum version bumps**

| Dependency | v2.x | v3.0 |
|------------|------|------|
| Python | 3.8+ | 3.11+ |
| Django | 3.2+ | 4.2+ |
| Wagtail | 4.1+ | 7.1+ |

### Migration Steps

**1. Audit Current Configuration**

```bash
# Check current Wagtail AI version
pip show wagtail-ai

# Check for deprecated settings
grep -r "WAGTAIL_AI_PROMPTS" .
grep -r "BACKENDS" . | grep "WAGTAIL_AI"
grep -r "IMAGE_DESCRIPTION_BACKEND" .
```

**2. Update Dependencies**

```bash
# Upgrade Python if needed
pyenv install 3.11.9
pyenv local 3.11.9

# Upgrade Django and Wagtail
pip install --upgrade django==5.2 wagtail==7.2

# Upgrade Wagtail AI
pip install --upgrade wagtail-ai
```

**3. Update Settings**

```python
# settings.py - Update all instances

# Before
WAGTAIL_AI = {
    "BACKENDS": {
        "default": {
            "CLASS": "wagtail_ai.ai.llm.LLMBackend",
            "CONFIG": {"MODEL_ID": "gpt-3.5-turbo"},
        }
    },
    "IMAGE_DESCRIPTION_BACKEND": "default",
}

WAGTAIL_AI_PROMPTS = {
    "correct": "Fix grammar:",
}

# After
WAGTAIL_AI = {
    "PROVIDERS": {  # Changed
        "default": {
            "CLASS": "wagtail_ai.ai.llm.LLMBackend",
            "CONFIG": {"MODEL_ID": "gpt-3.5-turbo"},
        }
    },
    "IMAGE_DESCRIPTION_PROVIDER": "default",  # Changed
}

# Remove WAGTAIL_AI_PROMPTS - migrate to admin
```

**4. Migrate Prompts to Admin**

```bash
# Run migrations
python manage.py migrate wagtail_ai

# Access admin
python manage.py runserver

# Navigate to: Settings > Prompts
# Manually recreate prompts from WAGTAIL_AI_PROMPTS
```

**5. Test Thoroughly**

```bash
# Run tests
python manage.py test

# Check for deprecation warnings
python manage.py check

# Manual testing
# - Open Wagtail admin
# - Create/edit page with RichText field
# - Test AI features
```

**6. Deploy to Staging**

```bash
# Deploy to staging environment
# Test all AI features
# Monitor logs for errors
```

**7. Deploy to Production**

```bash
# Deploy to production during low-traffic window
# Monitor API usage and error rates
```

### Rollback Plan

If migration fails:

1. **Revert code**:
   ```bash
   git revert HEAD  # Or checkout previous commit
   ```

2. **Downgrade packages**:
   ```bash
   pip install wagtail-ai==2.1.2
   ```

3. **Restore database**:
   ```bash
   python manage.py migrate wagtail_ai 0001  # Or restore DB backup
   ```

---

## Resources

### Official Documentation

- **Wagtail AI Docs**: https://wagtail-ai.readthedocs.io/latest/
- **Installation Guide**: https://wagtail-ai.readthedocs.io/stable/installation/
- **AI Backends**: https://wagtail-ai.readthedocs.io/latest/ai-backends/
- **GitHub Repository**: https://github.com/wagtail/wagtail-ai
- **Changelog**: https://github.com/wagtail/wagtail-ai/blob/main/CHANGELOG.md

### AI Provider Documentation

- **OpenAI API**: https://platform.openai.com/docs
- **Anthropic Claude**: https://docs.anthropic.com/
- **Mistral AI**: https://docs.mistral.ai/
- **LLM Library** (Simon Willison): https://llm.datasette.io/
- **llm-anthropic Plugin**: https://github.com/simonw/llm-anthropic

### Community Resources

- **Wagtail CMS Official Site**: https://wagtail.org/
- **Wagtail AI Product Page**: https://wagtail.org/wagtail-ai/
- **Package Spotlight Blog**: https://wagtail.org/blog/package-spotlight-wagtail-ai/
- **Wagtail AI Webinar Recording**: https://wagtail.org/blog/wagtail-ai-webinar/
- **Django Packages**: https://djangopackages.org/packages/p/wagtail-ai/
- **PyPI**: https://pypi.org/project/wagtail-ai/

### Related Tools

- **Django Rate Limit**: https://django-ratelimit.readthedocs.io/
- **Celery** (async tasks): https://docs.celeryproject.org/
- **PyBreaker** (circuit breaker): https://github.com/danielfm/pybreaker
- **Tenacity** (retry logic): https://tenacity.readthedocs.io/

### Security & Privacy

- **OpenAI Privacy Policy**: https://openai.com/privacy/
- **Anthropic Privacy Policy**: https://www.anthropic.com/legal/privacy
- **GDPR Compliance Guide**: https://gdpr.eu/
- **Django Security Checklist**: https://docs.djangoproject.com/en/stable/howto/deployment/checklist/

---

## Appendix: Complete Example Configuration

### Production-Ready `settings.py`

```python
# settings/production.py
import os
from pathlib import Path

# Build paths
BASE_DIR = Path(__file__).resolve().parent.parent

# Security
DEBUG = False
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY')
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '').split(',')

# HTTPS
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Applications
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Wagtail
    'wagtail.contrib.forms',
    'wagtail.contrib.redirects',
    'wagtail.embeds',
    'wagtail.sites',
    'wagtail.users',
    'wagtail.snippets',
    'wagtail.documents',
    'wagtail.images',
    'wagtail.search',
    'wagtail.admin',
    'wagtail',

    # Wagtail AI
    'wagtail_ai',

    # Your apps
    'blog',
    'home',
]

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME'),
        'USER': os.getenv('DB_USER'),
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': os.getenv('DB_HOST'),
        'PORT': os.getenv('DB_PORT', '5432'),
    }
}

# Cache (Redis)
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': os.getenv('REDIS_URL', 'redis://localhost:6379/1'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

# Wagtail AI Configuration
WAGTAIL_AI = {
    "PROVIDERS": {
        "default": {
            "CLASS": "wagtail_ai.ai.llm.LLMBackend",
            "CONFIG": {
                "MODEL_ID": "claude-3-5-sonnet-20241022",
                "TOKEN_LIMIT": 200000,
                "INIT_KWARGS": {
                    "key": os.getenv("ANTHROPIC_API_KEY"),
                },
                "PROMPT_KWARGS": {
                    "system": "You are a helpful content editor. Be concise and clear.",
                },
            },
        },
        "fast": {
            "CLASS": "wagtail_ai.ai.openai.OpenAIBackend",
            "CONFIG": {
                "MODEL_ID": "gpt-3.5-turbo",
                "TOKEN_LIMIT": 16385,
            },
        },
    },
    "IMAGE_DESCRIPTION_PROVIDER": "default",
}

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/var/log/django/app.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'ai_usage': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/var/log/django/ai_usage.log',
            'maxBytes': 10485760,
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': False,
        },
        'wagtail_ai': {
            'handlers': ['ai_usage'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'static')
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Wagtail settings
WAGTAIL_SITE_NAME = 'My Site'
WAGTAILADMIN_BASE_URL = 'https://example.com'
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-11-09 | Initial release - comprehensive Wagtail AI 3.0 best practices |

---

**Document compiled by**: Claude Code (Anthropic)
**Research methodology**: Web search, official documentation analysis, community best practices synthesis
**Last updated**: November 9, 2025

For questions or contributions, please open an issue at: https://github.com/wagtail/wagtail-ai/issues
