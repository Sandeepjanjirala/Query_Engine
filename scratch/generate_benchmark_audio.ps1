Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.Rate = -1
$audioDir = "scratch\audio"

# 10s text (~25-30 words)
$text10 = "Please provide the executive analytics report for RI Anitha, including dropout rates, active fee dues, revenue versus salary metrics, and student teacher ratios across all branches."

# 20s text (~55-60 words)
$text20 = "Good morning executive team. Please provide a comprehensive overview of branch performance for the current academic year. We need detailed metrics on student dropout percentages across all zones, outstanding fee dues for twenty twenty five, salary burden percentages compared with revenue, and student teacher ratios for primary and high school levels."

# 30s text (~85-90 words)
$text30 = "Welcome to the executive analytical assistant. Please analyze the complete organizational hierarchy starting from AGM Suresh down to RI Anitha and RI Srinivasa Rao. We require a thorough breakdown of dropout statistics comparing current year and last year, total pending fee dues with zero paid student counts, detailed revenue versus salary burden analysis across all branches, and comprehensive staffing metrics including student teacher ratios and students per section across pre primary, primary school, and high school categories."

$benchmarks = @(
    @{ file = "bench_10s.wav"; text = $text10 },
    @{ file = "bench_20s.wav"; text = $text20 },
    @{ file = "bench_30s.wav"; text = $text30 }
)

foreach ($b in $benchmarks) {
    $outPath = Join-Path $audioDir $b.file
    $synth.SetOutputToWaveFile($outPath)
    $synth.Speak($b.text)
    $synth.SetOutputToDefaultAudioDevice()
    Write-Output "Generated benchmark audio: $outPath"
}
