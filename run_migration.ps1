# PowerShell script to run Railway migration
Write-Host "======================================"
Write-Host "  Railway Database Migration"
Write-Host "======================================"
Write-Host ""

$projectName = "distinguished-illumination"
$migrationFile = "migrations/add_missing_columns.sql"

# Link to Railway project
Write-Host "Linking to Railway project: $projectName"
$linkProcess = Start-Process -FilePath "railway" -ArgumentList "link" -PassThru -NoNewWindow

# Wait a moment for the interactive prompt
Start-Sleep -Seconds 2

# Send the project selection (distinguished-illumination is option 2)
Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.SendKeys]::SendWait("{DOWN}")
Start-Sleep -Milliseconds 500
[System.Windows.Forms.SendKeys]::SendWait("{ENTER}")

# Wait for linking to complete
$linkProcess.WaitForExit()

Write-Host ""
Write-Host "Getting database connection..."

# Get DATABASE_URL
$env:DATABASE_URL = railway variables get DATABASE_URL

if ([string]::IsNullOrEmpty($env:DATABASE_URL)) {
    Write-Host "Error: Could not retrieve DATABASE_URL" -ForegroundColor Red
    exit 1
}

Write-Host "Connected! Running migration..." -ForegroundColor Green
Write-Host ""

# Run psql with the migration file
railway run psql -f $migrationFile

Write-Host ""
Write-Host "======================================"
Write-Host "  Migration Complete!"
Write-Host "======================================"
