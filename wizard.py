"""
Setup and packaging script for Antigravity Telegram Remote Bridge.
Usage:
  pip install -e .              (Install global CLI `antigravity-bridge`)
  python setup.py               (Launch interactive setup wizard)
"""
import sys

# If invoked by pip / build tools:
if len(sys.argv) > 1 and any(arg in sys.argv[1:] for arg in ["install", "develop", "bdist_wheel", "egg_info", "sdist", "build"]):
    from setuptools import setup, find_packages
    setup(
        name="antigravity-telegram-bridge",
        version="2.1.0",
        description="Remote control Google Antigravity & AGY Terminal from Telegram on any device",
        packages=find_packages(),
        install_requires=[
            "requests>=2.31.0",
            "Pillow>=10.0.0",
        ],
        entry_points={
            "console_scripts": [
                "antigravity-bridge = core.cli:main",
                "agy-bridge = core.cli:main",
            ]
        },
        python_requires=">=3.10",
    )
else:
    # Run the interactive wizard
    from wizard import run_wizard
    try:
        run_wizard()
    except KeyboardInterrupt:
        print("\n\nSetup cancelled by user.")
        sys.exit(0)
