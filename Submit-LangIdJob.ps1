param(
    # Full path to the audio file (UNC is fine)
    [Parameter(Mandatory = $true)]
    [string]$FilePath,

    # LangID API base (no trailing slash)
    [string]$ApiBaseUrl = "http://agn-vntg-ls01.production.ctv.ca:8080",

    # Optional query params on submit
    [string]$TargetLang,
    [string]$Internal,

    # Polling settings
    [int]$PollIntervalSeconds = 5,
    [int]$TimeoutSeconds = 600,

    # Optional directory to also write the JSON result as <job_id>.json
    [string]$OutputDir
)

# ---------- PowerShell version guard ----------
$psMajor = 0
if (Get-Variable -Name PSVersionTable -ErrorAction SilentlyContinue) {
    $psMajor = $PSVersionTable.PSVersion.Major
} else {
    # Very old PS – treat as unsupported
    $psMajor = 2
}

if ($psMajor -lt 3) {
    throw ("This script requires PowerShell 3.0 or later (for JSON cmdlets). Detected PS version: {0}" -f $PSVersionTable.PSVersion)
}

if (-not (Test-Path -LiteralPath $FilePath)) {
    throw "File not found: $FilePath"
}

if ($OutputDir -and -not (Test-Path -LiteralPath $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
}

# ---------- HTTP client setup (robust Add-Type) ----------
try {
    Add-Type -AssemblyName System.Net.Http -ErrorAction Stop
} catch {
    # In some environments (e.g. PowerShell Core) the assembly is already loaded.
    # Swallow the error to avoid "dll not found" style issues.
}

$client = New-Object System.Net.Http.HttpClient
$fileStream = $null

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

try {
    # ---------- 1) SUBMIT JOB ----------
    $submitBase = $ApiBaseUrl.TrimEnd('/') + "/jobs"
    $submitUriBuilder = New-Object System.UriBuilder($submitBase)

    $queryParts = @()
    if ($TargetLang) {
        $queryParts += ("target_lang=" + [Uri]::EscapeDataString($TargetLang))
    }
    if ($Internal) {
        $queryParts += ("internal=" + [Uri]::EscapeDataString($Internal))
    }
    if ($queryParts.Count -gt 0) {
        $submitUriBuilder.Query = [string]::Join("&", $queryParts)
    }

    $submitUri = $submitUriBuilder.Uri

    $content = New-Object System.Net.Http.MultipartFormDataContent

    $fileStream = [System.IO.File]::OpenRead($FilePath)
    $fileContent = New-Object System.Net.Http.StreamContent($fileStream)
    $fileContent.Headers.ContentType = 'application/octet-stream'

    $fileName = [System.IO.Path]::GetFileName($FilePath)
    $content.Add($fileContent, "file", $fileName)

    $submitResponse = $client.PostAsync($submitUri, $content).Result
    $submitBody     = $submitResponse.Content.ReadAsStringAsync().Result

    if (-not $submitResponse.IsSuccessStatusCode) {
        throw ("Submit failed with HTTP {0}: {1}" -f [int]$submitResponse.StatusCode, $submitBody)
    }

    $submitJson = $submitBody | ConvertFrom-Json
    $jobId = $submitJson.job_id

    if (-not $jobId) {
        throw "Submit JSON has no job_id. Body: $submitBody"
    }

    # ---------- 2) POLL /jobs?job_id=... ----------
    $statusBase = $ApiBaseUrl.TrimEnd('/') + "/jobs"
    $statusUriBuilder = New-Object System.UriBuilder($statusBase)
    $statusUriBuilder.Query = "job_id=" + [Uri]::EscapeDataString([string]$jobId)
    $statusUri = $statusUriBuilder.Uri

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $finalStatus = $null

    while ($true) {
        if ((Get-Date) -gt $deadline) {
            throw "Timeout waiting for job $jobId after $TimeoutSeconds seconds."
        }

        Start-Sleep -Seconds $PollIntervalSeconds

        $statusResponse = $client.GetAsync($statusUri).Result
        $statusBody     = $statusResponse.Content.ReadAsStringAsync().Result

        if (-not $statusResponse.IsSuccessStatusCode) {
            continue
        }

        $statusJson = $statusBody | ConvertFrom-Json

        if (-not $statusJson.jobs -or $statusJson.jobs.Count -eq 0) {
            continue
        }

        $job = $statusJson.jobs | Where-Object { $_.job_id -eq $jobId } | Select-Object -First 1
        if (-not $job) {
            $job = $statusJson.jobs[0]
        }

        $statusValue = [string]$job.status
        $statusLower = $statusValue.ToLower()

        if ($statusLower -eq "succeeded" -or $statusLower -eq "failed" -or $statusLower -eq "error") {
            $finalStatus = $statusLower
            break
        }
    }

    if ($finalStatus -ne "succeeded") {
        throw "Job $jobId finished with non-succeeded status: $finalStatus"
    }

    # ---------- 3) FETCH FINAL RESULT /jobs/{id}/result ----------
    $resultUri = $ApiBaseUrl.TrimEnd('/') + "/jobs/" + [Uri]::EscapeDataString([string]$jobId) + "/result"

    $resultResponse = $client.GetAsync($resultUri).Result
    $resultBody     = $resultResponse.Content.ReadAsStringAsync().Result

    if (-not $resultResponse.IsSuccessStatusCode) {
        throw ("Result fetch failed with HTTP {0}: {1}" -f [int]$resultResponse.StatusCode, $resultBody)
    }

    $resultJson = $resultBody | ConvertFrom-Json

    # ---------- 4) EXTRACT FIELDS ----------
    $lang            = $null
    $probability     = $null
    $gateDecision    = $null
    $musicOnly       = $false
    $detectionMethod = $null

    if ($resultJson.PSObject.Properties.Name -contains "language") {
        $lang = [string]$resultJson.language
    }
    elseif ($resultJson.PSObject.Properties.Name -contains "raw" -and $resultJson.raw) {
        if ($resultJson.raw.PSObject.Properties.Name -contains "language") {
            $lang = [string]$resultJson.raw.language
        }
    }

    if ($resultJson.PSObject.Properties.Name -contains "probability") {
        $probability = [double]$resultJson.probability
    }

    if ($resultJson.PSObject.Properties.Name -contains "gate_decision") {
        $gateDecision = [string]$resultJson.gate_decision
    }
    elseif ($resultJson.PSObject.Properties.Name -contains "raw" -and $resultJson.raw) {
        if ($resultJson.raw.PSObject.Properties.Name -contains "gate_decision") {
            $gateDecision = [string]$resultJson.raw.gate_decision
        }
        elseif ($resultJson.raw.PSObject.Properties.Name -contains "raw" -and $resultJson.raw.raw) {
            $deep = $resultJson.raw.raw
            if ($deep.PSObject.Properties.Name -contains "lang_gate" -and $deep.lang_gate) {
                $lg = $deep.lang_gate
                if ($lg.PSObject.Properties.Name -contains "gate_decision") {
                    $gateDecision = [string]$lg.gate_decision
                }
            }
        }
    }

    if ($resultJson.PSObject.Properties.Name -contains "music_only") {
        $musicOnly = [bool]$resultJson.music_only
    }
    elseif ($resultJson.PSObject.Properties.Name -contains "raw" -and $resultJson.raw) {
        if ($resultJson.raw.PSObject.Properties.Name -contains "music_only") {
            $musicOnly = [bool]$resultJson.raw.music_only
        }
        elseif ($resultJson.raw.PSObject.Properties.Name -contains "raw" -and $resultJson.raw.raw) {
            $deep2 = $resultJson.raw.raw
            if ($deep2.PSObject.Properties.Name -contains "music_only") {
                $musicOnly = [bool]$deep2.music_only
            }
        }
    }

    if ($resultJson.PSObject.Properties.Name -contains "detection_method") {
        $detectionMethod = [string]$resultJson.detection_method
    }
    elseif ($resultJson.PSObject.Properties.Name -contains "raw" -and $resultJson.raw) {
        if ($resultJson.raw.PSObject.Properties.Name -contains "detection_method") {
            $detectionMethod = [string]$resultJson.raw.detection_method
        }
    }

    $pipelineMode = Get-PipelineMode -resultJson $resultJson

    # ---------- 5) DECISION ALGO + HUMAN_INTERVENTION ----------
    $resultCode = "NONE"
    $reason     = "UNKNOWN"

    $decision     = $gateDecision
    $decisionNorm = ""
    if ($decision) {
        $decisionNorm = ($decision + "").ToUpper()
    }

    $langNorm = ""
    if ($lang) {
        $langNorm = ($lang + "").ToLower()
    }

    if ($musicOnly -eq $true) {
        $resultCode = "NONE"
        $reason     = "MUSIC"
    }
    elseif ($decisionNorm -eq "NO_SPEECH_MUSIC_ONLY") {
        $resultCode = "NONE"
        $reason     = "MUSIC"
    }
    elseif ($decisionNorm -eq "FALLBACK" -or -not $decision) {
        $resultCode = "NONE"
        $reason     = "FALLBACK"
    }
    else {
        if ($langNorm -eq "eng" -or $langNorm -eq "en") {
            $resultCode = "EN"
            $reason     = "ACCEPT"
        }
        elseif ($langNorm -eq "fra" -or $langNorm -eq "fre" -or $langNorm -eq "fr") {
            $resultCode = "FR"
            $reason     = "ACCEPT"
        }
        else {
            $resultCode = "NONE"
            $reason     = "UNKNOWN"
        }
    }

    # human_intervention = True if:
    #   music_only == true OR gate_decision == "fallback"
    $humanIntervention = $false
    if ($musicOnly -eq $true -or $decisionNorm -eq "FALLBACK") {
        $humanIntervention = $true
    }

    # ---------- 6) FINAL JSON OUTPUT ----------
    $finalOut = [pscustomobject]@{
        job_id             = $jobId
        file               = $fileName
        result             = $resultCode
        reason             = $reason
        music_only         = $musicOnly
        gate_decision      = $gateDecision
        pipeline_mode      = $pipelineMode
        language           = $lang
        detection_method   = $detectionMethod
        human_intervention = $humanIntervention
    }

    $json = $finalOut | ConvertTo-Json -Depth 20

    if ($OutputDir) {
        $outPath = Join-Path $OutputDir ("{0}.json" -f $jobId)
        Set-Content -LiteralPath $outPath -Value $json -Encoding UTF8
    }

    # Silent mode: only emit the JSON
    Write-Output $json
}
finally {
    if ($fileStream) { $fileStream.Dispose() }
    if ($client)     { $client.Dispose() }
}