param(
    [Parameter(Mandatory = $true)]
    [string]$FilePath,

    [int]$Runs = 10,

    [string]$ApiBaseUrl = "http://localhost:8080",

    [int]$PollIntervalSeconds = 5,
    [int]$TimeoutSeconds = 600
)

if (-not (Test-Path -LiteralPath $FilePath)) {
    throw "File not found: $FilePath"
}

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

function Get-GateDiagnostics {
    param([object]$resultJson)

    $midZone        = $false
    $vadUsed        = $false
    $stopEn         = $null
    $stopFr         = $null
    $tokenCount     = $null
    $useVadDeep     = $null
    $methodDeep     = $null
    $langDeep       = $null
    $probDeep       = $null

    if ($resultJson -and $resultJson.PSObject.Properties.Name -contains "gate_meta" -and $resultJson.gate_meta) {
        if ($resultJson.gate_meta.PSObject.Properties.Name -contains "mid_zone") {
            $midZone = [bool]$resultJson.gate_meta.mid_zone
        }
        if ($resultJson.gate_meta.PSObject.Properties.Name -contains "vad_used") {
            $vadUsed = [bool]$resultJson.gate_meta.vad_used
        }
        if ($resultJson.gate_meta.PSObject.Properties.Name -contains "stopword_ratio_en") {
            $stopEn = $resultJson.gate_meta.stopword_ratio_en
        }
        if ($resultJson.gate_meta.PSObject.Properties.Name -contains "stopword_ratio_fr") {
            $stopFr = $resultJson.gate_meta.stopword_ratio_fr
        }
        if ($resultJson.gate_meta.PSObject.Properties.Name -contains "token_count") {
            $tokenCount = $resultJson.gate_meta.token_count
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
            if (-not $stopEn -and $rawOuter.gate_meta.PSObject.Properties.Name -contains "stopword_ratio_en") {
                $stopEn = $rawOuter.gate_meta.stopword_ratio_en
            }
            if (-not $stopFr -and $rawOuter.gate_meta.PSObject.Properties.Name -contains "stopword_ratio_fr") {
                $stopFr = $rawOuter.gate_meta.stopword_ratio_fr
            }
            if (-not $tokenCount -and $rawOuter.gate_meta.PSObject.Properties.Name -contains "token_count") {
                $tokenCount = $rawOuter.gate_meta.token_count
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
                    if (-not $stopEn -and $lg.gate_meta.PSObject.Properties.Name -contains "stopword_ratio_en") {
                        $stopEn = $lg.gate_meta.stopword_ratio_en
                    }
                    if (-not $stopFr -and $lg.gate_meta.PSObject.Properties.Name -contains "stopword_ratio_fr") {
                        $stopFr = $lg.gate_meta.stopword_ratio_fr
                    }
                    if (-not $tokenCount -and $lg.gate_meta.PSObject.Properties.Name -contains "token_count") {
                        $tokenCount = $lg.gate_meta.token_count
                    }
                }

                if ($lg.PSObject.Properties.Name -contains "use_vad") {
                    $useVadDeep = [bool]$lg.use_vad
                }
                if ($lg.PSObject.Properties.Name -contains "method") {
                    $methodDeep = [string]$lg.method
                }
                if ($lg.PSObject.Properties.Name -contains "language") {
                    $langDeep = [string]$lg.language
                }
                if ($lg.PSObject.Properties.Name -contains "probability") {
                    $probDeep = [double]$lg.probability
                }
            }
        }
    }

    return [pscustomobject]@{
        MidZone             = $midZone
        VadUsed             = $vadUsed
        StopwordRatioEn     = $stopEn
        StopwordRatioFr     = $stopFr
        TokenCount          = $tokenCount
        LangGateUseVad      = $useVadDeep
        LangGateMethod      = $methodDeep
        LangGateLanguage    = $langDeep
        LangGateProbability = $probDeep
    }
}

