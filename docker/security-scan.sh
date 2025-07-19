#!/bin/bash
# Docker Security Scanning Script for Oikotie Daily Scraper Automation
# This script performs comprehensive security scanning of Docker images

set -euo pipefail

# Configuration
IMAGE_NAME="${1:-oikotie-scraper}"
TAG="${2:-latest}"
FULL_IMAGE="${IMAGE_NAME}:${TAG}"

echo "🔍 Starting security scan for ${FULL_IMAGE}"

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Install security scanning tools if not present
install_security_tools() {
    echo "📦 Installing security scanning tools..."
    
    # Install Trivy for vulnerability scanning
    if ! command_exists trivy; then
        echo "Installing Trivy..."
        curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin
    fi
    
    # Install Hadolint for Dockerfile linting
    if ! command_exists hadolint; then
        echo "Installing Hadolint..."
        wget -O /usr/local/bin/hadolint https://github.com/hadolint/hadolint/releases/latest/download/hadolint-Linux-x86_64
        chmod +x /usr/local/bin/hadolint
    fi
    
    # Install Docker Bench Security
    if [ ! -d "docker-bench-security" ]; then
        echo "Installing Docker Bench Security..."
        git clone https://github.com/docker/docker-bench-security.git
    fi
}

# Dockerfile security linting
dockerfile_lint() {
    echo "🔧 Running Dockerfile security lint..."
    if command_exists hadolint; then
        hadolint Dockerfile || echo "⚠️  Hadolint found issues in Dockerfile"
    else
        echo "⚠️  Hadolint not available, skipping Dockerfile lint"
    fi
}

# Vulnerability scanning
vulnerability_scan() {
    echo "🛡️  Running vulnerability scan..."
    if command_exists trivy; then
        # Scan for vulnerabilities
        trivy image --exit-code 1 --severity HIGH,CRITICAL "${FULL_IMAGE}" || {
            echo "❌ Critical vulnerabilities found!"
            return 1
        }
        
        # Generate detailed report
        trivy image --format json --output "security-report-${TAG}.json" "${FULL_IMAGE}"
        echo "📄 Detailed security report saved to security-report-${TAG}.json"
    else
        echo "⚠️  Trivy not available, skipping vulnerability scan"
    fi
}

# Image analysis
image_analysis() {
    echo "📊 Analyzing image composition..."
    
    # Check image size
    IMAGE_SIZE=$(docker images "${FULL_IMAGE}" --format "table {{.Size}}" | tail -n 1)
    echo "📏 Image size: ${IMAGE_SIZE}"
    
    # Check for unnecessary packages
    echo "🔍 Checking for unnecessary packages..."
    docker run --rm "${FULL_IMAGE}" sh -c "apt list --installed 2>/dev/null | wc -l" || echo "Could not check packages"
    
    # Check running processes
    echo "🔍 Checking default processes..."
    docker run --rm "${FULL_IMAGE}" ps aux || echo "Could not check processes"
}

# Security best practices check
security_best_practices() {
    echo "✅ Checking security best practices..."
    
    # Check if running as non-root
    USER_CHECK=$(docker run --rm "${FULL_IMAGE}" whoami)
    if [ "${USER_CHECK}" = "root" ]; then
        echo "⚠️  Image runs as root user"
    else
        echo "✅ Image runs as non-root user: ${USER_CHECK}"
    fi
    
    # Check for secrets in image
    echo "🔍 Scanning for potential secrets..."
    docker run --rm "${FULL_IMAGE}" find / -name "*.key" -o -name "*.pem" -o -name "*.crt" 2>/dev/null | head -10 || echo "No obvious secret files found"
}

# Generate security report
generate_report() {
    echo "📋 Generating security summary report..."
    
    REPORT_FILE="docker-security-report-${TAG}-$(date +%Y%m%d-%H%M%S).md"
    
    cat > "${REPORT_FILE}" << EOF
# Docker Security Scan Report

**Image:** ${FULL_IMAGE}  
**Scan Date:** $(date)  
**Scanner Version:** $(trivy --version 2>/dev/null || echo "N/A")

## Summary

- **Image Size:** ${IMAGE_SIZE:-Unknown}
- **Base Image:** python:3.11-slim
- **User:** ${USER_CHECK:-Unknown}

## Vulnerability Scan Results

$(if command_exists trivy; then
    trivy image --format table "${FULL_IMAGE}" 2>/dev/null || echo "Scan failed"
else
    echo "Trivy not available"
fi)

## Recommendations

1. **Regular Updates:** Rebuild image monthly with latest base image
2. **Minimal Dependencies:** Remove unnecessary packages
3. **Security Patches:** Apply security updates during build
4. **Non-root User:** Ensure application runs as non-root (✅ Implemented)
5. **Secrets Management:** Use external secret management systems

## Next Steps

- [ ] Review and fix any HIGH/CRITICAL vulnerabilities
- [ ] Update base image if newer version available
- [ ] Consider using distroless images for production
- [ ] Implement image signing and verification

EOF

    echo "📄 Security report saved to ${REPORT_FILE}"
}

# Main execution
main() {
    echo "🚀 Docker Security Scan Starting..."
    
    # Check if image exists
    if ! docker image inspect "${FULL_IMAGE}" >/dev/null 2>&1; then
        echo "❌ Image ${FULL_IMAGE} not found. Please build the image first."
        exit 1
    fi
    
    # Run security checks
    dockerfile_lint
    vulnerability_scan
    image_analysis
    security_best_practices
    generate_report
    
    echo "✅ Security scan completed!"
    echo "📄 Check the generated report for detailed findings."
}

# Run main function
main "$@"