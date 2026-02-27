import re

# Read the file
with open('templates/admin.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Map old emoji to new emoji
emoji_map = {
    '🚩': '🔴',
    '🐺': '🔵',
    '💁‍♂️': '🟢',
    '📅': '🟡',
    '🐶': '🟣',
    '💅': '🟠',
    '🐋': '⚫',
    '👑': '💎',
}

# Replace each old emoji with new one throughout the file
for old, new in emoji_map.items():
    content = content.replace(old, new)

# Write back
with open('templates/admin.html', 'w', encoding='utf-8') as f:
    f.write(content)

print('Successfully updated all emojis!')
