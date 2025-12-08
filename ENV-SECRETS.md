# DigitalOcean App Platform - Required Secrets

## IMPORTANT: Add these secrets to DigitalOcean Console

These secrets need to be added via the DigitalOcean App Platform console:
https://cloud.digitalocean.com/apps → zkalphaflow → Settings → Environment Variables

### Required Secrets (Add as "SECRET" type)

#### Authentication
- **CLERK_SECRET_KEY**: Your Clerk production secret key
  - Get from: https://dashboard.clerk.com/last-active?path=api-keys
  - Format: Production keys for zkalphaflow.com domain

#### Database
- **DATABASE_URL**: (Will be auto-generated if using DigitalOcean managed database)
- **POSTGRES_HOST**: Your PostgreSQL host
- **POSTGRES_DB**: zkalphaflow
- **POSTGRES_USER**: Your database user
- **POSTGRES_PASSWORD**: Your database password

#### API Keys
- **WHALE_ALERT_API_KEY**: Your Whale Alert API key (check local .env file)
- **ALPHA_VANTAGE_API_KEY**: Your Alpha Vantage key (check local .env file)
- **ETHERSCAN_API_KEY**: Your Etherscan API key (check local .env file)
- **DUNE_API_KEY**: Your Dune Analytics key (check local .env file)

#### Optional API Keys (Add if available)
- **POLYGON_API_KEY**: (Get from https://polygon.io)
- **COINGECKO_API_KEY**: (Get from https://www.coingecko.com/api)
- **FINNHUB_API_KEY**: (Get from https://finnhub.io)
- **ALCHEMY_WS_URL**: `wss://eth-mainnet.g.alchemy.com/v2/YOUR_KEY`
- **ALCHEMY_API_KEY**: Your Alchemy API key
- **SOLANA_RPC_URL**: Your Solana RPC endpoint

#### Slack Integration
- **ALERTS_SLACK_WEBHOOK**: Your Slack webhook URL
- **SLACK_EDUCATOR_WEBHOOK_URL**: Slack webhook for course notifications
- **SLACK_BOT_TOKEN**: Slack bot OAuth token
- **SLACK_COURSE_WEBHOOK_URL**: Course-specific webhook

#### Monitoring
- **SENTRY_DSN**: Your Sentry DSN for error tracking

## How to Add Secrets

1. **Via DigitalOcean Console**:
   - Go to: https://cloud.digitalocean.com/apps
   - Click on "zkalphaflow"
   - Go to "Settings" → "App-Level Environment Variables"
   - Click "Edit" → "Add Variable"
   - Enter Key and Value
   - Set Type to "SECRET" (encrypts the value)
   - Click "Save"

2. **Via CLI**:
   ```bash
   doctl apps update [APP_ID] --env KEY=VALUE:SECRET
   ```

## Verify Secrets Are Set

After adding secrets, verify they're available:

```bash
# Check app configuration
doctl apps get [APP_ID] --format Spec.Services[0].Envs

# Test API with secrets
curl https://api.zkalphaflow.com/health
```

## Security Notes

- **NEVER** commit secrets to Git
- Always use DigitalOcean's SECRET type for sensitive values
- Rotate keys periodically
- Use different keys for development and production

## Production Checklist

- [ ] CLERK_SECRET_KEY added
- [ ] Database credentials configured
- [ ] API keys added as secrets
- [ ] Slack webhooks configured (if using)
- [ ] Redis connection configured (auto via ${redis.DATABASE_URL})
- [ ] Test deployment with `curl https://api.zkalphaflow.com/health`
