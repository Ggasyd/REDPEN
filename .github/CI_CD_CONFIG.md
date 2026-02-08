# CI/CD Configuration

## Environment Variables for Testing

This document explains the environment variables used in the GitHub Actions CI/CD pipeline.

### Database & Cache

- **DATABASE_URL**: PostgreSQL connection for tests (uses in-memory or service container)
- **REDIS_URL**: Redis connection for Celery and caching

### Authentication

- **SECRET_KEY**: JWT secret for token generation (dummy value for tests)

### Storage Configuration

- **STORAGE_TYPE**: `minio` (MinIO for local/test, S3 for production)
- **MINIO_ENDPOINT**: MinIO server endpoint
- **MINIO_ACCESS_KEY**: MinIO access credentials (dummy for CI/CD)
- **MINIO_SECRET_KEY**: MinIO secret credentials (dummy for CI/CD)
- **MINIO_SECURE**: Use HTTPS for MinIO connection
- **MINIO_BUCKET_NAME**: Default bucket name for storage

### AI Service Keys (Dummy Values for CI/CD)

**⚠️ IMPORTANT**: The API keys in `.github/workflows/ci.yml` are **DUMMY VALUES** for testing only.

- **OPENAI_API_KEY**: `sk-test-dummy-key-for-ci-cd-testing-only-not-real`
  - Not a real OpenAI API key
  - Tests that require actual API calls should be mocked
  
- **GOOGLE_API_KEY**: `AIzaTest-Dummy-Google-API-Key-For-CI-CD-Testing`
  - Not a real Google AI API key
  - Gemini API calls should be mocked in tests
  
- **MISTRAL_API_KEY**: `test-dummy-mistral-key-for-ci-cd-pipeline`
  - Not a real Mistral API key
  - OCR service calls should be mocked in tests

### AI Model Configuration

- **OPENAI_MODEL**: `gpt-4o-mini` (model name for OpenAI calls)
- **GEMINI_MODEL**: `gemini-1.5-flash` (model name for Google calls)
- **MISTRAL_OCR_MODEL**: `pixtral-12b-2409` (model name for Mistral OCR)

### Celery Configuration

- **CELERY_BROKER_URL**: Redis URL for Celery message broker
- **CELERY_RESULT_BACKEND**: Redis URL for Celery result storage

### CORS

- **CORS_ORIGINS**: JSON array of allowed CORS origins

### GDPR Defaults

- **DEFAULT_RETENTION_SUBMISSIONS_DAYS**: Default retention period for submissions (730 days = 2 years)
- **DEFAULT_RETENTION_ARTIFACTS_DAYS**: Default retention period for artifacts (365 days = 1 year)
- **DEFAULT_RETENTION_ML_DAYS**: Default retention period for ML datasets (365 days = 1 year)

## Testing Strategy

### Unit Tests

Unit tests do **NOT** make real API calls. All external services are mocked:

```python
# Example: Mocking OpenAI API in tests
@pytest.fixture
def mock_openai(monkeypatch):
    def mock_create(*args, **kwargs):
        return MockResponse(...)
    monkeypatch.setattr("openai.ChatCompletion.create", mock_create)
```

### Integration Tests

Integration tests may use:
- Real PostgreSQL (via Docker service)
- Real Redis (via Docker service)
- **Mocked** AI services (no real API calls)
- **Mocked** storage (no real MinIO/S3)

### Production Keys

**Real API keys should NEVER be committed to the repository.**

For production deployment:
1. Use GitHub Secrets for sensitive values
2. Configure via environment variables in deployment platform
3. Use secret management services (AWS Secrets Manager, Azure Key Vault, etc.)

## GitHub Secrets Setup (Optional)

If you need to test with real API keys in CI/CD:

1. Go to: Repository → Settings → Secrets and variables → Actions
2. Add secrets:
   - `OPENAI_API_KEY_PROD`
   - `GOOGLE_API_KEY_PROD`
   - `MISTRAL_API_KEY_PROD`
3. Update workflow to use secrets:

```yaml
env:
  OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY_PROD }}
  GOOGLE_API_KEY: ${{ secrets.GOOGLE_API_KEY_PROD }}
  MISTRAL_API_KEY: ${{ secrets.MISTRAL_API_KEY_PROD }}
```

**Note**: Current tests work with dummy keys because external APIs are mocked.

## Security Best Practices

✅ **DO**:
- Use mocked services in tests
- Store real keys in GitHub Secrets
- Rotate API keys regularly
- Use different keys for dev/staging/prod
- Monitor API usage and costs

❌ **DON'T**:
- Commit real API keys to repository
- Use production keys in CI/CD tests
- Share API keys in logs or error messages
- Hardcode sensitive values in code

## Troubleshooting

### Tests fail with "Invalid API key"

- Check if the test is properly mocking external API calls
- Verify that dummy keys are being used (not real ones)
- Ensure mocking is set up before the test runs

### Environment variable not found

- Check that the variable is defined in `.github/workflows/ci.yml`
- Verify the variable name matches exactly (case-sensitive)
- Ensure quotes are used for string values with special characters

### Permission denied errors

- Check GitHub Actions permissions in repository settings
- Verify that the workflow has necessary permissions
- Check if secrets are accessible to the workflow
