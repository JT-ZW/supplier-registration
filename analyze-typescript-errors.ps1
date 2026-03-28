# ============================================================================
# TypeScript Error Analysis Script
# ============================================================================
# This script analyzes TypeScript compilation errors in your Next.js project
# and provides detailed information to help fix them effectively.
# ============================================================================

# Helper Functions (defined first)
function Get-ErrorSolution {
    param($Error)
    
    $message = $Error.Message
    
    if ($message -match "Property '(\w+)' does not exist on type '(\w+)'") {
        $property = $Matches[1]
        $type = $Matches[2]
        return "Add the missing property '$property' to the '$type' interface/type definition.`n`n1. Locate the type definition for '$type'`n2. Add the property: $property`: <appropriate-type>;`n3. Ensure it matches the backend API response structure"
    }
    
    if ($message -match "Type '(.+)' is not assignable to type '(.+)'") {
        return "Fix type mismatch:`n1. Check if the types should actually match`n2. Add appropriate type casting if needed: value as TargetType`n3. Or update the type definition to match actual usage"
    }
    
    if ($message -match "Cannot find name '(\w+)'") {
        $name = $Matches[1]
        return "The identifier '$name' is not defined:`n1. Check if you need to import it`n2. Verify the spelling`n3. Ensure it's defined in the current scope"
    }
    
    return $null
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  TypeScript Error Analyzer" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# Configuration
$ProjectRoot = $PSScriptRoot
$FrontendPath = Join-Path $ProjectRoot "frontend"
$ErrorLogPath = Join-Path $ProjectRoot "typescript-errors.log"
$ReportPath = Join-Path $ProjectRoot "typescript-error-report.md"

# Check if frontend directory exists
if (-not (Test-Path $FrontendPath)) {
    Write-Host "Error: Frontend directory not found at $FrontendPath" -ForegroundColor Red
    exit 1
}

Write-Host "Project Root: $ProjectRoot" -ForegroundColor Yellow
Write-Host "Frontend Path: $FrontendPath" -ForegroundColor Yellow
Write-Host ""

# Change to frontend directory
Set-Location $FrontendPath

# Check if node_modules exists
if (-not (Test-Path "node_modules")) {
    Write-Host "Installing dependencies first..." -ForegroundColor Yellow
    npm ci
    Write-Host ""
}

Write-Host "Running TypeScript compilation check..." -ForegroundColor Cyan
Write-Host ""

# Run TypeScript check and capture output
$tscOutput = & npx tsc --noEmit 2>&1 | Out-String

# Also try Next.js build to get more detailed errors
Write-Host "Running Next.js build check..." -ForegroundColor Cyan
Write-Host ""
$buildOutput = & npm run build 2>&1 | Out-String

# Save full output to log file
$fullOutput = @"
=================================
TypeScript Check Output (tsc)
=================================
$tscOutput

=================================
Next.js Build Output
=================================
$buildOutput
"@

$fullOutput | Out-File -FilePath $ErrorLogPath -Encoding UTF8
Write-Host "Full output saved to: $ErrorLogPath" -ForegroundColor Green
Write-Host ""

# Parse and analyze errors
Write-Host "Analyzing errors..." -ForegroundColor Cyan
Write-Host ""

$errors = @()
$errorPattern = '(?m)^(.+?)\((\d+),(\d+)\):\s+error\s+TS(\d+):\s+(.+)$'
$nextErrorPattern = '(?m)^(.+?):(\d+):(\d+)[\r\n]+Type error:\s+(.+)$'

# Parse tsc errors
if ($tscOutput -match 'error TS') {
    foreach ($match in ([regex]::Matches($tscOutput, $errorPattern))) {
        $errors += [PSCustomObject]@{
            File = $match.Groups[1].Value
            Line = $match.Groups[2].Value
            Column = $match.Groups[3].Value
            Code = "TS$($match.Groups[4].Value)"
            Message = $match.Groups[5].Value
            Source = "tsc"
        }
    }
}

# Parse Next.js errors
if ($buildOutput -match 'Type error:') {
    $lines = $buildOutput -split "`n"
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match '^(.+?):(\d+):(\d+)$') {
            $file = $Matches[1]
            $line = $Matches[2]
            $column = $Matches[3]
            
            if ($i + 1 -lt $lines.Count -and $lines[$i + 1] -match '^Type error:\s+(.+)$') {
                $message = $Matches[1]
                $errors += [PSCustomObject]@{
                    File = $file
                    Line = $line
                    Column = $column
                    Code = "Next.js"
                    Message = $message
                    Source = "Next.js Build"
                }
            }
        }
    }
}

