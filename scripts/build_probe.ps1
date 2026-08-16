$u = Join-Path $env:LOCALAPPDATA "Programs\MSYS2\ucrt64\bin"
$env:PATH = "$u;$env:PATH"
$root = "C:\Users\29517\Documents\Codex\2026-08-13\https-github-com-zisonzishen0415-stack-ampneve"

& "$u\gcc.exe" -O2 -I "$root\ampneve\core" "$root\work\gain_probe.c" "$root\ampneve\core\ampsim.c" -o "$root\work\gain_probe_before.exe" -lm 2> "$root\work\gcc_err_before.txt"
Write-Output "before build exit: $LASTEXITCODE"
& "$u\gcc.exe" -O2 -I "$root\ampneve\core" "$root\work\gain_probe.c" "$root\work\ampsim_patched.c" -o "$root\work\gain_probe_after.exe" -lm 2> "$root\work\gcc_err_after.txt"
Write-Output "after build exit: $LASTEXITCODE"

& "$u\gcc.exe" -O2 -I "$root\ampneve\core" "$root\ampneve\tests\test_ampsim.c" "$root\work\ampsim_patched.c" -o "$root\work\test_ampsim_patched.exe" -lm 2> "$root\work\gcc_err_test.txt"
Write-Output "test build exit: $LASTEXITCODE"
& "$root\work\test_ampsim_patched.exe"

& "$u\gcc.exe" -O2 -I "$root\ampneve\core" "$root\work\gain_probe.c" "$root\work\ampsim_v2.c" -o "$root\work\gain_probe_v2.exe" -lm 2> "$root\work\gcc_err_v2.txt"
Write-Output "v2 build exit: $LASTEXITCODE"
& "$u\gcc.exe" -O2 -I "$root\ampneve\core" "$root\ampneve\tests\test_ampsim.c" "$root\work\ampsim_v2.c" -o "$root\work\test_ampsim_v2.exe" -lm 2> "$root\work\gcc_err_test2.txt"
Write-Output "v2 test build exit: $LASTEXITCODE"
& "$root\work\test_ampsim_v2.exe"

& "$u\gcc.exe" -O2 -I "$root\ampneve\core" "$root\work\gain_probe.c" "$root\work\ampsim_v3.c" -o "$root\work\gain_probe_v3.exe" -lm 2> "$root\work\gcc_err_v3.txt"
Write-Output "v3 build exit: $LASTEXITCODE"
& "$u\gcc.exe" -O2 -I "$root\ampneve\core" "$root\ampneve\tests\test_ampsim.c" "$root\work\ampsim_v3.c" -o "$root\work\test_ampsim_v3.exe" -lm 2> "$root\work\gcc_err_test3.txt"
Write-Output "v3 test build exit: $LASTEXITCODE"
& "$root\work\test_ampsim_v3.exe"

& "$u\gcc.exe" -O2 -I "$root\ampneve\core" "$root\work\gain_probe.c" "$root\work\ampsim_v4.c" -o "$root\work\gain_probe_v4.exe" -lm 2> "$root\work\gcc_err_v4.txt"
Write-Output "v4 build exit: $LASTEXITCODE"
& "$u\gcc.exe" -O2 -I "$root\ampneve\core" "$root\ampneve\tests\test_ampsim.c" "$root\work\ampsim_v4.c" -o "$root\work\test_ampsim_v4.exe" -lm 2> "$root\work\gcc_err_test4.txt"
Write-Output "v4 test build exit: $LASTEXITCODE"
& "$root\work\test_ampsim_v4.exe"

