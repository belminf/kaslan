from setuptools import setup
from kaslan import __version__, __description__

setup(
    name='kaslan',
    packages=['kaslan',],
    version=__version__,
    install_requires=[
        'netaddr',
        'pyvmomi',
        'PyYAML',
        'argparse',
    ],
    entry_points={
        'console_scripts': [
            'kaslan = kaslan.__main__:main',
        ],
    },
)