function Invoke-LangIdJob {
    param(
        [string]$FilePath,
        [string]$ApiBaseUrl,
        [int]$PollIntervalSeconds,
        [int]$TimeoutSeconds
    )

    $submitBase = $ApiBaseUrl.TrimEnd('/') + "/jobs"
    $submitUri  = [Uri]$submitBase

    Write-Host ""
    Write-Host "=== Submitting job to $submitUri for file '$FilePath' ==="

    $content    = New-Object System.Net.Http.MultipartFormDataContent
    $fileStream = [System.IO.File]::OpenRead($FilePath)
    $fileContent = New-Object System.Net.Http.StreamContent($fileStream)
    $fileContent.Headers.ContentType = 'application/octet-stream'

    $fileName = [System.IO.Path]::GetFileName($FilePath)
    $content.Add($fileContent, "file", $fileName)

    try {
        $submitResponse = $client.PostAsync($submitUri, $content).Result
        $submitBody     = $submitResponse.Content.ReadAsStringAsync().Result
    }
    finally {
        if ($fileStream) { $fileStream.Dispose() }
    }

    Write-Host "Submit HTTP: $([int]$submitResponse.StatusCode)"
    Write-Host "Submit body:"
    try {
        $submitBody | ConvertFrom-Json | ConvertTo-Json -Depth 20
    }
    catch {
        Write-Host $submitBody
    }

    if (-not $submitResponse.IsSuccessStatusCode) {
        throw ("Submit failed with HTTP {0}: {1}" -f [int]$submitResponse.StatusCode, $submitBody)
    }

    $submitJson = $submitBody | ConvertFrom-Json
    $jobId      = $submitJson.job_id
    if (-not $jobId) {
        throw "Submit JSON has no job_id. Body: $submitBody"
    }

    Write-Host "Job ID: $jobId"
    Write-Host "Initial status: $($submitJson.status)"

    $statusBase = $ApiBaseUrl.TrimEnd('/') + "/jobs"
    $statusUriBuilder = New-Object System.UriBuilder($statusBase)
    $statusUriBuilder.Query = "job_id=" + [Uri]::EscapeDataString([string]$jobId)
    $statusUri = $statusUriBuilder.Uri

    Write-Host ""
    Write-Host "============================================================"
    Write-Host "[POLL] Starting polling loop for job $jobId"
    Write-Host "[POLL] Will poll $statusUri every $PollIntervalSeconds seconds, timeout after $TimeoutSeconds seconds."
    Write-Host "============================================================"

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $finalStatus = $null

    $attempt = 0
    while ($true) {
        if ((Get-Date) -gt $deadline) {
            throw "Timeout waiting for job $jobId after $TimeoutSeconds seconds."
        }

        $attempt++
        Write-Host ""
        Write-Host "[POLL] Attempt #$attempt for job $jobId – sleeping $PollIntervalSeconds seconds before status check..."
        Start-Sleep -Seconds $PollIntervalSeconds

        Write-Host "[POLL] Checking status for job $jobId at $statusUri"
        $statusResponse = $client.GetAsync($statusUri).Result
        $statusBody     = $statusResponse.Content.ReadAsStringAsync().Result

        Write-Host "Status HTTP: $([int]$statusResponse.StatusCode)"
        Write-Host "[POLL] Status body (pretty JSON):"
        try {
            $statusBody | ConvertFrom-Json | ConvertTo-Json -Depth 20
        }
        catch {
            Write-Host $statusBody
        }

        if (-not $statusResponse.IsSuccessStatusCode) {
            Write-Host "[POLL] Non-success while polling, retrying..."
            continue
        }

        $statusJson = $statusBody | ConvertFrom-Json
        if (-not $statusJson.jobs -or $statusJson.jobs.Count -eq 0) {
            Write-Host "[POLL] No jobs[] in response, retrying..."
            continue
        }

        $job = $statusJson.jobs | Where-Object { $_.job_id -eq $jobId } | Select-Object -First 1
        if (-not $job) {
            $job = $statusJson.jobs[0]
        }

        $statusValue = [string]$job.status
        $statusLower = $statusValue.ToLower()

        Write-Host ("[POLL] Job {0} status: {1}" -f $jobId, $statusValue)

        if ($statusLower -eq "succeeded" -or $statusLower -eq "failed" -or $statusLower -eq "error") {
            Write-Host ("[POLL] Job {0} finished with terminal status '{1}'. Exiting polling loop." -f $jobId, $statusValue)
            $finalStatus = $statusLower
            break
        }

        Write-Host ("[POLL] Job {0} is not finished yet (status={1}), will continue polling..." -f $jobId, $statusValue)
    }

    if ($finalStatus -ne "succeeded") {
        throw "Job $jobId finished with non-succeeded status: $finalStatus"
    }

    $resultUri = $ApiBaseUrl.TrimEnd('/') + "/jobs/" + [Uri]::EscapeDataString([string]$jobId) + "/result"
    Write-Host ""
    Write-Host "Fetching final result from $resultUri"

    $resultResponse = $client.GetAsync($resultUri).Result
    $resultBody     = $resultResponse.Content.ReadAsStringAsync().Result

    Write-Host "Result HTTP: $([int]$resultResponse.StatusCode)"
    Write-Host "Result body (pretty JSON):"
    try {
        $resultBody | ConvertFrom-Json | ConvertTo-Json -Depth 20
    }
    catch {
        Write-Host $resultBody
    }

    if (-not $resultResponse.IsSuccessStatusCode) {
        throw ("Result fetch failed with HTTP {0}: {1}" -f [int]$resultResponse.StatusCode, $resultBody)
    }

    $resultJson = $resultBody | ConvertFrom-Json
    return @{ JobId = $jobId; Result = $resultJson }
}

$results = @()

