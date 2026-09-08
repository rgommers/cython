import os
import tempfile

from ...Compiler import Main
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
