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

import re
import datetime
import errno
import os
import subprocess
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Dict, Iterator, List, Tuple, Union

WIN32 = sys.platform == "win32"


class Error(Exception):
    """Base class for x7zipfile errors."""


class No7ZipEntry(Error):
    """File not found in archive"""


class x7ZipExecError(Error):
    """Problem reported by 7-zip."""


class x7ZipCannotExec(x7ZipExecError):
    """Executable not found."""


@dataclass
class x7ZipInfo:
    filename: Union[str, None]
    file_size: Union[int, None] = None
    compress_size: Union[int, None] = None
    date_time: Union[Tuple[int, int, int, int, int, int], None] = None
    CRC: Union[int, None] = None
    mode: Union[str, None] = None
    encrypted: Union[str, None] = None
    compress_type: Union[str, None] = None
    block: Union[int, None] = None

    def is_dir(self) -> bool:
        if self.mode is None:
            return False

        return self.mode.startswith('D')

    def is_file(self) -> bool:
        if self.mode is None:
            return False

        return self.mode.startswith('A')

    def needs_password(self) -> bool:
        return self.encrypted == '+'


class ExecutorABC(ABC):
    @property
    @abstractmethod
    def executable(self) -> str:
        pass

    def list_command(self, file: str) -> List[str]:
        return [self.executable, 'l', '-slt', '-sccUTF-8', file]

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
        creationflags = 0x08000000 if WIN32 else 0  # CREATE_NO_WINDOW
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
                exit_code = p.poll()
                error_message = p.stderr.read().decode('utf-8').strip()

                for stream in [p.stdin, p.stdout, p.stderr]:
                    try:
                        stream.close()
                    except:
                        pass

                if exit_code == 0:
                    break

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

    def execute_list(self, archive_name: str, password: Union[str, None] = None) -> List[x7ZipInfo]:
        parsers: Tuple[str, int, Callable[[str], str]] = [
            (
                parse_parameter[0],
                parse_parameter[1],
                parse_parameter[2],
                len(parse_parameter[0])
            )
            for parse_parameter in [
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
            for prefix, property_name, parse_property, prefix_length in parsers:
                if not line.startswith(prefix):
                    continue

                try:
                    value = parse_property(line[prefix_length:])
                except:
                    raise Error(f'parse error: {line}')

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

        for line in self.execute(command):
            print(line)


class Command7zaExecutor(ExecutorABC):
    @property
    def executable(self) -> str:
        return '7za'


class Command7zrExecutor(Command7zaExecutor):
    @property
    def executable(self) -> str:
        return '7zr'


class Command7zExecutor(Command7zaExecutor):
    @property
    def executable(self) -> str:
        return '7z'


EXECUTOR: ExecutorABC = None


def get_executor() -> ExecutorABC:
    global EXECUTOR

    if EXECUTOR is not None:
        return EXECUTOR

    for executor_class in [Command7zExecutor, Command7zaExecutor, Command7zrExecutor]:
        executor = executor_class()
        if executor.is_available():
            EXECUTOR = executor
            return EXECUTOR

    raise x7ZipCannotExec(
        'Cannot find working 7-zip command. '
        'Please install 7-zip and setup the PATH properly.'
    )


class x7ZipFile:
    def __init__(
        self,
        file: Union[str, bytes, os.PathLike],
        mode='r',
        pwd: Union[str, None] = None,
        charset=None,
    ):
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

    def __enter__(self):
        """Open context."""
        return self

    def __exit__(self, typ, value, traceback):
        """Exit context."""
        self.close()

    def open(self):
        pass

    def close(self):
        pass

    def infolist(self) -> List[x7ZipInfo]:
        return self._info_list

    def getinfo(self, member: str) -> x7ZipInfo:
        try:
            return self._info_map[member]
        except KeyError:
            raise No7ZipEntry(f'No such file: {member}') from None

    def namelist(self) -> List[str]:
        return [info.filename for info in self.infolist()]

    def extract(self, member: str,  path: Union[str, None] = None, pwd: Union[str, None] = None):
        """Extract single file into current directory.

        Parameters:

            member
                filename or :class:`RarInfo` instance
            path
                optional destination path
            pwd
                optional password to use
        """
        self._executor.execute_extract(
            archive_name=self._file,
            output_directory=path,
            file_names=[member],
            password=pwd or self._pwd,
            other_options=['-y']
        )

    def extractall(self, path: Union[str, None] = None, members: Union[List[str], None] = None, pwd: Union[str, None] = None):
        """Extract all files into current directory.

        Parameters:

            path
                optional destination path
            members
                optional filename or :class:`RarInfo` instance list to extract
            pwd
                optional password to use
        """
        self._executor.execute_extract(
            archive_name=self._file,
            output_directory=path,
            file_names=members,
            password=pwd or self._pwd,
            other_options=['-y']
        )