for ($i = 1; $i -le $Runs; $i++) {
    Write-Host ""
    Write-Host "==================================================="
    Write-Host ("RUN #{0} / {1}" -f $i, $Runs)
    Write-Host "==================================================="

    try {
        $call       = Invoke-LangIdJob -FilePath $FilePath -ApiBaseUrl $ApiBaseUrl -PollIntervalSeconds $PollIntervalSeconds -TimeoutSeconds $TimeoutSeconds
        $jobId      = $call.JobId
        $resultJson = $call.Result

        $lang            = $null
        $probability     = $null
        $gateDecision    = $null
        $musicOnly       = $false
        $transcript      = $null
        $detectionMethod = $null

        if ($resultJson.PSObject.Properties.Name -contains "language") {
            $lang = [string]$resultJson.language
        }
        if ($resultJson.PSObject.Properties.Name -contains "probability") {
            $probability = [double]$resultJson.probability
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
        if ($resultJson.PSObject.Properties.Name -contains "detection_method") {
            $detectionMethod = [string]$resultJson.detection_method
        }

        $pipelineMode = Get-PipelineMode -resultJson $resultJson
        $gateInfo     = Get-GateDiagnostics -resultJson $resultJson

        $row = [pscustomobject]@{
            Run                 = $i
            JobId               = $jobId
            Language            = $lang
            Probability         = if ($probability -ne $null) { [math]::Round($probability, 6) } else { $null }
            GateDecision        = $gateDecision
            PipelineMode        = $pipelineMode
            MusicOnly           = $musicOnly
            DetectionMethod     = $detectionMethod
            Transcript          = $transcript
            GateMidZone         = $gateInfo.MidZone
            GateVadUsed         = $gateInfo.VadUsed
            StopwordRatioEn     = $gateInfo.StopwordRatioEn
            StopwordRatioFr     = $gateInfo.StopwordRatioFr
            TokenCount          = $gateInfo.TokenCount
            LangGateUseVad      = $gateInfo.LangGateUseVad
            LangGateMethod      = $gateInfo.LangGateMethod
            LangGateLanguage    = $gateInfo.LangGateLanguage
            LangGateProbability = if ($gateInfo.LangGateProbability -ne $null) { [math]::Round($gateInfo.LangGateProbability, 6) } else { $null }
        }

        $results += $row
    }
    catch {
        Write-Host ("ERROR in run #{0}: {1}" -f $i, $_.Exception.Message)

        $results += [pscustomobject]@{
            Run                 = $i
            JobId               = $null
            Language            = $null
            Probability         = $null
            GateDecision        = $null
            PipelineMode        = $null
            MusicOnly           = $null
            DetectionMethod     = $null
            Transcript          = $null
            GateMidZone         = $null
            GateVadUsed         = $null
            StopwordRatioEn     = $null
            StopwordRatioFr     = $null
            TokenCount          = $null
            LangGateUseVad      = $null
            LangGateMethod      = $null
            LangGateLanguage    = $null
            LangGateProbability = $null
            ConsistentWithRun1  = $false
            Error               = $_.Exception.Message
        }
    }
}

Write-Host ""
Write-Host "==================== PER-RUN RESULTS ===================="
$results | Format-Table -AutoSize

if ($results.Count -gt 0) {
    $baseline = $results[0]

    # *** NEW: define "consistency" only on high-level outputs ***
    $keysToCompare = @(
        'Language',
        'MusicOnly'
    )

    foreach ($row in $results) {
        $consistent = $true
        foreach ($key in $keysToCompare) {
            $valThis = $row.$key
            $valBase = $baseline.$key
            if ($valThis -ne $valBase) {
                $consistent = $false
                break
            }
        }
        Add-Member -InputObject $row -NotePropertyName "ConsistentWithRun1" -NotePropertyValue $consistent -Force
    }

    $inconsistent = $results | Where-Object { $_.ConsistentWithRun1 -eq $false }

    Write-Host ""
    Write-Host "======================= SUMMARY ========================="
    if ($inconsistent.Count -eq 0) {
        Write-Host "All runs are consistent with run #1 for fields:"
        Write-Host ("  {0}" -f ($keysToCompare -join ", "))
    }
    else {
        Write-Host "Found inconsistencies vs run #1 for fields:"
        Write-Host ("  {0}" -f ($keysToCompare -join ", "))
        Write-Host ""
        Write-Host "Inconsistent runs (high-level outputs):"
        $inconsistent | Select-Object Run, JobId, Language, MusicOnly | Format-Table -AutoSize
    }

    # *** NEW: pipeline behaviour stats (VAD vs MID_ZONE etc.) ***
    Write-Host ""
    Write-Host "================= PIPELINE BEHAVIOUR STATS ================="
    $results |
        Group-Object PipelineMode, DetectionMethod, GateDecision |
        Select-Object @{
            Name       = 'PipelineMode'    ; Expression = { $_.Name.Split(',')[0].Trim() }
        }, @{
            Name       = 'DetectionMethod' ; Expression = { $_.Name.Split(',')[1].Trim() }
        }, @{
            Name       = 'GateDecision'    ; Expression = { $_.Name.Split(',')[2].Trim() }
        }, @{
            Name       = 'Count'           ; Expression = { $_.Count }
        } |
        Sort-Object Count -Descending |
        Format-Table -AutoSize
}

if ($client) { $client.Dispose() }