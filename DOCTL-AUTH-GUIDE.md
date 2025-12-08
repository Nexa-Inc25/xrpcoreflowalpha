# DigitalOcean CLI Authentication Guide

## Fix for "Unable to authenticate you" Error

### Quick Fix - Authenticate doctl

1. **Generate a Personal Access Token**:
   - Go to: https://cloud.digitalocean.com/account/api/tokens
   - Click "Generate New Token"
   - Name it: "doctl-access" (or any name)
   - Select scopes: Read and Write
   - Click "Generate Token"
   - **COPY THE TOKEN IMMEDIATELY** (it won't be shown again)

2. **Authenticate doctl**:
   ```bash
   doctl auth init
   ```
   - Paste your token when prompted
   - Press Enter

3. **Verify Authentication**:
   ```bash
   doctl account get
   ```

### Alternative: Use Environment Variable

Set the token as an environment variable:
```bash
export DIGITALOCEAN_ACCESS_TOKEN="your-token-here"
doctl auth init -t $DIGITALOCEAN_ACCESS_TOKEN
```

### Now You Can Run Registry Commands

```bash
# List registry repositories
doctl registry repository list-v2

# Get registry info
doctl registry get

# List tags for a repository
doctl registry repository list-tags zkalphaflow/api
doctl registry repository list-tags zkalphaflow/web
```

### Check App Status

```bash
# List all apps
doctl apps list

# Get app details
doctl apps get zkalphaflow

# Get recent deployments
doctl apps list-deployments zkalphaflow

# View logs
doctl apps logs zkalphaflow --follow
```

### Useful Commands After Authentication

```bash
# See what's in your registry
doctl registry repository list-v2

# Check garbage collection status
doctl registry garbage-collection get-active

# Get registry usage
doctl registry get

# Check app deployment status
doctl apps get zkalphaflow --format ID,ActiveDeployment.Phase,UpdatedAt
```

### Add Token to GitHub Secrets

For CI/CD to work, add your token to GitHub:
1. Go to: https://github.com/Nexa-Inc25/xrpcoreflowalpha/settings/secrets/actions
2. Click "New repository secret"
3. Name: `DIGITALOCEAN_ACCESS_TOKEN`
4. Value: Your access token
5. Click "Add secret"

Also add the App ID:
1. Get the app ID: `doctl apps list --format ID,Spec.Name`
2. Add as secret: `APP_ID`
3. Value: The ID from the command above

### Troubleshooting

If you still get authentication errors:

1. **Check token validity**:
   ```bash
   doctl auth list
   ```

2. **Remove old contexts**:
   ```bash
   doctl auth remove --context default
   doctl auth init
   ```

3. **Use a specific context**:
   ```bash
   doctl auth init --context production
   doctl auth switch --context production
   ```

4. **Check current context**:
   ```bash
   doctl auth list
   doctl auth current
   ```

### Security Notes

- **Never commit tokens** to Git
- Rotate tokens periodically
- Use read-only tokens when possible
- Store tokens in password managers

### Required Permissions for Registry

Your token needs these scopes:
- ✅ Read access
- ✅ Write access (for pushing images)
