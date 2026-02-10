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
    [switch]$SkipConfig,
    [switch]$SkipRoleAssignments,
    [string]$ConfigPath = ""
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
    $FRONTEND_URL = ""
    $OPENAI_ACCOUNT_NAME = ""
    $BLOB_ACCOUNT_NAME = ""
}
else {
    $RG = "REPLACE_WITH_PROD_RG"
    $ACR_NAME = "REPLACE_WITH_PROD_ACR_NAME"
    $WEBAPP_NAME = "REPLACE_WITH_PROD_WEBAPP"
    $IMAGE_TAG = "prod"
    $FRONTEND_URL = "REPLACE_WITH_PROD_FRONTEND_URL"
    $OPENAI_ACCOUNT_NAME = "REPLACE_WITH_PROD_OPENAI_ACCOUNT_NAME"
    $BLOB_ACCOUNT_NAME = "REPLACE_WITH_PROD_BLOB_ACCOUNT_NAME"
}

$ACR_URL = "$ACR_NAME.azurecr.io"
$IMAGE_NAME = "rfp-builder-api"
$FULL_IMAGE = "$ACR_URL/${IMAGE_NAME}:$IMAGE_TAG"
$API_PORT = 8000

# Get paths
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")
if ([string]::IsNullOrWhiteSpace($ConfigPath)) {
    $ConfigPath = Join-Path $repoRoot "config.toml"
}

function Get-ConfigTomlAppSettings {
    param(
        [Parameter(Mandatory=$true)]
        [string]$TomlPath
    )

    if (-not (Test-Path $TomlPath)) {
        Write-Warning "Config file not found at $TomlPath; skipping config.toml-derived app settings."
        return @()
    }

    $pythonScript = @'
import json
import base64
import pathlib
import sys

cfg_path = pathlib.Path(sys.argv[1])
try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

with cfg_path.open("rb") as f:
    data = tomllib.load(f)

settings = {}

def flatten(prefix, value):
    if isinstance(value, dict):
        for k, v in value.items():
            key = f"{prefix}__{k}" if prefix else str(k)
            flatten(key, v)
    else:
        if isinstance(value, bool):
            serialized = "true" if value else "false"
        elif value is None:
            serialized = ""
        elif isinstance(value, (list, dict)):
            payload = json.dumps(value, separators=(",", ":")).encode("utf-8")
            serialized = "__JSON_B64__" + base64.b64encode(payload).decode("ascii")
        else:
            serialized = str(value)
        settings[prefix.upper()] = serialized

for section, section_value in data.items():
    flatten(str(section), section_value)

print(json.dumps(settings))
'@

    $json = $pythonScript | python - $TomlPath
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($json)) {
        throw "Failed to parse config.toml at $TomlPath"
    }

    $parsed = $json | ConvertFrom-Json
    $envSettings = @()
    foreach ($prop in $parsed.PSObject.Properties) {
        $key = [string]$prop.Name
        $value = [string]$prop.Value
        $envSettings += "${key}=${value}"
    }
    return $envSettings
}

