#!/usr/bin/env python3
# -*- coding: utf-8 -*-

replacements = [
    ('🚩', '🔴'),
    ('🐺', '🔵'),
    ('💁‍♂️', '🟢'),
    ('📅', '🟡'),
    ('🐶', '🟣'),
    ('💅', '🟠'),
    ('🐋', '⚫'),
    ('👑', '💎'),
]

with open('templates/admin.html', 'r', encoding='utf-8') as f:
    content = f.read()

for old, new in replacements:
    content = content.replace(old, new)

with open('templates/admin.html', 'w', encoding='utf-8') as f:
    f.write(content)

print('Updated emojis successfully')
