# User Mappings - Quick Start Guide

## For Everyone

### What is it?
`user_mappings.json` lets you add custom artist name mappings for Plex matching without editing any code.

### Why use it?
- Fix artist name mismatches specific to your Plex library
- Add regional variations or alternative spellings
- Test mappings before committing to code

---

## Docker Users

### Setup

The example file and README are already included in your Docker image at `/app/data/`.

### To Add Custom Mappings

1. **Create the file in your mounted volume:**
   ```bash
   # If using docker-compose
   vi ./data/user_mappings.json
   ```

2. **Add your mappings:**
   ```json
   {
     "mappings": {
       "YourArtist": "Correct Plex Name"
     }
   }
   ```

3. **Restart the container:**
   ```bash
   docker-compose restart
   ```

### Location
- File: `./data/user_mappings.json` (in your mounted volume)
- Template: `./data/user_mappings.json.example` (already included)
- Documentation: `./data/USER_MAPPINGS_README.md` (already included)

---

## Windows EXE Users

### Setup

The example file and README are included in the same folder as `Radio Monitor.exe`.

### To Add Custom Mappings

1. **Copy the template:**
   ```cmd
   copy "user_mappings.json.example" "user_mappings.json"
   ```

2. **Edit the file:**
   - Open `user_mappings.json` in Notepad or your favorite text editor
   - Add your mappings:
   ```json
   {
     "mappings": {
       "YourArtist": "Correct Plex Name"
     }
   }
   ```

3. **Save and restart Radio Monitor**

### Location
- All files in same folder as `Radio Monitor.exe`:
  - `Radio Monitor.exe`
  - `user_mappings.json.example` (template)
  - `USER_MAPPINGS_README.md` (documentation)
  - `user_mappings.json` (your custom mappings - you create this)

---

## Example Mappings

### Common Patterns

```json
{
  "mappings": {
    "Truncated Names": {
      "Whitney": "Whitney Houston",
      "Mariah": "Mariah Carey"
    },
    "Special Characters": {
      "Pnk": "P!NK",
      "Beyonce": "Beyoncé"
    },
    "Collaborations": {
      "Brooks Dunn": "Brooks & Dunn",
      "Dan Shay": "Dan + Shay"
    }
  }
}
```

### Remove the "comments" section before using - this is just for illustration:

```json
{
  "mappings": {
    "Whitney": "Whitney Houston",
    "Mariah": "Mariah Carey",
    "Pnk": "P!NK",
    "Beyonce": "Beyoncé",
    "Brooks Dunn": "Brooks & Dunn",
    "Dan Shay": "Dan + Shay"
  }
}
```

---

## Testing Your Mappings

### Quick Test

```python
from radio_monitor.plex import get_canonical_artist_name

result = get_canonical_artist_name("YourArtistName")
print(result)  # Should print your mapped name
```

### In Production

1. Add your mapping to `user_mappings.json`
2. Restart Radio Monitor
3. Create a Plex playlist
4. Check if the artist now matches!

---

## Troubleshooting

### "Mappings not working"

**Docker:**
- Make sure file is in `./data/` (mounted volume)
- Restart container: `docker-compose restart`
- Check logs: `docker-compose logs -f`

**Windows EXE:**
- Make sure file is in same folder as `Radio Monitor.exe`
- File must be named exactly: `user_mappings.json`
- Restart Radio Monitor

### "Invalid JSON"

**Common mistakes:**
- Using single quotes `'` instead of double quotes `"`
- Trailing commas: `{"a": "b",}` ← Remove comma
- Comments not supported in JSON (remove `//` or `/* */`)

**Test your JSON:**
```python
import json
json.load(open('user_mappings.json'))
# If no error, JSON is valid
```

---

## Built-in Mappings

Radio Monitor comes with 68+ built-in mappings including:
- Celine → Céline Dion
- Pnk → P!NK
- A Ha → A-ha
- Brooks Dunn → Brooks & Dunn
- Dan Shay → Dan + Shay
- And 60+ more!

Your `user_mappings.json` can override or add to these.

---

## Need Help?

See `USER_MAPPINGS_README.md` for complete documentation.
