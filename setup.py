from setuptools import setup, find_packages

setup(
    name="antigravity-telegram-bridge",
    version="2.1.0",
    description="Remote Telegram bridge for Google Antigravity and AGY Terminal Engine",
    packages=find_packages(),
    py_modules=["bridge", "wizard"],
    install_requires=[
        "requests>=2.31.0",
        "Pillow>=10.0.0",
        "SpeechRecognition>=3.10.0",
        "imageio-ffmpeg>=0.4.9",
        "psutil>=5.9.0",
    ],
    entry_points={
        "console_scripts": [
            "antigravity-bridge = core.cli:main",
            "agy-bridge = core.cli:main",
        ],
    },
)