function Ensure-RoleAssignment {
    param(
        [Parameter(Mandatory=$true)]
        [string]$PrincipalId,
        [Parameter(Mandatory=$true)]
        [string]$RoleName,
        [Parameter(Mandatory=$true)]
        [string]$Scope
    )
    $existingCountRaw = az role assignment list `
        --assignee-object-id $PrincipalId `
        --scope $Scope `
        --query "[?roleDefinitionName=='$RoleName'] | length(@)" `
        -o tsv 2>$null

    $existingCount = 0
    if (-not [string]::IsNullOrWhiteSpace($existingCountRaw)) {
        [int]::TryParse($existingCountRaw, [ref]$existingCount) | Out-Null
    }

    if ($existingCount -gt 0) {
        Write-Host "[OK] Role exists: $RoleName @ $Scope" -ForegroundColor Green
        return
    }

    az role assignment create `
        --assignee-object-id $PrincipalId `
        --assignee-principal-type ServicePrincipal `
        --role $RoleName `
        --scope $Scope `
        -o none | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] Role assigned: $RoleName @ $Scope" -ForegroundColor Green
    }
    else {
        Write-Warning "Role assignment failed: $RoleName @ $Scope"
    }
}

function Clear-AppCommandLine {
    param(
        [Parameter(Mandatory=$true)]
        [string]$ResourceGroup,
        [Parameter(Mandatory=$true)]
        [string]$WebAppName
    )
    $configId = (az webapp config show -g $ResourceGroup -n $WebAppName --query "id" -o tsv 2>$null).Trim()
    if ([string]::IsNullOrWhiteSpace($configId)) {
        Write-Warning "Could not resolve config id to clear appCommandLine for $WebAppName."
        return
    }
    az resource update --ids $configId --set properties.appCommandLine="" -o none | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] Cleared startup command override (appCommandLine)" -ForegroundColor Green
    }
    else {
        Write-Warning "Failed to clear appCommandLine for $WebAppName."
    }
}

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
Write-Host "  Config TOML: $ConfigPath"
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

    Clear-AppCommandLine -ResourceGroup $RG -WebAppName $WEBAPP_NAME

    Write-Host "[OK] Container configured: $FULL_IMAGE" -ForegroundColor Green
    
    # Build environment variables
    Write-Host ""
    Write-Host "Setting environment variables..." -ForegroundColor Yellow
    
    $envVars = @(
        "WEBSITES_PORT=$API_PORT",
        "RFP_CORS_ALLOWED_ORIGINS=$FRONTEND_URL,http://localhost:3000,http://localhost:5173"
    )

    $tomlEnvVars = Get-ConfigTomlAppSettings -TomlPath $ConfigPath
    if ($tomlEnvVars.Count -gt 0) {
        Write-Host "[OK] Loaded $($tomlEnvVars.Count) setting(s) from config.toml" -ForegroundColor Green
        $envVars += $tomlEnvVars
    }
    
    # Apply settings in batch
    az webapp config appsettings set -g $RG -n $WEBAPP_NAME --settings $envVars | Out-Null
    
    Write-Host "[OK] Environment variables configured" -ForegroundColor Green
    
    # Restart to pick up changes
    Write-Host ""
    Write-Host "Restarting Web App..." -ForegroundColor Yellow
    az webapp restart -g $RG -n $WEBAPP_NAME | Out-Null
    Write-Host "[OK] Web App restarted" -ForegroundColor Green
}

if (-not $SkipRoleAssignments) {
    Write-Host ""
    Write-Host "Applying managed identity role assignments..." -ForegroundColor Yellow

    $principalId = (az webapp show -g $RG -n $WEBAPP_NAME --query "identity.principalId" -o tsv).Trim()
    if ([string]::IsNullOrWhiteSpace($principalId)) {
        Write-Warning "No system-assigned identity found on $WEBAPP_NAME. Skipping role assignments."
    }
    else {
        $openAiResourceId = ""
        $storageResourceId = ""
        if (-not [string]::IsNullOrWhiteSpace($OPENAI_ACCOUNT_NAME)) {
            $openAiResourceId = (az cognitiveservices account show -g $RG -n $OPENAI_ACCOUNT_NAME --query "id" -o tsv 2>$null).Trim()
        }
        if (-not [string]::IsNullOrWhiteSpace($BLOB_ACCOUNT_NAME)) {
            $storageResourceId = (az storage account show -g $RG -n $BLOB_ACCOUNT_NAME --query "id" -o tsv 2>$null).Trim()
        }
        $acrResourceId = (az acr show -g $RG -n $ACR_NAME --query "id" -o tsv 2>$null).Trim()

        if (-not [string]::IsNullOrWhiteSpace($openAiResourceId)) {
            Ensure-RoleAssignment -PrincipalId $principalId -RoleName "Cognitive Services OpenAI User" -Scope $openAiResourceId
        }
        else {
            Write-Warning "Could not resolve OpenAI resource id. Set OPENAI_ACCOUNT_NAME for this environment."
        }

        if (-not [string]::IsNullOrWhiteSpace($storageResourceId)) {
            Ensure-RoleAssignment -PrincipalId $principalId -RoleName "Storage Blob Data Contributor" -Scope $storageResourceId
        }
        else {
            Write-Warning "Could not resolve storage account id. Set BLOB_ACCOUNT_NAME for this environment."
        }

        if (-not [string]::IsNullOrWhiteSpace($acrResourceId)) {
            Ensure-RoleAssignment -PrincipalId $principalId -RoleName "AcrPull" -Scope $acrResourceId
        }
        else {
            Write-Warning "Could not resolve ACR resource id ($ACR_NAME)."
        }
    }
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
