import setuptools

with open("README.md", "r") as readme:
    long_description = readme.read()

setuptools.setup(
    name="redis-spaceship",
    version="1.0",
    author="Andrew Brookins",
    author_email="andrew@spellbookpress.com",
    description="Redis-powered spaceship",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/abrookins/redis-spaceship",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.8'
)
