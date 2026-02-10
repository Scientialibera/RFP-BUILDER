# ============================================================================
# RFP Builder Backend Deployment Script
# ============================================================================
# Deploys the RFP Builder API to Azure Web App (Linux)
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
$TENANT_ID = "da48a11d-a542-482e-b762-ed2f7db76734"
$SUBSCRIPTION_ID = "02562ae4-c185-435a-98a1-f5243be83a16"

if ($Environment -eq "dev") {
    $RG = "AURA-Bot"
    $ACR_NAME = "auraboreg"
    $WEBAPP_NAME = "aurabot-api-dev"
    $IMAGE_TAG = "dev"
    $FRONTEND_URL = "https://aurabot-web-dev.azurewebsites.net"
}
else {
    $RG = "REPLACE_WITH_PROD_RG"
    $ACR_NAME = "REPLACE_WITH_PROD_ACR_NAME"
    $WEBAPP_NAME = "REPLACE_WITH_PROD_WEBAPP"
    $IMAGE_TAG = "prod"
    $FRONTEND_URL = "REPLACE_WITH_PROD_FRONTEND_URL"
}

$ACR_URL = "$ACR_NAME.azurecr.io"
$IMAGE_NAME = "rfp-builder-api"
$FULL_IMAGE = "$ACR_URL/${IMAGE_NAME}:$IMAGE_TAG"
$API_PORT = 8000

# Get paths
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")

# ============================================================================
# MAIN
# ============================================================================

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "RFP Builder Backend Deployment - $($Environment.ToUpper())" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Configuration:" -ForegroundColor Yellow
Write-Host "  Resource Group: $RG"
Write-Host "  Web App: $WEBAPP_NAME"
Write-Host "  ACR: $ACR_NAME"
Write-Host "  Image: $FULL_IMAGE"
Write-Host "  CORS: $FRONTEND_URL"
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
    
    docker build -t "${IMAGE_NAME}:$IMAGE_TAG" -f backend/Dockerfile .
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
    
    Write-Host "[OK] Container configured: $FULL_IMAGE" -ForegroundColor Green
    
    # Build environment variables
    Write-Host ""
    Write-Host "Setting environment variables..." -ForegroundColor Yellow
    
    $envVars = @(
        "WEBSITES_PORT=$API_PORT",
        "RFP_CORS_ALLOWED_ORIGINS=$FRONTEND_URL,http://localhost:3000,http://localhost:5173"
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
Write-Host "Backend Deployment Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "API URL: https://$WEBAPP_NAME.azurewebsites.net" -ForegroundColor Cyan
Write-Host "Health:  https://$WEBAPP_NAME.azurewebsites.net/health" -ForegroundColor Cyan
Write-Host "Docs:    https://$WEBAPP_NAME.azurewebsites.net/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "Check logs:" -ForegroundColor Yellow
Write-Host "  az webapp log tail -g $RG -n $WEBAPP_NAME"
Write-Host ""
