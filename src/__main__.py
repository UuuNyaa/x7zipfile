# -*- coding: utf-8 -*-
# Copyright 2021 UuuNyaa <UuuNyaa@gmail.com>
# This file is part of x7zipfile.

import argparse
import sys

import x7zipfile


def main():
    parser = argparse.ArgumentParser(prog='x7zipfile')

    subparsers = parser.add_subparsers(dest='command', help='commands')

    parser_list = subparsers.add_parser('l', help='List contents of archive')
    parser_list.add_argument('archive_name', type=argparse.FileType('rb'))
    parser_list.add_argument('file_names', nargs='*', help='file name list to list')
    parser_list.add_argument('-p', '--password', help='set Password')

    parser_extract = subparsers.add_parser('x', help='eXtract files with full paths')
    parser_extract.add_argument('archive_name', type=argparse.FileType('rb'))
    parser_extract.add_argument('-o', '--output_directory', help='set Output directory')
    parser_extract.add_argument('-p', '--password', help='set Password')
    parser_extract.add_argument('file_names', nargs='*', help='file name list to extract')

    parser_test = subparsers.add_parser('t', help='test')
    parser_test.add_argument('archive_name', type=argparse.FileType('rb'))

    options = parser.parse_args()

    if options.command == 'l':
        with x7zipfile.x7ZipFile(options.archive_name.name, pwd=options.password) as zipfile:
            print('   Date      Time    Attr         Size   Compressed  Name')
            print('------------------- ----- ------------ ------------  ------------------------')

            total_compress_size = 0
            total_file_size = 0
            file_count = 0
            folder_count = 0
            nofilter = len(options.file_names) == 0
            members = set(options.file_names)

            for info in zipfile.infolist():
                total_compress_size += info.compress_size or 0

                if not nofilter and info.filename not in members:
                    continue

                date_time = info.date_time
                if date_time is None:
                    print(' '*19, end=' ')
                else:
                    print(f'{date_time[0]:04}-{date_time[1]:02}-{date_time[2]:02} {date_time[3]:02}:{date_time[4]:02}:{date_time[5]:02}', end=' ')

                mode = ['.', '.', '.', '.', '.', ]
                if info.is_dir():
                    mode[0] = 'D'
                    folder_count += 1

                if info.is_readonly():
                    mode[1] = 'R'

                if info.is_file():
                    mode[4] = 'A'
                    file_count += 1

                print(''.join(mode), end=' ')

                print(str(info.file_size).rjust(12), end=' ')
                print((str(info.compress_size) if info.compress_size is not None else '').rjust(12), end='  ')
                print(info.filename)

                total_file_size += info.file_size

            print('------------------- ----- ------------ ------------  ------------------------')
            print(' '*19, end=' ')
            print(' '*5, end=' ')
            print(str(total_file_size).rjust(12), end=' ')
            print(str(total_compress_size).rjust(12), end='  ')
            print(f'{file_count} files', end='')
            if folder_count > 0:
                print(f', {folder_count} folders', end='')
            print()

    elif options.command == 'x':
        with x7zipfile.x7ZipFile(options.archive_name.name) as zipfile:
            zipfile.extractall(
                path=options.output_directory,
                members=options.file_names if len(options.file_names) > 0 else None,
                pwd=options.password,
            )
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
