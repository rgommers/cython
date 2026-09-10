import os
import shutil
import tempfile
from pathlib import Path

from .. import Main, Scanning
from ...TestUtils import CythonTest
from ... import Utils


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

    def test_output_independent_of_build_and_include_directories(self):
        sources = {
            "pkg/__init__.py": "",
            "pkg/module.pyx": (
                'include "local.pxi"\n'
                'include "vendor/external.pxi"\n'
                'cimport dep\n'
                'def from_pxd():\n    return dep.from_include()\n'
            ),
            "pkg/local.pxi": (
                'include "nested/inner.pxi"\n'
                'def local():\n    raise ValueError("local")\n'
            ),
            "pkg/nested/inner.pxi": (
                'include "../sibling.pxi"\n'
                'def inner():\n    raise ValueError("inner")\n'
            ),
            "pkg/sibling.pxi": 'def sibling():\n    raise ValueError("sibling")\n',
        }
        includes = {
            "vendor/external.pxi": (
                'include "nested.pxi"\n'
                'def external():\n    raise ValueError("external")\n'
            ),
            "vendor/nested.pxi": 'def nested():\n    raise ValueError("nested")\n',
            "dep/__init__.pxd": 'include "inline.pxi"\n',
            "dep/inline.pxi": 'cdef inline int from_include() except -1:\n    raise ValueError\n',
            # The source directory must take precedence over -I directories.
            "local.pxi": 'invalid Cython syntax!\n',
        }
        expected_paths = (
            "pkg/module.pyx", "pkg/local.pxi", "pkg/nested/inner.pxi",
            "pkg/sibling.pxi", "vendor/external.pxi", "vendor/nested.pxi",
            "dep/inline.pxi",
        )
        original_cwd = os.getcwd()
        generated_sources = []
        with tempfile.TemporaryDirectory(prefix="cython-include-source-path-") as temp_dir:
            root = Path(temp_dir).resolve()
            for name, contents in sources.items():
                path = root / "source" / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(contents, encoding="UTF-8")
            # The first -I directory must take precedence over later ones.
            shadow = root / "shadow" / "vendor" / "external.pxi"
            shadow.parent.mkdir(parents=True)
            shadow.write_text('invalid Cython syntax!\n', encoding="UTF-8")
            try:
                for index, directory in enumerate(("", "source", "source/build", "source/build/nested/deep")):
                    with self.subTest(directory=directory):
                        build_dir = root / directory
                        build_dir.mkdir(parents=True, exist_ok=True)
                        include_dir = root / f"environment-{index}" / "includes"
                        for name, contents in includes.items():
                            path = include_dir / name
                            path.parent.mkdir(parents=True, exist_ok=True)
                            path.write_text(contents, encoding="UTF-8")
                        os.chdir(build_dir)
                        Utils.clear_function_caches()
                        include_path = [str(include_dir), str(root / "shadow")]
                        if index % 2:
                            include_path = [os.path.relpath(path) for path in include_path]
                        result = Main.compile(
                            os.path.relpath(root / "source" / "pkg" / "module.pyx"),
                            include_path=include_path,
                            output_file=str(build_dir / "module.c"),
                        )
                        self.assertEqual(result.num_errors, 0)
                        generated_code = Path(result.c_file).read_text(encoding="UTF-8")
                        filename_table = generated_code.split("/* #### Code section: filename_table ### */", 1)[1]
                        filename_table = filename_table.split("};", 1)[0]
                        for name in expected_paths:
                            self.assertIn(f'"{name}",', filename_table)
                        generated_sources.append(generated_code)
            finally:
                os.chdir(original_cwd)
                Utils.clear_function_caches()
        for generated_code in generated_sources[1:]:
            self.assertTrue(generated_code == generated_sources[0], "Generated C differs between build directories")
