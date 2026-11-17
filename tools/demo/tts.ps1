param($Json,$OutDir)
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.SelectVoice('Microsoft Zira Desktop'); $s.Rate = 0; $s.Volume = 100
$fmt = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(44100, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
New-Item -ItemType Directory -Force $OutDir | Out-Null
$data = Get-Content $Json -Raw | ConvertFrom-Json
foreach ($seg in $data) { $i = 0; foreach ($line in $seg.lines) {
  $f = Join-Path $OutDir ("s{0}_{1}.wav" -f $seg.seg, $i)
  $s.SetOutputToWaveFile($f, $fmt); $s.Speak($line); $s.SetOutputToNull(); $i++ } }
