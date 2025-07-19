# PowerShell script for secure Docker image building
# Oikotie Daily Scraper Automation - Secure Build Process

param(
    [string]$ImageName = "oikotie-scraper",
    [string]$Tag = "latest",
    [string]$Target = "production",
    [switch]$SecurityScan = $true,
    [switch]$Push = $false
)

$ErrorActionPreference = "Stop"

Write-Host "🚀 Starting secure Docker build process..." -ForegroundColor Green
Write-Host "Image: $ImageName`:$Tag" -ForegroundColor Cyan
Write-Host "Target: $Target" -ForegroundColor Cyan

# Build the Docker image
Write-Host "🔨 Building Docker image..." -ForegroundColor Yellow
docker build --target $Target --tag "$ImageName`:$Tag" --tag "$ImageName`:latest" .

if ($LASTEXITCODE -ne 0) {
    Write-Error "Docker build failed!"
    exit 1
}

Write-Host "✅ Docker image built successfully!" -ForegroundColor Green

# Security scanning (if enabled)
if ($SecurityScan) {
    Write-Host "🔍 Running security scan..." -ForegroundColor Yellow
    
    # Check if Trivy is available
    try {
        $trivyVersion = docker run --rm aquasec/trivy:latest --version
        Write-Host "Using Trivy: $trivyVersion" -ForegroundColor Cyan
        
        # Run vulnerability scan
        Write-Host "🛡️ Scanning for vulnerabilities..." -ForegroundColor Yellow
        docker run --rm -v /var/run/docker.sock:/var/run/docker.sock `
            aquasec/trivy:latest image --exit-code 1 --severity HIGH,CRITICAL "$ImageName`:$Tag"
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ No critical vulnerabilities found!" -ForegroundColor Green
        } else {
            Write-Warning "⚠️ Critical vulnerabilities detected! Review before deployment."
        }
        
        # Generate detailed report
        $reportFile = "security-report-$Tag-$(Get-Date -Format 'yyyyMMdd-HHmmss').json"
        docker run --rm -v /var/run/docker.sock:/var/run/docker.sock `
            -v "${PWD}:/output" aquasec/trivy:latest image --format json --output "/output/$reportFile" "$ImageName`:$Tag"
        
        Write-Host "📄 Security report saved to: $reportFile" -ForegroundColor Cyan
        
    } catch {
        Write-Warning "⚠️ Security scanning failed: $_"
    }
}

# Image analysis
Write-Host "📊 Analyzing image..." -ForegroundColor Yellow
$imageInfo = docker images "$ImageName`:$Tag" --format "table {{.Repository}}:{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}"
Write-Host $imageInfo -ForegroundColor Cyan

# Test image functionality
Write-Host "🧪 Testing image functionality..." -ForegroundColor Yellow
try {
    $testResult = docker run --rm "$ImageName`:$Tag" python -c "import oikotie; print('✅ Package import successful')"
    Write-Host $testResult -ForegroundColor Green
} catch {
    Write-Warning "⚠️ Image functionality test failed: $_"
}

# Push to registry (if enabled)
if ($Push) {
    Write-Host "📤 Pushing image to registry..." -ForegroundColor Yellow
    docker push "$ImageName`:$Tag"
    docker push "$ImageName`:latest"
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Image pushed successfully!" -ForegroundColor Green
    } else {
        Write-Error "Failed to push image to registry!"
    }
}

Write-Host "🎉 Secure build process completed!" -ForegroundColor Green
Write-Host "Image ready: $ImageName`:$Tag" -ForegroundColor Cyan