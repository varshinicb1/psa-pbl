from setuptools import setup, find_packages

setup(
    name="dt-bescom",
    version="2.0.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "pandapower>=3.0",
    ],
)