& "$u\gcc.exe" -O2 -I "$root\ampneve\core" "$root\work\comp_probe.c" "$root\ampneve\core\ampsim.c" -o "$root\work\comp_probe.exe" -lm 2> "$root\work\gcc_err_comp.txt"
Write-Output "comp build exit: $LASTEXITCODE"
foreach ($s in @("0.8 0.8 0.8 0", "0.8 0.8 0.8 1", "0.6 0.6 0.8 0", "0.6 0.6 0.8 1", "0.55 0.55 0.8 0", "0.55 0.55 0.8 1", "0.5 0.7 0.8 0", "0.5 0.7 0.8 1", "0.45 0.6 0.8 0", "0.45 0.6 0.8 1")) {
    & "$root\work\comp_probe.exe" $s.Split(" ")
}

& "$u\gcc.exe" -O2 -I "$root\ampneve\core" "$root\work\extreme_probe.c" "$root\ampneve\core\ampsim.c" -o "$root\work\extreme_probe.exe" -lm 2> "$root\work\gcc_err_extreme.txt"
Write-Output "extreme probe build exit: $LASTEXITCODE"
& "$root\work\extreme_probe.exe"

& "$u\gcc.exe" -O2 -I "$root\ampneve\core" "$root\work\spectrum_probe.c" "$root\ampneve\core\ampsim.c" -o "$root\work\spectrum_probe.exe" -lm 2> "$root\work\gcc_err_spec.txt"
Write-Output "spectrum probe build exit: $LASTEXITCODE"
& "$root\work\spectrum_probe.exe"

& "$u\gcc.exe" -O2 -I "$root\ampneve\core" "$root\work\block_reset_probe.c" "$root\ampneve\core\ampsim.c" -o "$root\work\block_reset_probe.exe" -lm 2> "$root\work\gcc_err_block.txt"
Write-Output "block reset probe build exit: $LASTEXITCODE"
& "$root\work\block_reset_probe.exe"

# --- v5 prototype checks ---
& "$u\gcc.exe" -O2 -I "$root\ampneve\core" "$root\work\block_reset_probe.c" "$root\work\ampsim_v5.c" -o "$root\work\block_reset_probe_v5.exe" -lm 2> "$root\work\gcc_err_block5.txt"
Write-Output "v5 block probe build: $LASTEXITCODE"
& "$root\work\block_reset_probe_v5.exe"

& "$u\gcc.exe" -O2 -I "$root\ampneve\core" "$root\work\extreme_probe.c" "$root\work\ampsim_v5.c" -o "$root\work\extreme_probe_v5.exe" -lm 2> "$root\work\gcc_err_extreme5.txt"
Write-Output "v5 extreme probe build: $LASTEXITCODE"
& "$root\work\extreme_probe_v5.exe"

& "$u\gcc.exe" -O2 -I "$root\ampneve\core" "$root\ampneve\tests\test_ampsim.c" "$root\work\ampsim_v5.c" -o "$root\work\test_ampsim_v5.exe" -lm 2> "$root\work\gcc_err_test5.txt"
Write-Output "v5 test build: $LASTEXITCODE"
& "$root\work\test_ampsim_v5.exe"

& "$u\gcc.exe" -O2 -I "$root\ampneve\core" "$root\work\extreme_probe.c" "$root\work\ampsim_v6.c" -o "$root\work\extreme_probe_v6.exe" -lm 2> "$root\work\gcc_err_extreme6.txt"
Write-Output "v6 extreme probe build: $LASTEXITCODE"
& "$root\work\extreme_probe_v6.exe"

& "$u\gcc.exe" -O2 -I "$root\ampneve\core" "$root\ampneve\tests\test_ampsim.c" "$root\work\ampsim_v6.c" -o "$root\work\test_ampsim_v6.exe" -lm 2> "$root\work\gcc_err_test6.txt"
Write-Output "v6 test build: $LASTEXITCODE"
& "$root\work\test_ampsim_v6.exe"

& "$u\gcc.exe" -O2 -I "$root\ampneve\core" "$root\work\stage_harmonics.c" "$root\work\ampsim_instr.c" -o "$root\work\stage_harmonics.exe" -lm 2> "$root\work\gcc_err_stage.txt"
Write-Output "stage harmonics build: $LASTEXITCODE"
& "$root\work\stage_harmonics.exe"
