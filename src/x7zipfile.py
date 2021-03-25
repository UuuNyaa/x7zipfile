# -*- coding: utf-8 -*-
# Copyright 2021 UuuNyaa <UuuNyaa@gmail.com>
# All rights reserved.
#
# BSD 3-Clause License
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import datetime
import errno
import os
import re
import subprocess
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Dict, Iterator, List, Tuple, Union

_WIN32 = sys.platform == "win32"
_EXECUTABLES = ['7z', '7za', '7zr'] + (['7z.exe', '7za.exe', '7zr.exe'] if _WIN32 else [])


class x7ZipError(Exception):
    """Base class for x7zipfile errors."""


class x7ZipNoEntry(x7ZipError):
    """File not found in archive"""


class x7ZipExecError(x7ZipError):
    """Problem reported by 7-zip."""


class x7ZipCannotExec(x7ZipExecError):
    """Executable not found."""


@dataclass
class x7ZipInfo:
    """An entry in 7-zip archive.

    Attributes:

        filename
            File name with relative path.
            Path separator is "/".  Always unicode string.

        date_time
            File modification timestamp. As tuple of (year, month, day, hour, minute, second).
            7-zip allows archives where it is missing, it's None then.

        file_size
            Uncompressed size.

        compress_size
            Compressed size.

        compress_type
            Compression method: eg. LZMA, LZMA2, PPMD, ...

        encrypted
            Encryption state: '+' = encrypted, '-' = not encrypted.

        mode
            File attributes. May be either dos-style or unix-style, depending on host_os.

        CRC
            CRC-32 of uncompressed file, unsigned int.

            RAR5: may be None.

    """
    filename: Union[str, None]
    date_time: Union[Tuple[int, int, int, int, int, int], None] = None
    file_size: Union[int, None] = None
    compress_size: Union[int, None] = None
    compress_type: Union[str, None] = None
    encrypted: Union[str, None] = None
    mode: Union[str, None] = None
    CRC: Union[int, None] = None
    block: Union[int, None] = None

    def is_dir(self) -> bool:
        """Returns True if entry is a directory.
        """
        if self.mode is None:
            return False

        return 'D' in self.mode

    def is_symlink(self) -> bool:
        """Returns True if entry is a symlink.
        """
        if self.mode is None:
            return False

        return ' l' in self.mode

    def is_file(self) -> bool:
        """Returns True if entry is a normal file.
        """
        if self.mode is None:
            return False

        return 'A' in self.mode

    def is_readonly(self) -> bool:
        """Returns True if entry is a readonly file.
        """
        if self.mode is None:
            return False

        return 'R' in self.mode

    def needs_password(self) -> bool:
        """Returns True if entry is stored password-protected.
        """
        return self.encrypted == '+'


class _Executor:
    def __init__(self, executable: str):
        self.executable = executable

    def is_available(self) -> bool:
        try:
            p = self._popen(self.executable)
            _, _ = p.communicate(timeout=1)
            p.wait()
            return p.returncode == 0
        except:
            return False

    def _popen(self, command: Union[str, List[str]]) -> subprocess.Popen:
        """Disconnect command from parent fds, read only from stdout.
        """
        creationflags = 0x08000000 if _WIN32 else 0  # CREATE_NO_WINDOW
        try:
            return subprocess.Popen(
                command,
                bufsize=0,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                creationflags=creationflags,
            )
        except OSError as e:
            if e.errno == errno.ENOENT:
                raise x7ZipCannotExec('7-zip not installed?') from None
            if e.errno == errno.EACCES or e.errno == errno.EPERM:
                raise x7ZipCannotExec('Cannot execute 7-zip') from None
            raise

    def execute(self, command: Union[str, List[str]]) -> Iterator[str]:
        linesep = os.linesep
        p = self._popen(command)
        while True:
            line = p.stdout.readline()
            if line is not None:
                yield line.decode('utf-8').rstrip(linesep)

            if not line and p.poll() is not None:
                break

        exit_code = p.poll()
        error_message = p.stderr.read().decode('utf-8').strip()

        for stream in [p.stdin, p.stdout, p.stderr]:
            try:
                stream.close()
            except:
                pass

        if exit_code == 0:
            return

        if exit_code == 1:
            raise x7ZipExecError(f'Warning: {error_message}')
        elif exit_code == 2:
            raise x7ZipExecError(f'Fatal error: {error_message}')
        elif exit_code == 7:
            raise x7ZipExecError(f'Command line error: {error_message}')
        elif exit_code == 8:
            raise x7ZipExecError(f'Not enough memory for operation: {error_message}')
        elif exit_code == 255:
            raise x7ZipExecError(f'User stopped the process: {error_message}')
        else:
            raise x7ZipExecError(error_message)

    _parsers: Tuple[str, int, Callable[[str], str]] = [
        (
            param[0],
            param[1],
            param[2],
            len(param[0]),
        )
        for param in [
            ('Path = ', 'filename', lambda p: p),
            ('Size = ', 'file_size', lambda p: int(p) if p else None),
            ('Packed Size = ', 'compress_size', lambda p: int(p) if p else None),
            ('Modified = ', 'date_time', lambda p: tuple([int(v) for v in re.split(r'[ \-:]', p)]) if p else None),
            ('Attributes = ', 'mode', lambda p: p),
            ('CRC = ', 'CRC', lambda p: int(p, 16) if p else None),
            ('Encrypted = ', 'encrypted', lambda p: p),
            ('Method = ', 'compress_type', lambda p: p if p else None),
            ('Block = ', 'block', lambda p: int(p) if p else None),
        ]
    ]

    def execute_list(self, archive_name: str, password: Union[str, None] = None) -> List[x7ZipInfo]:
        info_list: List[x7ZipInfo] = []
        info = None
        for line in self.execute([
            self.executable,
            'l',
            '-slt',
            '-sccUTF-8',
            f"-p{password or ''}",
            archive_name,
        ]):
            for prefix, property_name, parse_property, prefix_length in self._parsers:
                if not line.startswith(prefix):
                    continue

                try:
                    value = parse_property(line[prefix_length:])
                except:
                    raise x7ZipError(f'parse error: {line}')

                if prefix == 'Path = ':
                    if info is not None:
                        info_list.append(info)

                    info = x7ZipInfo(filename=None if info is None else value)

                if info is None:
                    break

                if info.filename is None:
                    break

                setattr(info, property_name, value)

        if info is not None:
            info_list.append(info)

        return info_list[1:]

    def execute_extract(
        self,
        archive_name: str,
        output_directory: Union[str, None] = None,
        file_names: Union[List[str], None] = None,
        password: Union[str, None] = None,
        other_options: Union[List[str], None] = None,
    ):
        command = [self.executable, 'x', '-sccUTF-8', archive_name]

        if output_directory is not None:
            command.append(f'-o{output_directory}')

        command.append(f"-p{password or ''}")

        if file_names is not None:
            command.extend(file_names)

        if other_options is not None:
            command.extend(other_options)

        for _ in self.execute(command):
            pass


