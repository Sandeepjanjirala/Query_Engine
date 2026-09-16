Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.Rate = 0
$voices = $synth.GetInstalledVoices()
foreach ($v in $voices) {
    Write-Output "Voice: $($v.VoiceInfo.Name) ($($v.VoiceInfo.Culture))"
}

# Ensure scratch/audio directory exists
$audioDir = "scratch\audio"
if (-not (Test-Path $audioDir)) {
    New-Item -ItemType Directory -Path $audioDir | Out-Null
}

$testQueries = @(
    @{ id = "q1"; text = "RI Anitha dropout statistics" },
    @{ id = "q2"; text = "RI Anitha fee due statistics" },
    @{ id = "q3"; text = "RI Anitha dropout fee due statistics" },
    @{ id = "q4"; text = "RI Anitha dropout fee due revenue versus salary statistics" },
    @{ id = "q5"; text = "Give Kakinada one statistics" },
    @{ id = "q6"; text = "Show Kakinada one dropout statistics" },
    @{ id = "q7"; text = "Branch Amalapuram statistics" },
    @{ id = "q8"; text = "Branch Amalapuram two statistics" },
    @{ id = "q9"; text = "Show top five branches by dropout percentage" },
    @{ id = "q10"; text = "Show revenue versus salary for RI Anitha" }
)

foreach ($item in $testQueries) {
    $outPath = Join-Path $audioDir "$($item.id).wav"
    $synth.SetOutputToWaveFile($outPath)
    $synth.Speak($item.text)
    $synth.SetOutputToDefaultAudioDevice()
    Write-Output "Generated: $outPath for '$($item.text)'"
}
