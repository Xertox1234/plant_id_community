# Wagtail AI Quick Start Guide

**For**: Developers who want to get Wagtail AI running in 5 minutes
**See also**: `WAGTAIL_AI_BEST_PRACTICES.md` (comprehensive guide)

---

## TL;DR - Fastest Setup

```bash
# 1. Install
pip install wagtail-ai

# 2. Configure (settings.py)
INSTALLED_APPS = [
    # ... existing apps
    "wagtail_ai",
]

WAGTAIL_AI = {
    "PROVIDERS": {
        "default": {
            "CLASS": "wagtail_ai.ai.llm.LLMBackend",
            "CONFIG": {"MODEL_ID": "gpt-3.5-turbo"},
        }
    }
}

# 3. Set API key (.env)
OPENAI_API_KEY=sk-proj-your-key-here

# 4. Migrate
python manage.py migrate

# 5. Test in Wagtail admin
# Create/edit page with RichText field > Click AI button
```

---

## Choose Your Provider

### OpenAI (Recommended for Getting Started)

**Pros**: Easy setup, reliable, good documentation
**Cons**: Moderate cost, data sent to OpenAI

```bash
# 1. Get API key
# Visit: https://platform.openai.com/account/api-keys

# 2. Install (already done if you installed wagtail-ai)
pip install wagtail-ai

# 3. Configure
# settings.py
WAGTAIL_AI = {
    "PROVIDERS": {
        "default": {
            "CLASS": "wagtail_ai.ai.openai.OpenAIBackend",
            "CONFIG": {"MODEL_ID": "gpt-4o"},  # Or gpt-3.5-turbo
        }
    }
}

# .env
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxx
```

**Cost**: ~$0.003 per 1000-word correction (GPT-3.5 Turbo)

---

### Anthropic Claude (Recommended for Production)

**Pros**: Better reasoning, longer context, competitive pricing
**Cons**: Requires LLM plugin installation

```bash
# 1. Get API key
# Visit: https://console.anthropic.com/account/keys

# 2. Install LLM plugin
pip install llm-anthropic
llm keys set anthropic
# (Paste your API key when prompted)

# 3. Configure
# settings.py
WAGTAIL_AI = {
    "PROVIDERS": {
        "default": {
            "CLASS": "wagtail_ai.ai.llm.LLMBackend",
            "CONFIG": {
                "MODEL_ID": "claude-3-5-sonnet-20241022",
                "TOKEN_LIMIT": 200000,
            },
        }
    }
}

# .env
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxx
```

**Cost**: ~$0.009 per 1000-word correction (Claude Sonnet)

---

### Local Models (Free, Private)

**Pros**: No API costs, complete privacy, works offline
**Cons**: Requires GPU, slower, lower quality

```bash
# 1. Install Ollama
brew install ollama  # macOS
# Or: https://ollama.ai/download

# 2. Pull model
ollama pull llama2

# 3. Install LLM plugin
pip install llm-ollama

# 4. Configure
# settings.py
WAGTAIL_AI = {
    "PROVIDERS": {
        "default": {
            "CLASS": "wagtail_ai.ai.llm.LLMBackend",
            "CONFIG": {
                "MODEL_ID": "llama2",
                "TOKEN_LIMIT": 4096,
            },
        }
    }
}
```

**Cost**: Free (electricity + compute resources)

---

## Common Tasks

### Enable AI in RichText Fields

**If field uses default features** (recommended):
```python
# No changes needed - AI is enabled by default
from wagtail.fields import RichTextField

class BlogPost(Page):
    body = RichTextField()  # AI button will appear
```

**If field has custom features**:
```python
# Add 'ai' to features list
from wagtail.fields import RichTextField

class BlogPost(Page):
    body = RichTextField(
        features=['bold', 'italic', 'link', 'ai']  # Add 'ai'
    )
```

---

### Generate Image Alt Text

**Automatic on upload** (v3.0 feature):
```python
# settings.py
WAGTAIL_AI = {
    "PROVIDERS": {
        "default": {
            "CLASS": "wagtail_ai.ai.openai.OpenAIBackend",  # Must support images
            "CONFIG": {"MODEL_ID": "gpt-4o"},
        }
    },
    "IMAGE_DESCRIPTION_PROVIDER": "default",  # Enable auto alt text
}
```

