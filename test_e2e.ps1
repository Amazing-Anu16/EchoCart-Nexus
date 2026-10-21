# ==============================================================================
# EchoCart Nexus - End-to-End Streamable HTTP & MCP Apps Verification (PowerShell)
# ==============================================================================

$BaseUrl = if ($env:MCP_URL) { $env:MCP_URL } else { "http://localhost:8080" }
$ProtoVersion = "2025-11-25"
$PassCount = 0
$FailCount = 0

function Assert-Check {
    param(
        [string]$Name,
        [bool]$Condition,
        [string]$Details = ""
    )
    if ($Condition) {
        Write-Host "  [PASS] $Name" -ForegroundColor Green
        $script:PassCount++
    } else {
        Write-Host "  [FAIL] $Name: $Details" -ForegroundColor Red
        $script:FailCount++
    }
}

Write-Host "`n=== EchoCart Nexus E2E Integration Suite ($BaseUrl) ===" -ForegroundColor Cyan

# 1. Health
Write-Host "`n1. Health Check & Readiness" -ForegroundColor Cyan
try {
    $health = Invoke-RestMethod -Uri "$BaseUrl/health" -Method Get
    Assert-Check "GET /health returns healthy" ($health.status -eq "healthy")
    Assert-Check "Protocol version matches" ($health.mcp_protocol_version -eq $ProtoVersion)
} catch {
    Assert-Check "GET /health reachable" $false $_.Exception.Message
}

# 2. Wire Version Check (Missing header rejected)
Write-Host "`n2. Protocol Version Header Enforcement" -ForegroundColor Cyan
try {
    $res = Invoke-WebRequest -Uri "$BaseUrl/mcp" -Method Post -ContentType "application/json" -Body '{"jsonrpc":"2.0","id":1,"method":"ping"}' -SkipHttpErrorCheck
    Assert-Check "Missing protocol header returns 400" ($res.StatusCode -eq 400)
} catch {
    Assert-Check "Missing protocol header returns 400" $true
}

# Valid ping
try {
    $headers = @{
        "MCP-Protocol-Version" = $ProtoVersion
        "Mcp-Method" = "ping"
    }
    $res = Invoke-WebRequest -Uri "$BaseUrl/mcp" -Method Post -Headers $headers -ContentType "application/json" -Body '{"jsonrpc":"2.0","id":2,"method":"ping"}'
    Assert-Check "Valid ping returns 200" ($res.StatusCode -eq 200)
    Assert-Check "Mirrors MCP-Protocol-Version" ($res.Headers["MCP-Protocol-Version"] -eq $ProtoVersion)
} catch {
    Assert-Check "Valid ping succeeds" $false $_.Exception.Message
}

# 3. Tool Discovery & UI Metadata
Write-Host "`n3. Tool Discovery & UI Metadata" -ForegroundColor Cyan
try {
    $headers = @{
        "MCP-Protocol-Version" = $ProtoVersion
        "Mcp-Method" = "tools/list"
    }
    $res = Invoke-RestMethod -Uri "$BaseUrl/mcp" -Method Post -Headers $headers -ContentType "application/json" -Body '{"jsonrpc":"2.0","id":20,"method":"tools/list"}'
    $tools = $res.tools
    $cartTool = $tools | Where-Object { $_.name -eq "manage_cart" }
    $searchTool = $tools | Where-Object { $_.name -eq "search_catalog" }

    Assert-Check "manage_cart has _meta.ui.resourceUri" ($cartTool._meta.ui.resourceUri -eq "ui://echocart/cart-view.html")
    Assert-Check "search_catalog has _meta.ui.resourceUri" ($searchTool._meta.ui.resourceUri -eq "ui://echocart/product-carousel.html")
} catch {
    Assert-Check "tools/list discovery succeeds" $false $_.Exception.Message
}

# 4. Resources
Write-Host "`n4. Resources & Template Verification" -ForegroundColor Cyan
try {
    $headers = @{
        "MCP-Protocol-Version" = $ProtoVersion
        "Mcp-Method" = "resources/list"
    }
    $res = Invoke-RestMethod -Uri "$BaseUrl/mcp" -Method Post -Headers $headers -ContentType "application/json" -Body '{"jsonrpc":"2.0","id":30,"method":"resources/list"}'
    $cartRes = $res.resources | Where-Object { $_.uri -eq "ui://echocart/cart-view.html" }
    Assert-Check "cart-view.html has MIME text/html;profile=mcp-app" ($cartRes.mimeType -eq "text/html;profile=mcp-app")
} catch {
    Assert-Check "resources/list succeeds" $false $_.Exception.Message
}

# 5. Direct HTTP View Endpoints
Write-Host "`n5. Direct HTTP View Endpoints & CSP" -ForegroundColor Cyan
try {
    $res = Invoke-WebRequest -Uri "$BaseUrl/mcp-apps/cart-view.html" -Method Get
    Assert-Check "GET /mcp-apps/cart-view.html returns 200" ($res.StatusCode -eq 200)
    Assert-Check "Has Content-Security-Policy header" ($res.Headers.ContainsKey("Content-Security-Policy"))
} catch {
    Assert-Check "Direct template serving succeeds" $false $_.Exception.Message
}

Write-Host "`n=== Summary: $PassCount Passed, $FailCount Failed ===" -ForegroundColor $(if ($FailCount -eq 0) { "Green" } else { "Red" })
if ($FailCount -gt 0) { exit 1 } else { exit 0 }
