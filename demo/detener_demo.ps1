# Apaga el sistema y la base de la demo local.
$Base = Join-Path $env:LOCALAPPDATA "MarEHijasDemo"
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*MarEHijasDemo*" } | ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}
Write-Host "Demo detenida. (Los datos quedan guardados en $Base)"
foreach ($p in 5050, 3307) {
    Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue | ForEach-Object {
        Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
    }
}
