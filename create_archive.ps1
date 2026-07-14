[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$archivePath = "d:\aliyun-sonicvale\zip归档\015_SonicVale_VolcanoVoiceIntegrationComplete.zip"
$sourcePath = "d:\aliyun-sonicvale\SonicVale"
if (Test-Path $archivePath) {
    Remove-Item $archivePath -Force
}
Compress-Archive -Path $sourcePath -DestinationPath $archivePath -Force
Write-Host "Done"
