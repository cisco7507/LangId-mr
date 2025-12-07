[CmdletBinding()]
param(
    [Parameter(ParameterSetName="ByHours", Mandatory=$true)]
    [int]$Hours,

    [Parameter(ParameterSetName="ByMinutes", Mandatory=$true)]
    [int]$Minutes,

    [string]$ApiBaseUrl = "http://localhost:8080"
)

if ($PSCmdlet.ParameterSetName -eq "ByMinutes") {
    $cutoffDate = (Get-Date).AddMinutes(-$Minutes).ToUniversalTime()
    Write-Host "Looking for successful jobs older than $Minutes minutes..."
}
else {
    $cutoffDate = (Get-Date).AddHours(-$Hours).ToUniversalTime()
    Write-Host "Looking for successful jobs older than $Hours hours..."
}

Write-Host "Cutoff date (UTC): $cutoffDate"

try {
    # Get all jobs
    $response = Invoke-RestMethod -Uri "$ApiBaseUrl/jobs" -Method Get
    
    if (-not $response.jobs) {
        Write-Host "No jobs returned from API."
        return
    }

    $jobs = $response.jobs

    # Filter jobs
    $jobsToDelete = @()
    foreach ($job in $jobs) {
        if ($job.status -ne 'succeeded') { continue }

        $val = $job.created_at
        $jobDate = $null

        if ($val -is [DateTime]) {
            $jobDate = $val
            if ($jobDate.Kind -eq 'Unspecified') {
                $jobDate = [DateTime]::SpecifyKind($jobDate, [System.DateTimeKind]::Utc)
            }
            elseif ($jobDate.Kind -eq 'Local') {
                $jobDate = $jobDate.ToUniversalTime()
            }
        }
        else {
            $createdAtStr = [string]$val
            # If the date string has no timezone info (no Z and no offset), assume UTC and append Z
            if ($createdAtStr -notmatch "Z$" -and $createdAtStr -notmatch "[+-]\d{2}:?\d{2}$") {
                 $createdAtStr = $createdAtStr + "Z"
            }
            try {
                $jobDate = [DateTime]$createdAtStr
                # Ensure we have a UTC DateTime for comparison
                if ($jobDate.Kind -eq 'Unspecified') {
                    $jobDate = [DateTime]::SpecifyKind($jobDate, [System.DateTimeKind]::Utc)
                }
                elseif ($jobDate.Kind -eq 'Local') {
                    $jobDate = $jobDate.ToUniversalTime()
                }
            }
            catch {
                Write-Warning "Failed to parse date '$val' for job $($job.job_id)"
                continue
            }
        }
        
        if ($jobDate -lt $cutoffDate) {
            $exceeded = $cutoffDate - $jobDate
            Write-Host "Marking for deletion: $($job.job_id)"
            Write-Host "  Last Updated:       $($job.updated_at)"
            Write-Host "  Exceeded Cutoff By: $($exceeded.ToString())"
            $jobsToDelete += $job
        }
    }

    if (-not $jobsToDelete -or $jobsToDelete.Count -eq 0) {
        Write-Host "No jobs found matching criteria."
        return
    }

    # Extract IDs
    # PowerShell might treat a single object differently than an array, ensure it's an array
    $jobIds = @($jobsToDelete) | ForEach-Object { $_.job_id }
    
    Write-Host "Found $($jobIds.Count) jobs to delete."

    # Prepare delete request
    $body = @{
        job_ids = $jobIds
    } | ConvertTo-Json

    # Delete jobs
    Invoke-RestMethod -Uri "$ApiBaseUrl/jobs" -Method Delete -Body $body -ContentType "application/json"
    
    Write-Host "Successfully deleted $($jobIds.Count) jobs."
}
catch {
    Write-Error "An error occurred: $_"
    if ($_.Exception.Response) {
        $reader = New-Object System.IO.StreamReader $_.Exception.Response.GetResponseStream()
        $responseBody = $reader.ReadToEnd()
        Write-Error "Response Body: $responseBody"
    }
}
