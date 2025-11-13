# Building Windows Executable for Arqueos Robot

This guide explains how to create a standalone Windows executable (.exe) for the Arqueos Robot GUI application.

## Prerequisites

1. **Python Installation**: Ensure Python 3.8+ is installed on Windows
2. **All Dependencies**: Install all required packages from requirements.txt
   ```bash
   pip install -r requirements.txt
   ```
3. **PyInstaller**: Install PyInstaller
   ```bash
   pip install pyinstaller
   ```

## Method 1: Quick Build (Simple)

Run this single command to create the executable:

```bash
pyinstaller --onefile --windowed --name ArqueosRobot run_gui.py
```

**Options explained:**
- `--onefile`: Creates a single executable file (everything bundled)
- `--windowed`: No console window appears (GUI only)
- `--name ArqueosRobot`: Sets the executable name

**Result**: The executable will be in `dist/ArqueosRobot.exe`

## Method 2: Using the .spec File (Recommended)

For more control and reproducible builds, use the provided `.spec` file:

```bash
pyinstaller ArqueosRobot.spec
```

This method:
- Includes all necessary hidden imports
- Bundles the .env.example file
- Optimizes the build with UPX compression
- Hides the console window for a clean GUI experience

**Result**: The executable will be in `dist/ArqueosRobot.exe`

## Method 3: Advanced Build with Icon

If you have an icon file (e.g., `icon.ico`), modify the command:

```bash
pyinstaller --onefile --windowed --name ArqueosRobot --icon=icon.ico run_gui.py
```

Or edit `ArqueosRobot.spec` and change:
```python
icon=None,  # Change to icon='icon.ico'
```

## Distribution

After building, you'll find:
- `dist/ArqueosRobot.exe` - The executable to distribute
- `build/` - Temporary build files (can be deleted)
- `ArqueosRobot.spec` - Build specification (keep for rebuilding)

### What to Distribute:

**Minimal distribution (most common):**
```
ArqueosRobot.exe
.env.example (users rename to .env and configure)
```

**Complete distribution package:**
```
ArqueosRobot.exe
.env.example
README.md
GUI_README.md
```

## Configuration

Users will need to:
1. Copy `.env.example` to `.env`
2. Edit `.env` with their RabbitMQ credentials and other settings
3. Run `ArqueosRobot.exe`

## Troubleshooting

### Issue: Missing modules at runtime
**Solution**: Add the missing module to `hiddenimports` in `ArqueosRobot.spec`:
```python
hiddenimports=[
    'missing_module_name',
    # ... other imports
],
```

### Issue: Executable is too large
**Solutions:**
1. Use `--onedir` instead of `--onefile` (creates a folder with dependencies)
2. Remove unused dependencies from requirements.txt
3. Ensure UPX is installed for better compression

### Issue: Antivirus flags the executable
**Solution**: This is common with PyInstaller. You can:
1. Sign the executable with a code signing certificate
2. Submit to antivirus vendors as a false positive
3. Use `--onedir` mode which is less likely to be flagged

### Issue: Console window appears
**Solution**: Make sure you're using `--windowed` flag or `console=False` in .spec file

### Issue: Application crashes without error
**Solution**: Build with console enabled temporarily to see errors:
```bash
pyinstaller --onefile --console --name ArqueosRobotDebug run_gui.py
```
Run the debug version to see error messages.

## Build on Different Platforms

**Important**: PyInstaller creates executables for the platform you build on:
- Build on Windows → Windows .exe
- Build on Linux → Linux executable
- Build on macOS → macOS app

To create a Windows executable, you **must build on a Windows machine**.

## Alternative: Cross-Platform with cx_Freeze

If you need cross-platform builds, consider cx_Freeze:

```bash
pip install cx_Freeze
```

Create `setup.py`:
```python
from cx_Freeze import setup, Executable

setup(
    name="ArqueosRobot",
    version="1.0",
    description="Arqueos Robot GUI Application",
    executables=[Executable("run_gui.py", base="Win32GUI")]
)
```

Build:
```bash
python setup.py build
```

## Testing the Executable

1. Copy the .exe to a clean Windows machine without Python
2. Ensure .env file is in the same directory
3. Run the executable
4. Test all functionality (RabbitMQ connection, task processing, etc.)

## File Size Optimization

Typical executable sizes:
- `--onefile`: ~100-200 MB (all dependencies bundled)
- `--onedir`: Total folder ~150-250 MB but faster startup

To reduce size:
1. Remove testing dependencies (pytest, etc.) before building
2. Use virtual environment with only required packages
3. Consider splitting into multiple executables if needed
