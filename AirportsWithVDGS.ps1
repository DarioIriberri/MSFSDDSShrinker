$CommunityPath = "C:\Users\dazz\AppData\Roaming\Microsoft Flight Simulator\Packages\Community"

Get-ChildItem -Path $CommunityPath -Directory | ForEach-Object {
    $pkg = $_
    $vdgsFiles = Get-ChildItem -Path $pkg.FullName -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Name -match 'vdgs' -or
            ($_.Extension -eq '.xml' -and (Select-String -Path $_.FullName -Pattern '<AerosoftVDGS|aerosoft-vdgs' -Quiet -ErrorAction SilentlyContinue))
        }

    if ($vdgsFiles) {
        [PSCustomObject]@{
            Package = $pkg.Name
            VDGSFiles = ($vdgsFiles.Name -join ', ')
        }
    }
} | Format-Table -AutoSize

Pause