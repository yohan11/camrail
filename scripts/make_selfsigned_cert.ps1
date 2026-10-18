# ==============================================================================
# CAMRAIL RailMind Lite - Generation de Certificat SSL/TLS Auto-Signe (PowerShell)
# ==============================================================================
# Ce script genere une paire de cles (certificat X.509 et cle privee RSA 2048)
# pour le developpement local et la validation du profil HTTPS Nginx sous Windows.
#
# UTILISATION EN PRODUCTION AVEC UNE AUTORITE INTERNE CAMRAIL (PKI / AD CS) :
# 1. En environnement de production ferroviaire, N'UTILISEZ PAS ce certificat auto-signe.
# 2. Faites emettre un certificat serveur officiel aupres de la PKI interne CAMRAIL :
#    - Nom de domaine (CN) : ex. railmind.camrail.net ou adresse IP du serveur
#    - Deposez la cle privee serveur dans : deploy/certs/privkey.pem
#    - Deposez la chaine complete de certificats (certificat serveur + autorites
#      intermediaires et racine CAMRAIL) dans : deploy/certs/fullchain.pem
# 3. Verifiez que l'autorite racine CAMRAIL est bien approuvee dans le magasin
#    "Autorites de certification racines de confiance" des postes clients CAMRAIL.
# ==============================================================================

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $ScriptDir
$CertsDir = Join-Path $RootDir "deploy\certs"

if (-not (Test-Path $CertsDir)) {
    New-Item -ItemType Directory -Path $CertsDir -Force | Out-Null
}

$PrivKeyPath = Join-Path $CertsDir "privkey.pem"
$FullChainPath = Join-Path $CertsDir "fullchain.pem"

Write-Host "==============================================================================" -ForegroundColor Cyan
Write-Host "  Generation du certificat auto-signe CAMRAIL RailMind Lite (Test/Dev)..." -ForegroundColor Cyan
Write-Host "  Emplacement cible : $CertsDir" -ForegroundColor Cyan
Write-Host "==============================================================================" -ForegroundColor Cyan

# 1. Tentative avec openssl si disponible dans le PATH
$opensslCmd = Get-Command openssl -ErrorAction SilentlyContinue

if ($opensslCmd) {
    & openssl req -x509 -nodes -days 365 -newkey rsa:2048 `
        -keyout "$PrivKeyPath" `
        -out "$FullChainPath" `
        -subj "/C=CM/ST=Littoral/L=Douala/O=CAMRAIL/OU=DSI/CN=railmind.camrail.net" `
        -addext "subjectAltName=DNS:localhost,DNS:railmind.camrail.net,IP:127.0.0.1"

    Write-Host "`n[OK] Certificats generes avec succes via OpenSSL :" -ForegroundColor Green
    Write-Host "  - Cle privee : $PrivKeyPath" -ForegroundColor Gray
    Write-Host "  - Certificat : $FullChainPath" -ForegroundColor Gray
} else {
    # 2. Generation robuste via Python (cryptography)
    Write-Host "`n[i] OpenSSL absent du PATH. Generation via Python..." -ForegroundColor Yellow
    $pythonCandidates = @(
        "$RootDir\backend\venv\Scripts\python.exe",
        "D:\camrail-main\backend\venv\Scripts\python.exe",
        "$RootDir\venv\Scripts\python.exe"
    )
    $pythonCmd = $null
    foreach ($cand in $pythonCandidates) {
        if (Test-Path $cand) {
            $pythonCmd = $cand
            break
        }
    }
    if (-not $pythonCmd) {
        $cmdObj = Get-Command python -ErrorAction SilentlyContinue
        if ($cmdObj) { $pythonCmd = $cmdObj.Source }
        else { $pythonCmd = "python" }
    }

    $pyScript = @"
import datetime, ipaddress
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa

key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
subject = issuer = x509.Name([
    x509.NameAttribute(NameOID.COUNTRY_NAME, 'CM'),
    x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, 'Littoral'),
    x509.NameAttribute(NameOID.LOCALITY_NAME, 'Douala'),
    x509.NameAttribute(NameOID.ORGANIZATION_NAME, 'CAMRAIL'),
    x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, 'DSI'),
    x509.NameAttribute(NameOID.COMMON_NAME, 'railmind.camrail.net'),
])

san = x509.SubjectAlternativeName([
    x509.DNSName('localhost'),
    x509.DNSName('railmind.camrail.net'),
    x509.IPAddress(ipaddress.IPv4Address('127.0.0.1')),
])

cert = (
    x509.CertificateBuilder()
    .subject_name(subject)
    .issuer_name(issuer)
    .public_key(key.public_key())
    .serial_number(x509.random_serial_number())
    .not_valid_before(datetime.datetime.now(datetime.timezone.utc))
    .not_valid_after(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=365))
    .add_extension(san, critical=False)
    .sign(key, hashes.SHA256())
)

with open(r'$PrivKeyPath', 'wb') as f:
    f.write(key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption()
    ))

with open(r'$FullChainPath', 'wb') as f:
    f.write(cert.public_bytes(serialization.Encoding.PEM))

print('GENERATED_OK')
"@

    $res = & $pythonCmd -c $pyScript
    if ($res -like "*GENERATED_OK*") {
        Write-Host "[OK] Certificats generes avec succes :" -ForegroundColor Green
        Write-Host "  - Cle privee : $PrivKeyPath" -ForegroundColor Gray
        Write-Host "  - Certificat : $FullChainPath" -ForegroundColor Gray
    } else {
        Write-Error "Echec de generation des certificats."
    }
}

Write-Host "`nPour activer le profil HTTPS sous Docker Compose :" -ForegroundColor Cyan
Write-Host "  docker compose --profile https up -d" -ForegroundColor White
