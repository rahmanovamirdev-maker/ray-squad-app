# Fix emojis in admin.html
$filePath = 'templates\admin.html'
$content = Get-Content -Path $filePath -Raw -Encoding UTF8

# Define replacements - maps entire option lines
$replacements = @{
    '<option value="Delta">🚩 Delta</option>' = '<option value="Delta">🔴 Delta</option>';
    '<option value="Den">🐺 Den</option>' = '<option value="Den">🔵 Den</option>';
    '<option value="Amir">💁‍♂️ Amir</option>' = '<option value="Amir">🟢 Amir</option>';
    '<option value="404">📅 404</option>' = '<option value="404">🟡 404</option>';
    '<option value="Bobik">🐶 Bobik</option>' = '<option value="Bobik">🟣 Bobik</option>';
    '<option value="Oir">💅 Oir</option>' = '<option value="Oir">🟠 Oir</option>';
    '<option value="Gordon">🐋 Gordon</option>' = '<option value="Gordon">⚫ Gordon</option>';
    '<option value="Rey">👑 Rey</option>' = '<option value="Rey">💎 Rey</option>';
}

$count = 0
foreach ($old in $replacements.Keys) {
    $new = $replacements[$old]
    if ($content -like "*$old*") {
        $content = $content -replace [regex]::Escape($old), $new
        $count++
        Write-Host "Replaced: $old"
    }
}

# Write back
$content | Set-Content -Path $filePath -Encoding UTF8 -NoNewline

Write-Host "Updated $count replacements"
