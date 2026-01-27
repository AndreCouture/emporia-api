from setuptools import setup, find_packages

setup(
    name="emporia-api",
    version="0.1.0",
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
    description="A Python API for Emporia Energy devices",
    url="https://github.com/yourusername/emporia_api", # User should update this
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)
