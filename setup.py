from setuptools import setup, find_packages
from kaslan import __version__

setup(
    name='kaslan',
    packages=find_packages(),
    version=__version__,
    install_requires=[
        'PyYAML',
        'argparse',
        'netaddr',
        'tzlocal',
        'pyvmomi==5.5.0.2014.1.1',
        'requests==2.5.3',
    ],
    entry_points={
        'console_scripts': [
            'kaslan = kaslan.cli:main',
        ],
    },
)
