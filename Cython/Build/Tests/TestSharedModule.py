import os
import tempfile
from unittest.mock import patch

from ...Compiler import Code, Main
from ...TestUtils import CythonTest
from ..SharedModule import generate_shared_module


class TestSharedModule(CythonTest):

    def test_output_independent_of_destination_directory(self):
        generated_sources = []

        with tempfile.TemporaryDirectory() as temp_dir:
            for directory_name in ('one', 'two'):
                output_dir = os.path.join(temp_dir, directory_name)
                os.mkdir(output_dir)
                output_file = os.path.join(output_dir, '_cyutility.c')
                options = Main.CompilationOptions(
                    Main.default_options,
                    shared_c_file_path=output_file,
                )

                error, _ = generate_shared_module(options)
                self.assertIsNone(error)
                with open(output_file, encoding='UTF-8') as generated_file:
                    generated_sources.append(generated_file.read())

        self.assertEqual(generated_sources[0], generated_sources[1])

    def test_output_independent_of_utility_directory_order(self):
        utility_files = sorted(os.listdir(Code.get_utility_dir()))
        generated_sources = []

        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = os.path.join(temp_dir, '_cyutility.c')
            for file_order in (utility_files, utility_files[::-1]):
                options = Main.CompilationOptions(
                    Main.default_options,
                    shared_c_file_path=output_file,
                )
                with patch('Cython.Build.SharedModule.os.listdir', return_value=file_order):
                    error, _ = generate_shared_module(options)
                self.assertIsNone(error)
                with open(output_file, encoding='UTF-8') as generated_file:
                    generated_sources.append(generated_file.read())

        self.assertEqual(generated_sources[0], generated_sources[1])
