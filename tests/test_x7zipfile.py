# -*- coding: utf-8 -*-
# Copyright 2021 UuuNyaa <UuuNyaa@gmail.com>
# This file is part of x7zipfile.

import os
import unittest

from x7zipfile.x7zipfile import x7ZipFile

from .archives import ARCHIVES, ARCHIVES_PATH


class TestCase(unittest.TestCase):
    def test_archive_list(self):
        for archive_name, password, expected_infolist in ARCHIVES:
            with self.subTest():
                with x7ZipFile(os.path.join(ARCHIVES_PATH, archive_name), pwd=password) as zipfile:
                    for actual_info, expected_info in zip(zipfile.infolist(), expected_infolist):
                        actual_info.needs_password()
                        actual_info.is_dir()
                        self.assertEqual(actual_info, expected_info)
