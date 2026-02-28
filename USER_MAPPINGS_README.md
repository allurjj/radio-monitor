# User-Defined Artist Name Mappings

## Overview

You can add your own artist name mappings without editing any code! This is useful for:
- Artist names specific to your Plex library
- Regional variations or alternative spellings
- Testing new mappings before committing to code

## How to Use

### Step 1: Create the File

Copy the example file:
```bash
cp user_mappings.json.example user_mappings.json
```

### Step 2: Edit the File

Open `user_mappings.json` and add your mappings:

```json
{
  "mappings": {
    "YourArtistName": "Correct Plex Artist Name",
    "Another Artist": "Another Artist feat. Someone",
    "Truncated Name": "Full Artist Name"
  }
}
```

### Step 3: Restart Radio Monitor

Restart the GUI for changes to take effect:
```bash
# Stop GUI (Ctrl+C)
# Start again
python -m radio_monitor.cli --gui
```

## Examples

### Truncated Names
```json
{
  "mappings": {
    "Whitney": "Whitney Houston",
    "Mariah": "Mariah Carey",
    "Cher": "Cher"
  }
}
```

### Special Characters
```json
{
  "mappings": {
    "Pnk": "P!NK",
    "Beyonce": "Beyoncé",
    "Andre 3000": "André 3000"
  }
}
```

### Collaborations
```json
{
  "mappings": {
    "Brooks Dunn": "Brooks & Dunn",
    "Dan Shay": "Dan + Shay",
    "Daryl Hall John Oates": "Daryl Hall & John Oates"
  }
}
```

### Override Built-In Mappings
```json
{
  "mappings": {
    "Celine": "Celine Dion"  // Override built-in "Céline Dion"
  }
}
```

## Features

- ✅ **Case-insensitive lookup**: "beyonce" and "Beyonce" both work
- ✅ **Overrides built-ins**: Your mappings take precedence
- ✅ **JSON format**: Easy to edit and validate
- ✅ **Hot-reload**: Changes apply when you restart GUI
- ✅ **No code changes**: Safe and reversible

## File Format

Must be valid JSON:
- Use double quotes `"` not single quotes `'`
- No trailing commas
- Use proper escaping for special characters

### Correct Format:
```json
{
  "mappings": {
    "Artist": "Name",
    "Another": "Name"
  }
}
```

### Incorrect Format:
```json
{
  'mappings': {           // ❌ Use double quotes
    'Artist': 'Name',     // ❌ Use double quotes
    "Another": "Name",    // ❌ No trailing comma
  }
}
```

## Troubleshooting

### Mappings Not Working?

1. **Check JSON format:**
   ```bash
   python -c "import json; print(json.load(open('user_mappings.json')))"
   ```

2. **Check file location:**
   - Must be in project root (same folder as radio_monitor/)
   - File must be named exactly: `user_mappings.json`

3. **Restart GUI:**
   - Changes only apply on startup

4. **Check logs:**
   - Look for "User artist mapping" messages in logs

### Test Your Mappings

```python
from radio_monitor.plex import get_canonical_artist_name

result = get_canonical_artist_name("YourArtistName")
print(result)  # Should print "Correct Plex Artist Name"
```

## Built-in Mappings

Radio Monitor comes with 68+ built-in mappings including:
- Truncated names (Celine → Céline Dion)
- Special characters (Pnk → P!NK)
- Hyphen variations (A Ha → A-ha)
- Collaborations (Brooks Dunn → Brooks & Dunn)
- Unicode normalization (All‐4‐One → All-4-One)

Your `user_mappings.json` can override or add to these.

## Advanced: Override Everything

If you want to completely disable built-in mappings, you can edit the code, but using `user_mappings.json` is safer and recommended.

## Support

If you find mappings that would benefit everyone, please share them! They can be added to the built-in mapping table for all users.