_EXECUTOR: _Executor = None


def get_executor() -> _Executor:
    global _EXECUTOR

    if _EXECUTOR is not None:
        return _EXECUTOR

    for executable in _EXECUTABLES:
        executor = _Executor(executable)
        if executor.is_available():
            _EXECUTOR = executor
            return _EXECUTOR

    raise x7ZipCannotExec(
        'Cannot find working 7-zip command. '
        'Please install 7-zip and setup the PATH properly.'
    )


class x7ZipFile:
    """Class with methods to open, close, list 7-zip files.
    """

    def __init__(
        self,
        file: Union[str, bytes, os.PathLike],
        mode='r',
        pwd: Union[str, None] = None,
        charset=None,
    ):
        """Open the 7-zip file with mode read 'r'.
        """
        self._file = file if not isinstance(file, os.PathLike) else str(file)
        self._charset = charset

        if mode != 'r':
            raise NotImplementedError('x7ZipFile supports only mode=r')

        self._pwd = pwd

        self._executor = get_executor()

        self._info_list = self._executor.execute_list(self._file, password=pwd)
        self._info_map = {
            info.filename: info
            for info in self._info_list
        }

    def __enter__(self) -> x7ZipInfo:
        """Open context."""
        return self

    def __exit__(self, typ, value, traceback):
        """Exit context."""
        self.close()

    def open(self):
        """Returns file-like object (:class:`x7ZipExtFile`) from where the data can be read.

        The object implements :class:`io.RawIOBase` interface, so it can
        be further wrapped with :class:`io.BufferedReader`
        and :class:`io.TextIOWrapper`.

        On older Python where io module is not available, it implements
        only .read(), .seek(), .tell() and .close() methods.

        The object is seekable, although the seeking is fast only on
        uncompressed files, on compressed files the seeking is implemented
        by reading ahead and/or restarting the decompression.

        Parameters:

            name
                file name or RarInfo instance.
            mode
                must be 'r'
            pwd
                password to use for extracting.
        """
        raise NotImplementedError('x7ZipFile does not yet support open')

    def close(self):
        """Release open resources."""
        pass

    def infolist(self) -> List[x7ZipInfo]:
        """Return x7ZipInfo objects for all files/directories in archive.
        """
        return self._info_list

    def getinfo(self, member: str) -> x7ZipInfo:
        """Return x7ZipInfo for file.
        """
        try:
            return self._info_map[member]
        except KeyError:
            raise x7ZipNoEntry(f'No such file: {member}') from None

    def namelist(self) -> List[str]:
        """Return list of filenames in archive.
        """
        return [info.filename for info in self.infolist()]

    @staticmethod
    def to_filename(member: Union[str, x7ZipInfo]) -> str:
        return member.filename if isinstance(member, x7ZipInfo) else member

    def extract(self, member: Union[str, x7ZipInfo], path: Union[str, None] = None, pwd: Union[str, None] = None):
        """Extract single file into current directory.

        Parameters:

            member
                filename or :class:`x7ZipInfo` instance
            path
                optional destination path
            pwd
                optional password to use
        """
        self._executor.execute_extract(
            archive_name=self._file,
            output_directory=path,
            file_names=[x7ZipFile.to_filename(member)],
            password=pwd or self._pwd,
            other_options=['-y']
        )

    def extractall(self, path: Union[str, None] = None, members: Union[List[Union[str, x7ZipInfo]], None] = None, pwd: Union[str, None] = None):
        """Extract all files into current directory.

        Parameters:

            path
                optional destination path
            members
                optional filename or :class:`x7ZipInfo` instance list to extract
            pwd
                optional password to use
        """
        self._executor.execute_extract(
            archive_name=self._file,
            output_directory=path,
            file_names=[x7ZipFile.to_filename(member) for member in members] if members else None,
            password=pwd or self._pwd,
            other_options=['-y']
        )
