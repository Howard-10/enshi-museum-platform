[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string] $PrimarySource,
    [Parameter(Mandatory = $true)] [string] $SupplementSource,
    [Parameter(Mandatory = $true)] [string] $MediaSource,
    [Parameter(Mandatory = $true)] [string] $TargetRoot,
    [Parameter(Mandatory = $true)] [string] $PrimaryTargetFolder,
    [Parameter(Mandatory = $true)] [string] $SupplementTargetFolder,
    [Parameter(Mandatory = $true)] [string] $MediaTargetFolder,
    [Parameter(Mandatory = $true)] [string] $AuditFolderName,
    [Parameter(Mandatory = $true)] [string] $ConflictFolderName,
    [switch] $DryRun
)

$ErrorActionPreference = 'Stop'

function Get-NormalizedHash {
    param([Parameter(Mandatory = $true)] [string] $Path)
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToUpperInvariant()
}

function Get-UniqueConflictPath {
    param(
        [Parameter(Mandatory = $true)] [string] $DesiredPath,
        [Parameter(Mandatory = $true)] [string] $Hash
    )

    if (-not (Test-Path -LiteralPath $DesiredPath)) {
        return $DesiredPath
    }

    if ((Get-NormalizedHash -Path $DesiredPath) -eq $Hash) {
        return $DesiredPath
    }

    $directory = Split-Path -Parent $DesiredPath
    $baseName = [System.IO.Path]::GetFileNameWithoutExtension($DesiredPath)
    $extension = [System.IO.Path]::GetExtension($DesiredPath)
    $number = 2
    do {
        $candidate = Join-Path $directory ("{0}__source_conflict_{1}{2}" -f $baseName, $number, $extension)
        $number++
    } while (Test-Path -LiteralPath $candidate)
    return $candidate
}

function Add-Record {
    param(
        [Parameter(Mandatory = $true)] [AllowEmptyCollection()] [System.Collections.Generic.List[object]] $List,
        [string] $Status,
        [string] $SourceAlias,
        [string] $SourcePath,
        [string] $TargetPath,
        [string] $Hash,
        [Int64] $Bytes,
        [string] $RelatedPath,
        [string] $Note
    )

    $List.Add([pscustomobject]@{
        status = $Status
        source_alias = $SourceAlias
        source_path = $SourcePath
        target_path = $TargetPath
        sha256 = $Hash
        bytes = $Bytes
        related_path = $RelatedPath
        note = $Note
    })
}

foreach ($path in @($PrimarySource, $SupplementSource, $MediaSource, $TargetRoot)) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Path not found: $path"
    }
}

$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$auditRoot = Join-Path $TargetRoot $AuditFolderName
$reportDirectory = Join-Path $auditRoot ("old-project-data-migration-" + $timestamp)
$conflictRoot = Join-Path $TargetRoot $ConflictFolderName

if (-not $DryRun) {
    New-Item -ItemType Directory -Force -Path $reportDirectory | Out-Null
    New-Item -ItemType Directory -Force -Path $conflictRoot | Out-Null
}

$sources = @(
    [pscustomobject]@{ Alias = 'primary'; Root = $PrimarySource; DestinationFolder = $PrimaryTargetFolder },
    [pscustomobject]@{ Alias = 'legacy_supplement'; Root = $SupplementSource; DestinationFolder = $SupplementTargetFolder },
    [pscustomobject]@{ Alias = 'media'; Root = $MediaSource; DestinationFolder = $MediaTargetFolder }
)

$hashToCanonicalPath = @{}
$pathToHash = @{}

Write-Output 'Indexing existing destination files with SHA-256...'
$existingFiles = @(Get-ChildItem -LiteralPath $TargetRoot -File -Recurse -Force | Where-Object {
    $_.FullName -notlike (Join-Path $auditRoot '*')
})
foreach ($file in $existingFiles) {
    $hash = Get-NormalizedHash -Path $file.FullName
    $pathToHash[$file.FullName] = $hash
    if (-not $hashToCanonicalPath.ContainsKey($hash)) {
        $hashToCanonicalPath[$hash] = $file.FullName
    }
}

$records = New-Object 'System.Collections.Generic.List[object]'
$sourceCount = 0
$sourceBytes = [Int64]0

