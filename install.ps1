#requires -Version 5.1

[CmdletBinding()]
param(
  [string]$Version = "",
  [switch]$Doctor,
  [switch]$Uninstall
)

# Simplicio ecosystem installer for Windows.
# Runtime assets are selected newest-first for Windows. Component wheels are
# selected newest-first and fall back to older releases when needed.

$ErrorActionPreference = "Stop"
$RuntimeRepo = "wesleysimplicio/simplicio"
$ApiRoot = "https://api.github.com/repos"
$InstallDir = if ($env:SIMPLICIO_BIN_DIR) { $env:SIMPLICIO_BIN_DIR } else { Join-Path $env:USERPROFILE ".local\bin" }
$StateDir = if ($env:SIMPLICIO_STATE_DIR) { $env:SIMPLICIO_STATE_DIR } else { Join-Path $env:USERPROFILE ".simplicio" }
$VenvDir = if ($env:SIMPLICIO_COMPONENT_VENV) { $env:SIMPLICIO_COMPONENT_VENV } else { Join-Path $StateDir "components-venv" }
$ManifestPath = Join-Path $StateDir "components.json"
$RuntimePath = Join-Path $InstallDir "simplicio.exe"

function Info([string]$Message) { Write-Host "==> $Message" }
function Ok([string]$Message) { Write-Host "  ✓ $Message" }
function Warn([string]$Message) { Write-Warning $Message }
function Fail([string]$Message) { throw $Message }

function Get-Python {
  $command = Get-Command python -ErrorAction SilentlyContinue
  if ($command) {
    return [PSCustomObject]@{ Exe = $command.Source; Args = @() }
  }
  $command = Get-Command py -ErrorAction SilentlyContinue
  if ($command) {
    return [PSCustomObject]@{ Exe = $command.Source; Args = @("-3") }
  }
  Fail "Python 3.11 ou superior não encontrado"
}

function Get-Releases {
  param(
    [Parameter(Mandatory = $true)][string]$Repository,
    [string]$PinnedVersion = ""
  )
  $headers = @{
    Accept = "application/vnd.github+json"
    "User-Agent" = "simplicio-installer"
  }
  if ($PinnedVersion) {
    $url = "$ApiRoot/$Repository/releases/tags/$PinnedVersion"
    return @(Invoke-RestMethod -Uri $url -Headers $headers -ErrorAction Stop)
  }
  $url = "$ApiRoot/$Repository/releases?per_page=100"
  return @(Invoke-RestMethod -Uri $url -Headers $headers -ErrorAction Stop)
}

function Find-ReleaseAsset {
  param(
    [Parameter(Mandatory = $true)][string]$Repository,
    [Parameter(Mandatory = $true)][string[]]$Patterns,
    [string]$PinnedVersion = ""
  )
  $releases = Get-Releases -Repository $Repository -PinnedVersion $PinnedVersion
  foreach ($release in $releases) {
    if ($release.draft -or $release.prerelease) { continue }
    foreach ($asset in @($release.assets)) {
      foreach ($pattern in $Patterns) {
        if ($asset.name -match $pattern) {
          return [PSCustomObject]@{
            Repository = $Repository
            Release = $release.tag_name
            Asset = $asset.name
            Url = $asset.browser_download_url
            Digest = $asset.digest
          }
        }
      }
    }
  }
  throw "Nenhum asset compatível encontrado em $Repository para: $($Patterns -join ', ')"
}

function Download-VerifiedAsset {
  param(
    [Parameter(Mandatory = $true)]$Asset,
    [Parameter(Mandatory = $true)][string]$Destination
  )
  $staging = "$Destination.download-$([guid]::NewGuid().ToString('N'))"
  try {
    Invoke-WebRequest -Uri $Asset.Url -OutFile $staging -UseBasicParsing -ErrorAction Stop
    if (-not (Test-Path $staging) -or (Get-Item $staging).Length -eq 0) {
      throw "download vazio: $($Asset.Url)"
    }
    if ($Asset.Digest -and $Asset.Digest -match '^sha256:(.+)$') {
      $expected = $Matches[1].ToLowerInvariant()
      $actual = (Get-FileHash -Path $staging -Algorithm SHA256).Hash.ToLowerInvariant()
      if ($actual -ne $expected) {
        throw "SHA-256 inválido para $($Asset.Asset): esperado $expected, obtido $actual"
      }
      Ok "SHA-256 verificado: $($Asset.Asset)"
    } else {
      Warn "sem digest SHA-256 publicado para $($Asset.Asset); instalação continua"
    }
    Move-Item -Force -Path $staging -Destination $Destination
  } finally {
    if (Test-Path $staging) { Remove-Item -Force $staging -ErrorAction SilentlyContinue }
  }
}

