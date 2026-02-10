# ============================================================================
# RFP Builder Frontend Deployment Script
# ============================================================================
# Deploys the RFP Builder React Frontend to Azure Web App (Linux)
# Prerequisites:
#   - Azure CLI authenticated (az login)
#   - Docker installed
#   - PowerShell 7+
# ============================================================================

param(
    [Parameter(Mandatory=$false)]
    [ValidateSet("dev", "prod")]
    [string]$Environment = "dev",
    
    [switch]$SkipDockerBuild,
    [switch]$SkipPush,
    [switch]$SkipConfig
)

$ErrorActionPreference = "Stop"

# ============================================================================
# CONFIGURATION
# ============================================================================

# TODO: Replace these with your real values
$TENANT_ID = ""
$SUBSCRIPTION_ID = ""

if ($Environment -eq "dev") {
    $RG = ""
    $ACR_NAME = ""
    $WEBAPP_NAME = ""
    $IMAGE_TAG = "dev"
    $API_URL = ""
}
else {
    $RG = "REPLACE_WITH_PROD_RG"
    $ACR_NAME = "REPLACE_WITH_PROD_ACR_NAME"
    $WEBAPP_NAME = "REPLACE_WITH_PROD_WEBAPP"
    $IMAGE_TAG = "prod"
    $API_URL = "REPLACE_WITH_PROD_API_URL/api"
}

$ACR_URL = "$ACR_NAME.azurecr.io"
$IMAGE_NAME = "rfp-builder-frontend"
$FULL_IMAGE = "$ACR_URL/${IMAGE_NAME}:$IMAGE_TAG"

# Get paths
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")

# ============================================================================
# MAIN
# ============================================================================

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "RFP Builder Frontend Deployment - $($Environment.ToUpper())" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Configuration:" -ForegroundColor Yellow
Write-Host "  Resource Group: $RG"
Write-Host "  Web App: $WEBAPP_NAME"
Write-Host "  ACR: $ACR_NAME"
Write-Host "  Image: $FULL_IMAGE"
Write-Host "  API URL: $API_URL"
Write-Host ""

# Set subscription
Write-Host "Setting Azure subscription..." -ForegroundColor Yellow
az account set --subscription $SUBSCRIPTION_ID
if ($LASTEXITCODE -ne 0) { Write-Error "Failed to set subscription"; exit 1 }
Write-Host "[OK] Subscription set" -ForegroundColor Green

# ============================================================================
# DOCKER BUILD & PUSH
# ============================================================================

if (-not $SkipDockerBuild) {
    Write-Host ""
    Write-Host "Building Docker image..." -ForegroundColor Yellow
    
    Push-Location $repoRoot
    
    docker build -t "${IMAGE_NAME}:$IMAGE_TAG" `
        --build-arg VITE_API_BASE_URL=$API_URL `
        -f frontend/Dockerfile .
    
    if ($LASTEXITCODE -ne 0) { Pop-Location; Write-Error "Docker build failed"; exit 1 }
    
    Write-Host "[OK] Docker image built: ${IMAGE_NAME}:$IMAGE_TAG" -ForegroundColor Green
    
    if (-not $SkipPush) {
        Write-Host ""
        Write-Host "Pushing to ACR..." -ForegroundColor Yellow
        
        az acr login --name $ACR_NAME
        if ($LASTEXITCODE -ne 0) { Pop-Location; Write-Error "ACR login failed"; exit 1 }
        
        docker tag "${IMAGE_NAME}:$IMAGE_TAG" $FULL_IMAGE
        docker push $FULL_IMAGE
        if ($LASTEXITCODE -ne 0) { Pop-Location; Write-Error "Docker push failed"; exit 1 }
        
        Write-Host "[OK] Image pushed: $FULL_IMAGE" -ForegroundColor Green
    }
    
    Pop-Location
}

# ============================================================================
# CONFIGURE WEB APP
# ============================================================================

if (-not $SkipConfig) {
    Write-Host ""
    Write-Host "Configuring Web App..." -ForegroundColor Yellow
    
    # Ensure ACR credentials are set for image pull
    $acrCreds = az acr credential show -n $ACR_NAME --query "{username:username, password:passwords[0].value}" -o json | ConvertFrom-Json

    # Set container image
    az webapp config container set -g $RG -n $WEBAPP_NAME `
        --container-image-name $FULL_IMAGE `
        --container-registry-url "https://$ACR_URL" `
        --container-registry-user $acrCreds.username `
        --container-registry-password $acrCreds.password | Out-Null

    # Clear stale startup command so Dockerfile CMD/ENTRYPOINT is used.
    $configId = (az webapp config show -g $RG -n $WEBAPP_NAME --query "id" -o tsv 2>$null).Trim()
    if (-not [string]::IsNullOrWhiteSpace($configId)) {
        az resource update --ids $configId --set properties.appCommandLine="" -o none | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[OK] Cleared startup command override (appCommandLine)" -ForegroundColor Green
        }
        else {
            Write-Warning "Failed to clear appCommandLine for $WEBAPP_NAME."
        }
    }
    else {
        Write-Warning "Could not resolve config id to clear appCommandLine for $WEBAPP_NAME."
    }

    Write-Host "[OK] Container configured: $FULL_IMAGE" -ForegroundColor Green
    
    # Build environment variables (runtime overrides if needed)
    Write-Host ""
    Write-Host "Setting environment variables..." -ForegroundColor Yellow
    
    $envVars = @(
        "WEBSITES_ENABLE_APP_SERVICE_STORAGE=false",
        "DOCKER_ENABLE_CI=true",
        "WEBSITES_PORT=80",
        "VITE_API_BASE_URL=$API_URL"
    )
    
    # Apply settings in batch
    az webapp config appsettings set -g $RG -n $WEBAPP_NAME --settings $envVars | Out-Null
    
    Write-Host "[OK] Environment variables configured" -ForegroundColor Green
    
    # Restart to pick up changes
    Write-Host ""
    Write-Host "Restarting Web App..." -ForegroundColor Yellow
    az webapp restart -g $RG -n $WEBAPP_NAME | Out-Null
    Write-Host "[OK] Web App restarted" -ForegroundColor Green
}

# ============================================================================
# SUMMARY
# ============================================================================

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Frontend Deployment Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Frontend URL: https://$WEBAPP_NAME.azurewebsites.net" -ForegroundColor Cyan
Write-Host ""
Write-Host "Check logs:" -ForegroundColor Yellow
Write-Host "  az webapp log tail -g $RG -n $WEBAPP_NAME"
Write-Host ""
