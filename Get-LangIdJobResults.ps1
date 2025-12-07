param(
    [string]$ApiBaseUrl = "http://localhost:8080",
    [int]$MaxJobs = 50
)

Add-Type -AssemblyName System.Net.Http
$client = New-Object System.Net.Http.HttpClient

function Get-PipelineMode {
    param([object]$resultJson)

    $midZone    = $false
    $vadUsed    = $false
    $useVadDeep = $false

    if ($resultJson -and $resultJson.PSObject.Properties.Name -contains "gate_meta" -and $resultJson.gate_meta) {
        if ($resultJson.gate_meta.PSObject.Properties.Name -contains "mid_zone") {
            $midZone = [bool]$resultJson.gate_meta.mid_zone
        }
        if ($resultJson.gate_meta.PSObject.Properties.Name -contains "vad_used") {
            $vadUsed = [bool]$resultJson.gate_meta.vad_used
        }
    }

    if ($resultJson -and $resultJson.PSObject.Properties.Name -contains "raw" -and $resultJson.raw) {
        $rawOuter = $resultJson.raw

        if ($rawOuter.PSObject.Properties.Name -contains "gate_meta" -and $rawOuter.gate_meta) {
            if (-not $midZone -and $rawOuter.gate_meta.PSObject.Properties.Name -contains "mid_zone") {
                $midZone = [bool]$rawOuter.gate_meta.mid_zone
            }
            if (-not $vadUsed -and $rawOuter.gate_meta.PSObject.Properties.Name -contains "vad_used") {
                $vadUsed = [bool]$rawOuter.gate_meta.vad_used
            }
        }

        if ($rawOuter.PSObject.Properties.Name -contains "raw" -and $rawOuter.raw) {
            $deep = $rawOuter.raw
            if ($deep.PSObject.Properties.Name -contains "lang_gate" -and $deep.lang_gate) {
                $lg = $deep.lang_gate

                if ($lg.PSObject.Properties.Name -contains "gate_meta" -and $lg.gate_meta) {
                    if (-not $midZone -and $lg.gate_meta.PSObject.Properties.Name -contains "mid_zone") {
                        $midZone = [bool]$lg.gate_meta.mid_zone
                    }
                    if (-not $vadUsed -and $lg.gate_meta.PSObject.Properties.Name -contains "vad_used") {
                        $vadUsed = [bool]$lg.gate_meta.vad_used
                    }
                }

                if ($lg.PSObject.Properties.Name -contains "use_vad") {
                    $useVadDeep = [bool]$lg.use_vad
                }
            }
        }
    }

    $mode = "NORMAL"
    if ($vadUsed -or $useVadDeep) {
        $mode = "VAD"
    }
    elseif ($midZone) {
        $mode = "MID_ZONE"
    }

    return $mode
}

# ---- 1) Get /jobs ----
$jobsUri = $ApiBaseUrl.TrimEnd('/') + "/jobs"
Write-Host "Fetching jobs from $jobsUri"

$jobsResponse = $client.GetAsync($jobsUri).Result
$jobsBody     = $jobsResponse.Content.ReadAsStringAsync().Result

if (-not $jobsResponse.IsSuccessStatusCode) {
    Write-Host "Error fetching /jobs:"
    Write-Host $jobsBody
    throw ("GET /jobs failed with HTTP {0}" -f [int]$jobsResponse.StatusCode)
}

$jobsJson = $jobsBody | ConvertFrom-Json
if (-not $jobsJson.jobs) {
    throw "No jobs[] in /jobs response."
}

$jobs = $jobsJson.jobs
if ($jobs.Count -gt $MaxJobs) {
    Write-Host ("Truncating jobs from {0} to {1} (MaxJobs)" -f $jobs.Count, $MaxJobs)
    $jobs = $jobs | Select-Object -First $MaxJobs
}

$rows = @()
$idx  = 0

foreach ($job in $jobs) {
    $idx++
    $jobId = $job.job_id
    Write-Host ""
    Write-Host ("[{0}/{1}] Fetching /jobs/{2}/result" -f $idx, $jobs.Count, $jobId)

    $resultUri       = $ApiBaseUrl.TrimEnd('/') + "/jobs/" + [Uri]::EscapeDataString([string]$jobId) + "/result"
    $resultResponse  = $client.GetAsync($resultUri).Result
    $resultBody      = $resultResponse.Content.ReadAsStringAsync().Result

    if (-not $resultResponse.IsSuccessStatusCode) {
        Write-Host ("  ERROR HTTP {0} for {1}" -f [int]$resultResponse.StatusCode, $resultUri)
        Write-Host "  Body:"
        Write-Host $resultBody

        $rows += [pscustomobject]@{
            JobId           = $jobId
            OriginalFile    = $job.original_filename
            Language        = $job.language
            Probability     = if ($job.probability -ne $null) { [math]::Round([double]$job.probability, 6) } else { $null }
            DetectionMethod = $null
            GateDecision    = $null
            PipelineMode    = $null
            MusicOnly       = $null
            Transcript      = $null
            Error           = ("HTTP {0}" -f [int]$resultResponse.StatusCode)
        }
        continue
    }

    $resultJson = $null
    try {
        $resultJson = $resultBody | ConvertFrom-Json
    }
    catch {
        Write-Host "  ERROR: result is not valid JSON"
        Write-Host $resultBody

        $rows += [pscustomobject]@{
            JobId           = $jobId
            OriginalFile    = $job.original_filename
            Language        = $job.language
            Probability     = if ($job.probability -ne $null) { [math]::Round([double]$job.probability, 6) } else { $null }
            DetectionMethod = $null
            GateDecision    = $null
            PipelineMode    = $null
            MusicOnly       = $null
            Transcript      = $null
            Error           = "Invalid JSON in /result"
        }
        continue
    }

    # ---- 2) Extract fields DIRECTLY from /jobs/{id}/result ----
    $lang            = $null
    $probResult      = $null
    $detMethod       = $null
    $gateDecision    = $null
    $musicOnly       = $null
    $transcript      = $null

    if ($resultJson.PSObject.Properties.Name -contains "language") {
        $lang = [string]$resultJson.language
    }
    if ($resultJson.PSObject.Properties.Name -contains "probability") {
        $probResult = [double]$resultJson.probability
    }
    if ($resultJson.PSObject.Properties.Name -contains "detection_method") {
        $detMethod = [string]$resultJson.detection_method
    }
    if ($resultJson.PSObject.Properties.Name -contains "gate_decision") {
        $gateDecision = [string]$resultJson.gate_decision
    }
    if ($resultJson.PSObject.Properties.Name -contains "music_only") {
        $musicOnly = [bool]$resultJson.music_only
    }
    if ($resultJson.PSObject.Properties.Name -contains "transcript_snippet") {
        $transcript = [string]$resultJson.transcript_snippet
    }

    $pipelineMode = Get-PipelineMode -resultJson $resultJson

    $rows += [pscustomobject]@{
        JobId           = $jobId
        OriginalFile    = $resultJson.original_filename
        Language        = $lang
        Probability     = if ($probResult -ne $null) { [math]::Round($probResult, 6) } else { $null }
        DetectionMethod = $detMethod
        GateDecision    = $gateDecision
        PipelineMode    = $pipelineMode
        MusicOnly       = $musicOnly
        Transcript      = $transcript
        Error           = $null
    }
}

Write-Host ""
Write-Host "==================== JOB RESULT SUMMARY ===================="
$rows | Sort-Object OriginalFile, JobId | Format-Table -AutoSize

if ($client) { $client.Dispose() }