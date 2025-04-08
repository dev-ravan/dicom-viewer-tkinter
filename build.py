import PyInstaller.__main__
import os
import shutil
import platform

# Application name
APP_NAME = "Dicom Viewer"

# Main script file
SCRIPT_FILE = "app.py"  # Change this to your script name

# Additional data files (like images, data files)
DATA_FILES = []

# Icon file (optional)
ICON_FILE = None  # or "your_icon.ico"

# Build options
options = [
    '--name=%s' % APP_NAME,
    '--onefile',
    '--windowed',
    '--add-data=measurements.csv;.',  # Include your data files
    '--add-data=screenshot.png;.' if os.path.exists('screenshot.png') else '',
    '--icon=%s' % ICON_FILE if ICON_FILE else '',
    '--noconsole',
    '--clean'
]

# Remove empty options
options = [opt for opt in options if opt]

# Add the main script
options.append(SCRIPT_FILE)

# Run PyInstaller
PyInstaller.__main__.run(options)

print("\nBuild completed!")
print(f"The executable is in the 'dist' folder: {os.path.join('dist', APP_NAME + ('.exe' if platform.system() == 'Windows' else ''))}")