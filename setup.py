"""pan_deduper"""
import setuptools

__version__ = "0.0.7"
__author__ = "Ryan Gillespie"

setuptools.setup(
    name="pan_deduper",
    version=__version__,
    packages=["pan_deduper"],
    install_requires=[
        "httpx==0.23.0",
        "typer==0.6.1",
        "lxml==4.9.1",
        "rich==12.5.1",
        "deepdiff==5.8.1",
        "xmltodict==0.13.0",
    ],
    classifiers=[
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Operating System :: POSIX :: Linux",
        "Operating System :: MacOS",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3 :: Only",
    ],
    python_requires=">=3.7",
    entry_points={"console_scripts": ["deduper = pan_deduper.cli:app"]},
)
