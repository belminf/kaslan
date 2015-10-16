from setuptools import setup
from kaslan import __version__

setup(
    name='kaslan',
    packages=['kaslan', ],
    version=__version__,
    install_requires=[
        'PyYAML',
        'argparse',
        'netaddr',
        'pyvmomi==5.5.0.2014.1.1',
        'requests',
    ],
    entry_points={
        'console_scripts': [
            'kaslan = kaslan.__main__:main',
        ],
    },
)
