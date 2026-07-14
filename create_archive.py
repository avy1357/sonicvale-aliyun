# -*- coding: utf-8 -*-
import os
import shutil
import zipfile

archive_path = r"d:\aliyun-sonicvale\zip归档\015_SonicVale_VolcanoVoiceIntegrationComplete.zip"
source_path = r"d:\aliyun-sonicvale\SonicVale"

if os.path.exists(archive_path):
    os.remove(archive_path)

with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
    for root, dirs, files in os.walk(source_path):
        for file in files:
            file_path = os.path.join(root, file)
            arcname = os.path.relpath(file_path, os.path.dirname(source_path))
            zipf.write(file_path, arcname)
            print(f"Added: {arcname}")

print(f"Done: {archive_path}")