function Remove-ManagedInstall {
  Info "Removendo Simplicio Runtime e componentes gerenciados"
  if (Test-Path $ManifestPath) {
    try {
      $manifest = Get-Content -Raw -Path $ManifestPath | ConvertFrom-Json
      foreach ($path in @($manifest.managed_paths)) {
        if ($path -and (Test-Path $path)) {
          Remove-Item -Force -Path $path -ErrorAction SilentlyContinue
        }
      }
    } catch {
      Warn "não foi possível ler o manifesto; removendo apenas os caminhos padrão"
    }
  } else {
    if (Test-Path $RuntimePath) { Remove-Item -Force $RuntimePath }
  }
  if (Test-Path $VenvDir) { Remove-Item -Recurse -Force $VenvDir }
  if (Test-Path $ManifestPath) { Remove-Item -Force $ManifestPath }
  Ok "componentes removidos; demais configurações foram preservadas"
}

function Test-Install {
  $failed = $false
  if (Test-Path $RuntimePath) {
    try {
      & $RuntimePath version | Out-Null
      Ok "Runtime executável"
    } catch {
      Warn "Runtime não executa: $RuntimePath"
      $failed = $true
    }
  } else {
    Warn "Runtime ausente: $RuntimePath"
    $failed = $true
  }
  if (Test-Path $ManifestPath) {
    $manifest = Get-Content -Raw -Path $ManifestPath | ConvertFrom-Json
    foreach ($path in @($manifest.managed_paths)) {
      if ($path -and (Test-Path $path)) { Ok "disponível: $(Split-Path -Leaf $path)" }
      elseif ($path) { Warn "ausente: $path"; $failed = $true }
    }
    Ok "manifesto: $ManifestPath"
  } else {
    Warn "manifesto ausente: $ManifestPath"
    $failed = $true
  }
  if ($failed) { exit 1 }
}

if ($Uninstall) {
  Remove-ManagedInstall
  exit 0
}
if ($Doctor) {
  Test-Install
  exit 0
}

$python = Get-Python
$pythonVersion = (& $python.Exe @($python.Args) -c "import sys; print('%d.%d' % sys.version_info[:2])").Trim()
try {
  if ([version]$pythonVersion -lt [version]"3.11") { Fail "Python 3.11 ou superior é necessário; encontrado $pythonVersion" }
} catch {
  if ($_.Exception.Message -like "Python 3.11*") { throw }
  Fail "não foi possível verificar a versão do Python"
}

$pinnedRuntime = if ($Version) { $Version } elseif ($env:SIMPLICIO_VERSION) { $env:SIMPLICIO_VERSION } else { "" }
$runtimePatterns = @(
  '^simplicio-windows-x64\.exe$',
  '^simplicio-windows-x86_64\.exe$',
  '^simplicio\.exe$'
)

