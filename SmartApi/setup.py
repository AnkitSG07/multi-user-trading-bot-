from setuptools import setup, find_packages

setup(
    name="SmartApi",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "requests",  # or any other dependency used inside SmartApi
    ],
    include_package_data=True,
)