# Generate report
$reportContent = "# TypeScript Error Analysis Report`n"
$reportContent += "**Generated**: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')`n`n"
$reportContent += "## Summary`n"
$reportContent += "- **Total Errors Found**: $($errors.Count)`n"
$reportContent += "- **Project**: Procurement System`n"
$reportContent += "- **Frontend Framework**: Next.js 16`n`n"
$reportContent += "---`n`n"
$reportContent += "## Errors by File`n`n"

if ($errors.Count -gt 0) {
    # Group errors by file
    $errorsByFile = $errors | Group-Object -Property File
    
    foreach ($fileGroup in $errorsByFile) {
        $fileName = $fileGroup.Name
        $fileErrors = $fileGroup.Group
        
        $reportContent += "### $fileName`n"
        $reportContent += "**Errors**: $($fileErrors.Count)`n`n"
        
        foreach ($error in $fileErrors) {
            $reportContent += "**Error at Line $($error.Line):$($error.Column)**`n"
            $reportContent += "- **Code**: $($error.Code)`n"
            $reportContent += "- **Message**: $($error.Message)`n"
            $reportContent += "- **Source**: $($error.Source)`n`n"
            $reportContent += "Location: $fileName`:$($error.Line)`:$($error.Column)`n`n"
        }
    }
    
    # Add recommendations
    $reportContent += "---`n`n"
    $reportContent += "## Recommended Fixes`n`n"
    
    foreach ($error in $errors) {
        $fix = Get-ErrorSolution -Error $error
        if ($fix) {
            $reportContent += "### Fix for: $($error.File)`:$($error.Line)`n"
            $reportContent += "**Problem**: $($error.Message)`n`n"
            $reportContent += "**Solution**:`n$fix`n`n"
        }
    }
    
} else {
    $reportContent += "### No TypeScript Errors Found!`n`n"
    $reportContent += "Your TypeScript code compiles successfully.`n`n"
}

$reportContent += "---`n`n"
$reportContent += "## Next Steps`n`n"
$reportContent += "1. Review each error in the report above`n"
$reportContent += "2. Apply the recommended fixes`n"
$reportContent += "3. Run npm run build to verify fixes`n"
$reportContent += "4. Repeat until all errors are resolved`n`n"
$reportContent += "---`n`n"
$reportContent += "**Full compilation output saved to**: $ErrorLogPath`n"

# Save report
$reportContent | Out-File -FilePath $ReportPath -Encoding UTF8

# Display summary
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Analysis Complete" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

if ($errors.Count -gt 0) {
    Write-Host "Found $($errors.Count) TypeScript error(s)" -ForegroundColor Red
    Write-Host ""
    
    # Show first few errors
    $displayCount = [Math]::Min(3, $errors.Count)
    Write-Host "Top $displayCount Error(s):" -ForegroundColor Yellow
    for ($i = 0; $i -lt $displayCount; $i++) {
        $error = $errors[$i]
        Write-Host ""
        Write-Host "  Location: $($error.File):$($error.Line):$($error.Column)" -ForegroundColor White
        Write-Host "  $($error.Message)" -ForegroundColor Gray
    }
    
    if ($errors.Count -gt $displayCount) {
        Write-Host ""
        Write-Host "  ... and $($errors.Count - $displayCount) more error(s)" -ForegroundColor Gray
    }
    
    Write-Host ""
    Write-Host "Full report: $ReportPath" -ForegroundColor Green
    Write-Host "Full logs: $ErrorLogPath" -ForegroundColor Green
    
} else {
    Write-Host "No TypeScript errors found!" -ForegroundColor Green
    Write-Host "Your code is ready to build!" -ForegroundColor Green
}

Write-Host ""

# Return to project root
Set-Location $ProjectRoot

# Exit with appropriate code
if ($errors.Count -gt 0) {
    exit 1
} else {
    exit 0
}