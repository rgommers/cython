import os
import shutil
import tempfile
from pathlib import Path

from .. import Main, Scanning
from ...TestUtils import CythonTest


class TestPxdSourcePaths(CythonTest):

    def setUp(self):
        super().setUp()
        self.temp_dir = tempfile.mkdtemp(prefix="cython-pxd-source-path-")

    def tearDown(self):
        shutil.rmtree(self.temp_dir)
        super().tearDown()

    def test_versioned_package_pxd_uses_module_relative_path(self):
        source_path = os.path.join(self.temp_dir, "module.pyx")
        include_dir = os.path.join(self.temp_dir, "build-env", "site-packages")
        numpy_dir = os.path.join(include_dir, "numpy")
        os.makedirs(numpy_dir)

        with open(source_path, "w") as source_file:
            source_file.write("cimport numpy\nvalue = numpy.get_value()\n")

        pxd_path = os.path.join(numpy_dir, "__init__.cython-30.pxd")
        with open(pxd_path, "w") as pxd_file:
            pxd_file.write("cdef inline int get_value() except -1:\n    raise RuntimeError\n")

        result = Main.compile(source_path, include_path=[include_dir])
        self.assertEqual(result.num_errors, 0)

        with open(result.c_file) as c_file:
            generated_code = c_file.read()

        filename_table = generated_code.split("/* #### Code section: filename_table ### */", 1)[1]
        filename_table = filename_table.split("};", 1)[0]
        self.assertIn('"numpy/__init__.cython-30.pxd",', filename_table)
        self.assertNotIn("build-env", filename_table)


class TestIncludeSourcePaths(CythonTest):

    def test_absolute_include_keeps_physical_path(self):
        with tempfile.TemporaryDirectory(prefix="cython-include-source-path-") as temp_dir:
            path = Path(temp_dir).resolve() / "external.pxi"
            path.touch()
            source = Scanning.FileSourceDescriptor(str(path.parent / "module.pyx"), "pkg/module.pyx")
            context = Main.Context([], {})
            included_source = context.find_include_file_source(str(path), (source, 1, 0))
            self.assertEqual(included_source.filename, str(path))
            self.assertEqual(included_source.path_description, str(path))
