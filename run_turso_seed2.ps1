# run_turso_seed2.ps1 — Seed modules, departments, item types, module access,
# field definitions, and workflow rules into Turso via HTTP API.

$TURSO_URL   = "srgec-sims-test-guttaprasad1-glitch.aws-ap-south-1.turso.io"
$TURSO_TOKEN = "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJhIjoicnciLCJpYXQiOjE3ODE0MTMwODUsImlkIjoiMDE5ZWM0N2MtZGMwMS03ODI2LTgxNmItNTlhMjRkZTJiNDVmIiwicmlkIjoiNmM4NDFkMjUtN2YyMi00YmY3LWE0NWItYmJmZmQ4NmI1YmQ2In0.IBc7aKD30Blbzdu14NzMIYs_EAFFtn-RyFF_sXeuuybwXfBF2nE4Mz4pmyTJvoyNS0xlCj6D7tonUCbTN6U8Cw"

$url = "https://$TURSO_URL/v2/pipeline"
$headers = @{
    "Authorization" = "Bearer $TURSO_TOKEN"
    "Content-Type"  = "application/json"
}

$bodyJson = Get-Content -Raw -Path "turso_seed2_body.json"

Write-Host "Sending modules/departments/item-types/workflows to Turso..."
$response = Invoke-RestMethod -Uri $url -Method Post -Headers $headers -Body $bodyJson

$errors = $response.results | Where-Object { $_.type -eq "error" }
if ($errors) {
    Write-Host "`n⚠️  $($errors.Count) statement(s) had errors:"
    foreach ($e in $errors) {
        Write-Host "  - $($e.error.message)"
    }
} else {
    Write-Host "`n✅ All seed statements executed successfully!"
}

Write-Host "`nDone. Reload your app and click Module Portal."
