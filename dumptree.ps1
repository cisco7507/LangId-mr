# Dump-LangIdTree.ps1
# Creates a snapshot of LangID-related directories and disk layout.

$timestamp   = Get-Date -Format "yyyyMMdd-HHmmss"
$outputDir   = "C:\LangId"
$outputFile  = Join-Path $outputDir "LangId_Directory_Snapshot_$timestamp.txt"

if (-not (Test-Path $outputDir)) {
    New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
}

"==== LangID Directory Snapshot ====" | Out-File $outputFile -Encoding UTF8
"Timestamp: $(Get-Date)" | Out-File $outputFile -Append -Encoding UTF8
"" | Out-File $outputFile -Append -Encoding UTF8

"==== Volume Info ====" | Out-File $outputFile -Append -Encoding UTF8
Get-Volume | Select DriveLetter, FileSystemLabel, Size, Path |
    Format-Table -AutoSize | Out-String |
    Out-File $outputFile -Append -Encoding UTF8
"" | Out-File $outputFile -Append -Encoding UTF8

"==== Disk Info ====" | Out-File $outputFile -Append -Encoding UTF8
Get-Disk | Select Number, FriendlyName, Size, IsBoot, IsSystem |
    Format-Table -AutoSize | Out-String |
    Out-File $outputFile -Append -Encoding UTF8
"" | Out-File $outputFile -Append -Encoding UTF8

# Helper to dump a tree if a path exists
function Dump-Tree {
    param(
        [string]$Label,
        [string]$Path
    )

    if (Test-Path $Path) {
        "==== Tree for $Label ($Path) ====" | Out-File $outputFile -Append -Encoding UTF8
        # /F = list files, /A = ASCII (no line-drawing chars)
        cmd /c "tree `"$Path`" /F /A" | Out-File $outputFile -Append -Encoding UTF8
        "" | Out-File $outputFile -Append -Encoding UTF8
    } else {
        "==== $Label ($Path) does not exist ====" | Out-File $outputFile -Append -Encoding UTF8
        "" | Out-File $outputFile -Append -Encoding UTF8
    }
}

# Likely relevant roots
Dump-Tree -Label "LangId root on C:" -Path "C:\LangId"
Dump-Tree -Label "langid_service on C:" -Path "C:\LangId\langid_service"
Dump-Tree -Label "LangId root on D:" -Path "D:\LangId"
Dump-Tree -Label "LangIdData on D:" -Path "D:\LangIdData"

Write-Host "Snapshot written to: $outputFile"