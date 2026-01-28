"""Setup configuration for emporia-api.

Note: This file is maintained for backwards compatibility.
The primary configuration is in pyproject.toml (PEP 621).
"""

from setuptools import setup, find_packages
import os

# Read version from __version__.py
version = {}
version_file = os.path.join(os.path.dirname(__file__), "emporia_api", "__version__.py")
with open(version_file) as f:
    exec(f.read(), version)

setup(
    name="emporia-api",
    version=version["__version__"],
    packages=find_packages(),
    install_requires=[
        "requests>=2.32.5",
        "boto3>=1.42.21",
        "warrant>=0.6.1",
        "python-jose[cryptography]>=3.3.0",
        "cryptography>=46.0.3",
        "python-dateutil>=2.9.0.post0",
    ],
    author="Andre Couture",
    description="Python API wrapper for Emporia Energy devices",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/AndreCouture/emporia-api",
    project_urls={
        "Bug Reports": "https://github.com/AndreCouture/emporia-api/issues",
        "Source": "https://github.com/AndreCouture/emporia-api",
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Home Automation",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
    ],
    python_requires='>=3.9',
    keywords="emporia energy monitoring ev-charger home-automation iot",
)
