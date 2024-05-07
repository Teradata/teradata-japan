# -*- coding: utf-8 -*-

import os
from setuptools import setup

readmefile = os.path.join(os.path.dirname(__file__), "README.md")
with open(readmefile) as f:
    readme = f.read()

setup(
    name='tdquiz',
    version='0.0.1',
    description='Teradata SQL Quiz',
    author='Kota Mori', 
    author_email='kota.mori@teradata.com',
    long_description=readme,
    long_description_content_type='text/markdown',
    
    py_modules=['tdquiz'],
    install_requires=['teradatasql', 'teradatasqlalchemy', 'toml', 'IPython', 'tqdm', 'pandas', 'sqlalchemy']
)
