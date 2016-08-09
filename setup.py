"""Setup script."""


# [ Imports ]
from setuptools import setup, find_packages


# [ Setup ]
setup(
    name='a_sync',
    version='0.3.0',
    description='async helper library.',
    long_description=open('LONG_DESCRIPTION.rst').read(),
    url='https://github.com/notion/a_sync',
    author='toejough',
    author_email='toejough@gmail.com',
    license='Apache 2.0',
    classifiers=[
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 3 - Alpha',

        # Indicate who your project is intended for
        'Intended Audience :: Developers',

        # Pick your license as you wish (should match "license" above)
        'License :: OSI Approved :: Apache 2.0 License',

        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both.
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
    ],
    keywords="async await asynchronous library parallel background",
    packages=find_packages(),
    install_requires=[],
)