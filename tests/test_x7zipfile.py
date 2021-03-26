# -*- coding: utf-8 -*-
# Copyright 2021 UuuNyaa <UuuNyaa@gmail.com>
# This file is part of x7zipfile.

import glob
import os
import shutil
import stat
import tempfile
import unittest

from tests import x7zipfile

from .archives import ARCHIVES, ARCHIVES_PATH


class TestCase(unittest.TestCase):
    def test_archive_list(self):
        for archive_name, password, _, expected_infolist in ARCHIVES:
            with self.subTest():
                with x7zipfile.x7ZipFile(os.path.join(ARCHIVES_PATH, archive_name), pwd=password) as zipfile:
                    for actual_info, expected_info in zip(zipfile.infolist(), expected_infolist):
                        actual_info.needs_password()
                        actual_info.is_dir()
                        self.assertEqual(actual_info, expected_info)

    def test_archive_extractall(self):
        for archive_name, password, error_message, expected_infolist in ARCHIVES:
            temp_dir = tempfile.mkdtemp()
            try:
                with self.subTest(f'{archive_name} on {temp_dir}'):
                    expected_infos = {info.filename: info for info in expected_infolist}
                    with x7zipfile.x7ZipFile(os.path.join(ARCHIVES_PATH, archive_name), pwd=password) as zipfile:
                        if error_message:
                            with self.assertRaisesRegex(x7zipfile.x7ZipExecError, error_message):
                                zipfile.extractall(temp_dir)
                            continue

                        zipfile.extractall(temp_dir)

                        for root, dirs, files in os.walk(temp_dir, followlinks=False):
                            for name in files + dirs:
                                actual_file = os.path.join(root, name)
                                actual_member = os.path.relpath(actual_file, temp_dir)

                                try:
                                    _ = zipfile.getinfo(actual_member)
                                    expected_info = expected_infos[actual_member]
                                    del expected_infos[actual_member]
                                except x7zipfile.x7ZipNoEntry:
                                    expected_info = None

                                actual_stat = os.lstat(actual_file)
                                actual_mode = actual_stat.st_mode

                                if stat.S_ISLNK(actual_mode):
                                    self.assertTrue(expected_info.is_symlink())
                                elif stat.S_ISDIR(actual_mode):
                                    if expected_info:
                                        self.assertTrue(expected_info.is_dir())
                                else:
                                    self.assertFalse(expected_info.is_dir())
                                    self.assertEqual(actual_stat.st_size, expected_info.file_size, f'file_size mismatch: {actual_file}')

                    self.assertEqual(len(expected_infos), 0)
            finally:
                shutil.rmtree(temp_dir)