foreach ($source in $sources) {
    $files = @(Get-ChildItem -LiteralPath $source.Root -File -Recurse -Force)
    Write-Output ("Processing {0}: {1} files..." -f $source.Alias, $files.Count)

    foreach ($file in $files) {
        $sourceCount++
        $sourceBytes += $file.Length
        $relativePath = $file.FullName.Substring($source.Root.Length).TrimStart('\')
        $destinationRoot = Join-Path $TargetRoot $source.DestinationFolder
        $desiredPath = Join-Path $destinationRoot $relativePath
        $hash = Get-NormalizedHash -Path $file.FullName

        if (Test-Path -LiteralPath $desiredPath) {
            $destinationHash = $pathToHash[$desiredPath]
            if (-not $destinationHash) {
                $destinationHash = Get-NormalizedHash -Path $desiredPath
                $pathToHash[$desiredPath] = $destinationHash
            }

            if ($destinationHash -eq $hash) {
                Add-Record -List $records -Status 'skipped_exact_duplicate' -SourceAlias $source.Alias -SourcePath $file.FullName -TargetPath $desiredPath -Hash $hash -Bytes $file.Length -RelatedPath $desiredPath -Note 'Same relative path and identical SHA-256.'
                continue
            }

            $conflictPath = Join-Path (Join-Path $conflictRoot $source.Alias) $relativePath
            $conflictPath = Get-UniqueConflictPath -DesiredPath $conflictPath -Hash $hash
            if (Test-Path -LiteralPath $conflictPath) {
                Add-Record -List $records -Status 'skipped_conflict_duplicate' -SourceAlias $source.Alias -SourcePath $file.FullName -TargetPath $conflictPath -Hash $hash -Bytes $file.Length -RelatedPath $desiredPath -Note 'Conflict copy already exists with identical SHA-256; original destination was not changed.'
                continue
            }

            if (-not $DryRun) {
                New-Item -ItemType Directory -Force -Path (Split-Path -Parent $conflictPath) | Out-Null
                Copy-Item -LiteralPath $file.FullName -Destination $conflictPath -Force:$false
            }
            $pathToHash[$conflictPath] = $hash
            if (-not $hashToCanonicalPath.ContainsKey($hash)) {
                $hashToCanonicalPath[$hash] = $conflictPath
            }
            Add-Record -List $records -Status 'copied_conflict_for_review' -SourceAlias $source.Alias -SourcePath $file.FullName -TargetPath $conflictPath -Hash $hash -Bytes $file.Length -RelatedPath $desiredPath -Note 'Destination had different content; source was copied to conflict review and destination was not overwritten.'
            continue
        }

        if ($hashToCanonicalPath.ContainsKey($hash)) {
            $canonicalPath = $hashToCanonicalPath[$hash]
            Add-Record -List $records -Status 'skipped_content_duplicate' -SourceAlias $source.Alias -SourcePath $file.FullName -TargetPath $desiredPath -Hash $hash -Bytes $file.Length -RelatedPath $canonicalPath -Note 'Identical content already exists elsewhere under the target knowledge base.'
            continue
        }

        if (-not $DryRun) {
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $desiredPath) | Out-Null
            Copy-Item -LiteralPath $file.FullName -Destination $desiredPath -Force:$false
        }
        $pathToHash[$desiredPath] = $hash
        $hashToCanonicalPath[$hash] = $desiredPath
        Add-Record -List $records -Status 'copied' -SourceAlias $source.Alias -SourcePath $file.FullName -TargetPath $desiredPath -Hash $hash -Bytes $file.Length -RelatedPath '' -Note 'Copied without overwriting an existing target file.'
    }
}

$summary = [ordered]@{
    generated_at = (Get-Date).ToString('o')
    source_file_count = $sourceCount
    source_total_bytes = $sourceBytes
    target_root = $TargetRoot
    copied = @($records | Where-Object { $_.status -eq 'copied' }).Count
    copied_conflict_for_review = @($records | Where-Object { $_.status -eq 'copied_conflict_for_review' }).Count
    skipped_exact_duplicate = @($records | Where-Object { $_.status -eq 'skipped_exact_duplicate' }).Count
    skipped_content_duplicate = @($records | Where-Object { $_.status -eq 'skipped_content_duplicate' }).Count
    skipped_conflict_duplicate = @($records | Where-Object { $_.status -eq 'skipped_conflict_duplicate' }).Count
    dry_run = [bool]$DryRun
}

if (-not $DryRun) {
    $records | Export-Csv -LiteralPath (Join-Path $reportDirectory 'file-manifest.csv') -NoTypeInformation -Encoding UTF8
    $summary | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $reportDirectory 'summary.json') -Encoding UTF8
    @(
        'Old project raw-data migration summary',
        ('Generated: ' + $summary.generated_at),
        ('Source files: ' + $summary.source_file_count),
        ('Source bytes: ' + $summary.source_total_bytes),
        ('Copied: ' + $summary.copied),
        ('Copied to conflict review: ' + $summary.copied_conflict_for_review),
        ('Skipped exact duplicates: ' + $summary.skipped_exact_duplicate),
        ('Skipped content duplicates: ' + $summary.skipped_content_duplicate),
        ('Skipped existing conflict duplicates: ' + $summary.skipped_conflict_duplicate),
        'D drive source files were never changed or deleted.'
    ) | Set-Content -LiteralPath (Join-Path $reportDirectory 'README.txt') -Encoding UTF8
}

$summary | ConvertTo-Json
if (-not $DryRun) {
    Write-Output ("Report directory: " + $reportDirectory)
}