Now when uploading images in Wagtail admin, alt text is generated automatically.

---

### Custom Prompts

**v3.0 uses admin interface** (not settings):

1. Access Wagtail admin
2. Navigate to: **Settings > Prompts**
3. Add new prompt:
   - **Name**: `grammar_check`
   - **Prompt**: `Fix grammar and spelling in this text:`
   - **Active**: ✓

Prompts are now managed in the database, not `settings.py`.

---

### Cost Control

**Set token limits**:
```python
WAGTAIL_AI = {
    "PROVIDERS": {
        "default": {
            "CLASS": "wagtail_ai.ai.llm.LLMBackend",
            "CONFIG": {
                "MODEL_ID": "gpt-3.5-turbo",
                "TOKEN_LIMIT": 4096,  # Max context window
                "PROMPT_KWARGS": {
                    "max_tokens": 500,  # Max output length
                },
            },
        }
    }
}
```

**Monitor usage**:
- OpenAI: https://platform.openai.com/usage
- Anthropic: https://console.anthropic.com/settings/usage

---

## Troubleshooting

### AI Button Not Showing

**Fix 1**: Collect static files
```bash
python manage.py collectstatic --noinput
```

**Fix 2**: Hard refresh browser
```
Cmd+Shift+R (Mac) or Ctrl+Shift+F5 (Windows)
```

**Fix 3**: Check `features` list
```python
# Add 'ai' if using custom features
body = RichTextField(features=['bold', 'italic', 'ai'])
```

---

### "Invalid API Key" Error

**Fix 1**: Check environment variable
```bash
echo $OPENAI_API_KEY  # Should output your key
```

**Fix 2**: Restart Django server
```bash
# Environment variables require restart
python manage.py runserver
```

**Fix 3**: Verify key at provider
- OpenAI: https://platform.openai.com/account/api-keys
- Anthropic: https://console.anthropic.com/account/keys

---

### Slow Responses (>10s)

**Fix 1**: Switch to faster model
```python
# Fast: GPT-3.5 Turbo (~2s)
"MODEL_ID": "gpt-3.5-turbo"

# Fast: Claude Haiku (<1s)
"MODEL_ID": "claude-3-5-haiku"

# Slow: GPT-4 (5-10s)
"MODEL_ID": "gpt-4o"
```

**Fix 2**: Reduce content length
```python
# Only send first 2000 characters
content = page.body[:2000]
```

---

## Production Checklist

Before deploying to production:

- [ ] `DEBUG = False` in settings
- [ ] API keys in environment variables (not hardcoded)
- [ ] `.env` added to `.gitignore`
- [ ] HTTPS enabled (`SECURE_SSL_REDIRECT = True`)
- [ ] Database migrations applied (`python manage.py migrate`)
- [ ] Static files collected (`python manage.py collectstatic`)
- [ ] Cost monitoring enabled (provider dashboard)
- [ ] Error logging configured
- [ ] Privacy policy updated (mention AI processing)
- [ ] API key rotation scheduled (every 30-60 days)

---

## Next Steps

1. **Read full guide**: `WAGTAIL_AI_BEST_PRACTICES.md`
2. **Review provider terms**: Ensure GDPR/privacy compliance
3. **Set up monitoring**: Track costs and usage
4. **Implement caching**: Reduce duplicate API calls
5. **Test thoroughly**: Unit tests with mocked responses

---

## Quick Reference: Provider Comparison

| Feature | OpenAI | Claude | Local |
|---------|--------|--------|-------|
| **Setup** | Easy | Medium | Hard |
| **Cost** | Low-Med | Medium | Free |
| **Speed** | Fast | Fast | Slow |
| **Quality** | Excellent | Excellent | Good |
| **Privacy** | Moderate | High | Complete |
| **Best For** | Getting started | Production | Privacy |

---

## Getting Help

- **Wagtail AI Docs**: https://wagtail-ai.readthedocs.io/
- **GitHub Issues**: https://github.com/wagtail/wagtail-ai/issues
- **Wagtail Slack**: https://wagtail.org/slack/
- **Stack Overflow**: Tag `wagtail-ai`

---

**Created**: November 9, 2025
**Version**: 1.0.0
