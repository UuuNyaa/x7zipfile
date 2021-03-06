# -*- coding: utf-8 -*-
# Copyright 2021 UuuNyaa <UuuNyaa@gmail.com>
# This file is part of x7zipfile.

import importlib
import os

namespace = 'x7zipfile'
loader = importlib.machinery.SourceFileLoader(
    namespace,
    os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'src',
        'x7zipfile.py'
    )
)

x7zipfile = loader.load_module(namespace)
x7ZipInfo = x7zipfile.x7ZipInfo
x7ZipFile = x7zipfile.x7ZipFile
x7ZipNoEntry = x7zipfile.x7ZipNoEntry
x7ZipExecError = x7zipfile.x7ZipNoEntry
