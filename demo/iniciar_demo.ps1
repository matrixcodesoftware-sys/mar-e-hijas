# =====================================================================
#  MAR E HIJAS - Demo local en Windows (un clic)
#  - Descarga MariaDB portable (no instala nada en Windows)
#  - Crea un entorno de Python con las librerias
#  - Crea la base con datos de prueba
#  - Inicia el sistema y abre el navegador en http://localhost:5000
#  Todo queda en %LOCALAPPDATA%\MarEHijasDemo (fuera de OneDrive).
# =====================================================================
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Proyecto = Split-Path -Parent $PSScriptRoot
$Base     = Join-Path $env:LOCALAPPDATA "MarEHijasDemo"
$DirMaria = Join-Path $Base "mariadb"
$DirDatos = Join-Path $Base "data"
$DirVenv  = Join-Path $Base "venv"
$PuertoDB = 3307
$PuertoApp = 5050
$env:PORT = "$PuertoApp"
$ClaveDB  = "demo_marehijas"

function Paso($t) { Write-Host ""; Write-Host "==> $t" -ForegroundColor Yellow }
function PuertoAbierto($p) {
    try { $c = New-Object Net.Sockets.TcpClient; $c.Connect("127.0.0.1", $p); $c.Close(); return $true } catch { return $false }
}

New-Item -ItemType Directory -Force -Path $Base | Out-Null

# ---------------------------------------------------------------- Python
Paso "Buscando Python"
$Py = $null
foreach ($cand in @("py", "python")) {
    try {
        $v = & $cand -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
        if ($LASTEXITCODE -eq 0 -and $v) { $Py = $cand; break }
    } catch {}
}
if (-not $Py) { throw "No se encontro Python. Instalalo desde https://www.python.org/downloads/ (marcar 'Add to PATH')." }
Write-Host "Python $v ($Py)"

# ---------------------------------------------------------------- MariaDB portable
$Mysqld = Get-ChildItem -Path $DirMaria -Recurse -Filter "mysqld.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $Mysqld) {
    Paso "Descargando MariaDB portable (~90 MB, una sola vez)"
    $versiones = @("10.11.10", "10.11.9", "10.11.8", "11.4.4")
    $zip = Join-Path $Base "mariadb.zip"
    $ok = $false
    foreach ($ver in $versiones) {
        $url = "https://archive.mariadb.org/mariadb-$ver/winx64-packages/mariadb-$ver-winx64.zip"
        try { Write-Host "Probando $url"; Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing; $ok = $true; break } catch { Write-Host "  no disponible" }
    }
    if (-not $ok) { throw "No se pudo descargar MariaDB." }
    Paso "Descomprimiendo MariaDB"
    Expand-Archive -Path $zip -DestinationPath $DirMaria -Force
    Remove-Item $zip
    $Mysqld = Get-ChildItem -Path $DirMaria -Recurse -Filter "mysqld.exe" | Select-Object -First 1
}
$Bin = $Mysqld.DirectoryName

# ---------------------------------------------------------------- Inicializar datos
if (-not (Test-Path (Join-Path $DirDatos "my.ini"))) {
    Paso "Creando la base de datos local"
    $install = Join-Path $Bin "mariadb-install-db.exe"
    if (-not (Test-Path $install)) { $install = Join-Path $Bin "mysql_install_db.exe" }
    & $install "--datadir=$DirDatos" "--port=$PuertoDB" "--password=$ClaveDB" | Out-Host
}

# ---------------------------------------------------------------- Arrancar MariaDB
if (-not (PuertoAbierto $PuertoDB)) {
    Paso "Iniciando MariaDB en el puerto $PuertoDB"
    Start-Process -FilePath $Mysqld.FullName -ArgumentList "--defaults-file=`"$DirDatos\my.ini`"", "--console" -WindowStyle Minimized
    for ($i = 0; $i -lt 40 -and -not (PuertoAbierto $PuertoDB); $i++) { Start-Sleep -Milliseconds 500 }
    if (-not (PuertoAbierto $PuertoDB)) { throw "MariaDB no arranco." }
}

# ---------------------------------------------------------------- Entorno Python
$VPy = Join-Path $DirVenv "Scripts\python.exe"
if (-not (Test-Path $VPy)) {
    Paso "Creando entorno de Python"
    & $Py -m venv $DirVenv
}
Paso "Instalando librerias (Flask, PyMySQL, ReportLab...)"
& $VPy -m pip install --disable-pip-version-check -q -r (Join-Path $Proyecto "requirements.txt")

# ---------------------------------------------------------------- .env
$EnvFile = Join-Path $Proyecto ".env"
if (-not (Test-Path $EnvFile)) {
    Paso "Creando archivo .env"
    $secreto = -join ((48..57) + (97..102) | Get-Random -Count 64 | ForEach-Object { [char]$_ })
    @"
FLASK_ENV=development
SECRET_KEY=$secreto
DB_HOST=127.0.0.1
DB_PORT=$PuertoDB
DB_NAME=mar_e_hijas
DB_USER=root
DB_PASSWORD=$ClaveDB
"@ | Set-Content -Path $EnvFile -Encoding ASCII
}

# ---------------------------------------------------------------- Base + datos de prueba
Set-Location $Proyecto
$existe = & (Join-Path $Bin "mysql.exe") -uroot "-p$ClaveDB" -P $PuertoDB -h 127.0.0.1 -N -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='mar_e_hijas' AND table_name='ventas'" 2>$null
if ($existe -ne "1") {
    Paso "Creando tablas y cargando DATOS DE PRUEBA"
    & $VPy manage.py init-db
    & $VPy manage.py seed-demo
}

# ---------------------------------------------------------------- Iniciar sistema
if (-not (PuertoAbierto $PuertoApp)) {
    Paso "Iniciando MAR E HIJAS"
    Start-Process -FilePath $VPy -ArgumentList "run.py" -WorkingDirectory $Proyecto -WindowStyle Minimized
    for ($i = 0; $i -lt 40 -and -not (PuertoAbierto $PuertoApp); $i++) { Start-Sleep -Milliseconds 500 }
}

Paso "Listo. Abriendo http://localhost:$PuertoApp"
Write-Host "Usuarios: dueno / Dueno2026!   admin / Admin2026!   vendedor / Vende2026!   chofer1 / Chofer2026!" -ForegroundColor Green
Write-Host "Para apagar todo: DETENER_DEMO.bat"
$chrome = @("$env:ProgramFiles\Google\Chrome\Application\chrome.exe", "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe", "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($chrome) { Start-Process $chrome "http://localhost:$PuertoApp" } else { Start-Process "http://localhost:$PuertoApp" }
