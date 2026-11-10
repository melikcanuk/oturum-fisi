# oturum-fisi installer for OpenAI Codex on Windows (PowerShell 5.1+).
# Run in PowerShell (not inside Codex):
#   irm https://raw.githubusercontent.com/melikcanuk/oturum-fisi/main/codex/install.ps1 | iex
# It copies the skill to ~/.agents/skills/oturum-fisi, adds a Stop hook to ~/.codex/config.toml
# (after a backup) and builds the first index. Nothing else is changed.
$ErrorActionPreference = 'Stop'
$raw = 'https://raw.githubusercontent.com/melikcanuk/oturum-fisi/main/skills/oturum-fisi'
$utf8 = New-Object System.Text.UTF8Encoding($false)

function Find-Python {
    if ($env:OTURUM_FISI_PYTHON -and (Test-Path $env:OTURUM_FISI_PYTHON)) { return $env:OTURUM_FISI_PYTHON }
    foreach ($c in @(@('py', '-3'), @('python'), @('python3'))) {
        try {
            $exe = $c[0]; $rest = @($c | Select-Object -Skip 1) + @('-c', 'import sys; print(sys.executable)')
            $out = & $exe @rest 2>$null
            if ($LASTEXITCODE -eq 0 -and $out -and (Test-Path "$out".Trim())) { return "$out".Trim() }
        } catch {}
    }
    return $null
}

Write-Host '1/4 Python araniyor...'
$py = Find-Python
if (-not $py) {
    Write-Host '    Python bulunamadi. winget ile kuruluyor (birkac dakika surebilir)...'
    winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'User') + ';' + [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $py = Find-Python
    if (-not $py) {
        $guess = Get-ChildItem "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($guess) { $py = $guess.FullName }
    }
    if (-not $py) { throw 'Python kurulamadi. python.org adresinden Python 3 kurup bu komutu yeniden calistirin.' }
}
Write-Host "    Python: $py"

Write-Host '2/4 Skill kopyalaniyor...'
$skill = if ($env:OTURUM_FISI_SKILLS_DIR) { Join-Path $env:OTURUM_FISI_SKILLS_DIR 'oturum-fisi' } else { Join-Path $HOME '.agents\skills\oturum-fisi' }
New-Item -ItemType Directory -Force $skill | Out-Null
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$fis = Join-Path $skill 'fis.py'
(New-Object Net.WebClient).DownloadFile("$raw/fis.py", $fis)
$wc = New-Object Net.WebClient; $wc.Encoding = [Text.Encoding]::UTF8
$md = $wc.DownloadString("$raw/SKILL.md")
$md = $md.Replace('python "${CLAUDE_SKILL_DIR}/fis.py"', "& `"$py`" `"$fis`"")
[IO.File]::WriteAllText((Join-Path $skill 'SKILL.md'), $md, $utf8)
Write-Host "    $skill"

Write-Host '3/4 Kanca (hook) ekleniyor...'
$codex = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME '.codex' }
New-Item -ItemType Directory -Force $codex | Out-Null
$cfg = Join-Path $codex 'config.toml'
$old = if (Test-Path $cfg) { [IO.File]::ReadAllText($cfg) } else { '' }
if ($old -match 'oturum-fisi') {
    Write-Host '    Kanca zaten var, dokunulmadi.'
} else {
    if ($old) { Copy-Item $cfg "$cfg.yedek-oturum-fisi" -Force }
    $p = $py.Replace('\', '\\'); $f = $fis.Replace('\', '\\')
    $block = "`n# >>> oturum-fisi >>>`n[[hooks.Stop]]`n`n[[hooks.Stop.hooks]]`ntype = `"command`"`n" +
             "command = `"'$p' '$f' --only -`"`ncommand_windows = `"& '$p' '$f' --only -`"`ntimeout = 60`n# <<< oturum-fisi <<<`n"
    [IO.File]::AppendAllText($cfg, $block, $utf8)
    Write-Host "    $cfg (yedek: config.toml.yedek-oturum-fisi)"
}

Write-Host '4/4 Ilk dizin olusturuluyor...'
& $py $fis
$out = if ($env:OTURUM_FISI_DIR) { $env:OTURUM_FISI_DIR } else { Join-Path $HOME '.oturum-fisi' }
$n = @(Get-Content (Join-Path $out 'INDEX.md')).Count - 1
Write-Host ''
Write-Host "TAMAM: $n oturum fislendi -> $out\INDEX.md"
Write-Host "Son adim: Codex'i kapatip yeniden acin. Yeni kancayi (oturum-fisi) onaylamanizi isterse ONAYLAYIN."
Write-Host "Sonra Codex'e sorun: gecen sefer ne yapmistik?"
