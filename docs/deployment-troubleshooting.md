# DigitalOcean Deployment Troubleshooting Guide

## Resolving "Build Job Skipped" Due to Pre-Built Image Configuration

### Problem
The error "[web]: Your build job was skipped because you specified a pre-built image" occurs when a component is configured to deploy from a container registry instead of building from source code.

### Solution

#### 1. Via DigitalOcean Console (Recommended)

1. **Access App Settings**
   ```
   1. Log into DigitalOcean Console
   2. Navigate to Apps → zkalphaflow
   3. Click on "Settings" tab
   ```

2. **Edit Component Source**
   ```
   1. Find the component showing "Image" as source (usually "web" or "api")
   2. Click "Edit" next to the component
   3. Change Source from "DigitalOcean Container Registry" to "GitHub"
   4. Select repository: Nexa-Inc25/xrpcoreflowalpha
   5. Set branch: main
   6. Set source directory (if needed):
      - For API: / (root)
      - For Web: apps/web
   ```

3. **Configure Build Settings**
   ```
   Build Command (Web): npm run build
   Run Command (Web): npm start
   
   Build Command (API): (leave default)
   Run Command (API): uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
   ```

4. **Save and Deploy**
   ```
   1. Click "Save"
   2. This will trigger a new deployment from source
   ```

#### 2. Via CLI (Alternative)

```bash
# Authenticate
doctl auth init

# Get app ID
APP_ID=$(doctl apps list --format ID,Spec.Name --no-header | grep "zkalphaflow" | awk '{print $1}')

# Update app spec
doctl apps update $APP_ID --spec .do/app.yaml --wait

# Force rebuild
doctl apps create-deployment $APP_ID --force-rebuild
```

#### 3. Via Deployment Script

```bash
# Make script executable
chmod +x deploy.sh

# Run deployment
./deploy.sh
```

### Common Issues and Fixes

#### Issue: Build fails with missing dependencies

**Solution**: Update `requirements.txt`
```python
# Add missing packages
polygon-api-client==1.13.2
slack-bolt==1.18.1
prophet==1.1.5
```

#### Issue: Port binding error

**Solution**: Use DigitalOcean's PORT env variable
```dockerfile
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
```

#### Issue: Health check failures

**Solution**: Add health endpoint
```python
# app/main.py
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}
```

#### Issue: Environment variables not available

**Solution**: Add to `.do/app.yaml`
```yaml
envs:
  - key: POLYGON_API_KEY
    type: SECRET
  - key: SLACK_BOT_TOKEN
    type: SECRET
  - key: ENABLE_EQUITY_CORRELATION
    value: "true"
```

### Verifying Deployment

#### 1. Check Build Logs
```bash
# Get recent deployment ID
DEPLOYMENT_ID=$(doctl apps list-deployments $APP_ID --format ID --no-header | head -1)

# View build logs
doctl apps logs $APP_ID --deployment $DEPLOYMENT_ID --type BUILD
```

#### 2. Test Endpoints

```bash
# Health check
curl https://api.zkalphaflow.com/health

# Multi-asset correlations
curl "https://api.zkalphaflow.com/analytics/heatmap?assets=xrp,btc,spy"

# Real-time flow state
curl https://api.zkalphaflow.com/dashboard/flow_state

# SSE stream (will stay open)
curl -N https://api.zkalphaflow.com/events/sse
```

#### 3. Monitor Real-Time Logs
```bash
# All components
doctl apps logs $APP_ID --follow

# Specific component
doctl apps logs $APP_ID --component api --follow
```

### Build Optimization Tips

1. **Use Multi-Stage Dockerfile**
   - Reduces image size
   - Separates build dependencies from runtime

2. **Cache Dependencies**
   ```dockerfile
   COPY requirements.txt ./
   RUN pip install -r requirements.txt
   COPY . .
   ```

3. **Set Resource Limits**
   ```yaml
   instance_size_slug: basic-xs  # 512MB RAM, 1 vCPU
   instance_count: 1
   ```

4. **Enable Auto-Deploy**
   ```yaml
   github:
     deploy_on_push: true
     branch: main
   ```

### Monitoring and Alerts

#### Slack Notifications
Configure in `.do/app.yaml`:
```yaml
envs:
  - key: SLACK_WEBHOOK_URL
    type: SECRET
  - key: ENABLE_SLACK_ALERTS
    value: "true"
```

#### Health Monitoring
```python
# services/health_monitor.py
async def check_services():
    checks = {
        "redis": await check_redis(),
        "postgres": await check_postgres(),
        "xrpl": await check_xrpl_connection(),
        "polygon": await check_polygon_api()
    }
    return checks
```

### Rollback Procedure

If deployment fails:

1. **Via Console**
   ```
   Apps → zkalphaflow → Activity → Previous Deployment → Rollback
   ```

2. **Via CLI**
   ```bash
   # List recent deployments
   doctl apps list-deployments $APP_ID
   
   # Rollback to previous
   doctl apps create-deployment $APP_ID --previous
   ```

### Performance Optimization

1. **Enable Redis Caching**
   ```yaml
   databases:
     - name: redis
       engine: REDIS
       version: "7"
       production: true
   ```

2. **Configure CDN for Static Assets**
   ```yaml
   cdn:
     enabled: true
   ```

3. **Set Up Horizontal Scaling**
   ```yaml
   instance_count: 2  # Scale to 2 instances
   ```

### Contact Support

If issues persist:
1. Check DigitalOcean Status: https://status.digitalocean.com
2. Review App Platform docs: https://docs.digitalocean.com/products/app-platform/
3. Contact support with:
   - App ID
   - Deployment ID
   - Error logs
   - `.do/app.yaml` configuration