New-Item -ItemType Directory -Force -Path $InstallDir, $StateDir | Out-Null
$tempDir = Join-Path $env:TEMP ("simplicio-install-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $tempDir | Out-Null

try {
  Info "Procurando o binário Runtime Windows mais recente"
  $runtime = Find-ReleaseAsset -Repository $RuntimeRepo -Patterns $runtimePatterns -PinnedVersion $pinnedRuntime
  $runtimeStaging = Join-Path $tempDir $runtime.Asset
  Download-VerifiedAsset -Asset $runtime -Destination $runtimeStaging
  Move-Item -Force -Path $runtimeStaging -Destination $RuntimePath
  Ok "Runtime $($runtime.Release) instalado: $RuntimePath"

  $components = @(
    [PSCustomObject]@{ Name = "simplicio-mapper"; Repository = "wesleysimplicio/simplicio-mapper"; Pattern = '^simplicio_mapper-.*\.whl$' },
    [PSCustomObject]@{ Name = "simplicio-prompt"; Repository = "wesleysimplicio/simplicio-prompt"; Pattern = '^simplicio_prompt-.*\.whl$' },
    [PSCustomObject]@{ Name = "simplicio-dev-cli"; Repository = "wesleysimplicio/simplicio-dev-cli"; Pattern = '^simplicio_cli-.*\.whl$' },
    [PSCustomObject]@{ Name = "simplicio-fast"; Repository = "wesleysimplicio/simplicio-fast"; Pattern = '^simplicio_fast-.*\.whl$' },
    [PSCustomObject]@{ Name = "simplicio-loop"; Repository = "wesleysimplicio/simplicio-loop"; Pattern = '^simplicio_loop-.*\.whl$' },
    [PSCustomObject]@{ Name = "simplicio-sprint"; Repository = "wesleysimplicio/simplicio-sprint"; Pattern = '^simplicio_sprint-.*\.whl$' }
  )

  & $python.Exe @($python.Args) -m venv $VenvDir
  if ($LASTEXITCODE -ne 0) { Fail "não foi possível criar a virtualenv: $VenvDir" }
  $venvPython = Join-Path $VenvDir "Scripts\python.exe"
  if (-not (Test-Path $venvPython)) { Fail "Python da virtualenv não encontrado: $venvPython" }
  & $venvPython -m pip install --disable-pip-version-check --upgrade pip | Out-Host
  if ($LASTEXITCODE -ne 0) { Fail "não foi possível preparar o pip da virtualenv" }

  $wheelPaths = @()
  $componentRecords = @()
  foreach ($component in $components) {
    Info "Procurando wheel de $($component.Name)"
    $asset = Find-ReleaseAsset -Repository $component.Repository -Patterns @($component.Pattern)
    $wheelPath = Join-Path $tempDir $asset.Asset
    Download-VerifiedAsset -Asset $asset -Destination $wheelPath
    $wheelPaths += $wheelPath
    $componentRecords += [PSCustomObject]@{
      name = $component.Name
      repository = $component.Repository
      release = $asset.Release
      asset = $asset.Asset
    }
  }

  & $venvPython -m pip install --disable-pip-version-check --upgrade --force-reinstall $wheelPaths | Out-Host
  if ($LASTEXITCODE -ne 0) { Fail "falha ao instalar as wheels dos componentes" }

  $managedPaths = New-Object System.Collections.Generic.List[string]
  $managedPaths.Add($RuntimePath)
  $scriptsDir = Join-Path $VenvDir "Scripts"
  foreach ($entry in @(Get-ChildItem -Path $scriptsDir -Filter "simplicio-*.exe" -File -ErrorAction SilentlyContinue)) {
    $destination = Join-Path $InstallDir $entry.Name
    Copy-Item -Force -Path $entry.FullName -Destination $destination
    $managedPaths.Add($destination)
  }
  foreach ($entry in @(Get-ChildItem -Path $scriptsDir -Filter "sendsprint.exe" -File -ErrorAction SilentlyContinue)) {
    $destination = Join-Path $InstallDir $entry.Name
    Copy-Item -Force -Path $entry.FullName -Destination $destination
    $managedPaths.Add($destination)
  }

  $manifest = [ordered]@{
    schema = "simplicio.ecosystem-manifest/v2"
    source = "github-releases"
    runtime = [ordered]@{
      repository = $RuntimeRepo
      target = "windows-x64"
      release = $runtime.Release
      asset = $runtime.Asset
      path = $RuntimePath
    }
    components = @($componentRecords)
    python_venv = $VenvDir
    managed_paths = @($managedPaths)
  }
  $manifest | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 -Path $ManifestPath
  Ok "manifesto gravado: $ManifestPath"
  Write-Host ""
  Write-Host "Instalação concluída."
  Write-Host "MCP: simplicio serve --mcp --stdio"
  Write-Host "PATH: adicione $InstallDir ao PATH se necessário."
} finally {
  if (Test-Path $tempDir) { Remove-Item -Recurse -Force $tempDir -ErrorAction SilentlyContinue }
}
