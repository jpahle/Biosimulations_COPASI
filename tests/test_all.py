""" Tests of the copasi command-line interface

:Author: Akhil Teja <akhilmteja@gmail.com>
:Date: 2020-04-16
:Copyright: 2020, Center for Reproducible Biomedical Modeling
:License: MIT
"""

try:
    from Biosimulations_utils.simulator.testing import SimulatorValidator
except ModuleNotFoundError:
    pass
import capturer

import Biosimulations_copasi
from Biosimulations_copasi import __main__

try:
    import docker
except ModuleNotFoundError:
    pass
import importlib
import libsbml  # noqa: F401
import libsedml  # noqa: F401
import os
import PyPDF2
import shutil
import tempfile
import unittest


class CliTestCase(unittest.TestCase):
    def setUp(self):
        self.dirname = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dirname)

    def test_help(self):
        with self.assertRaises(SystemExit):
            with __main__.App(argv=['--help']) as app:
                app.run()

    def test_version(self):
        with __main__.App(argv=['-v']) as app:
            with capturer.CaptureOutput(merged=False, relay=False) as captured:
                with self.assertRaises(SystemExit):
                    app.run()
                self.assertIn(Biosimulations_copasi.__version__, captured.stdout.get_text())
                self.assertEqual(captured.stderr.get_text(), '')

        with __main__.App(argv=['--version']) as app:
            with capturer.CaptureOutput(merged=False, relay=False) as captured:
                with self.assertRaises(SystemExit):
                    app.run()
                self.assertIn(Biosimulations_copasi.__version__, captured.stdout.get_text())
                self.assertEqual(captured.stderr.get_text(), '')

    def test_sim_short_arg_names(self):
        archive_filename = 'tests/fixtures/BIOMD0035-1task-cvode.omex'
        with __main__.App(argv=['-i', archive_filename, '-o', self.dirname]) as app:
            app.run()
        self.assert_outputs_created(self.dirname)

    def test_sim_long_arg_names(self):
        archive_filename = 'tests/fixtures/BIOMD0035-1task-cvode.omex'
        with __main__.App(argv=['--archive', archive_filename, '--out-dir', self.dirname]) as app:
            app.run()
        self.assert_outputs_created(self.dirname)

    @unittest.skipIf(True or os.getenv('CI', '0') in ['1', 'true'], 'Docker not setup in CI')
    def test_build_docker_image(self):
        docker_client = docker.from_env()

        # build image
        image_repo = 'crbm/biosimulations_copasi'
        image_tag = Biosimulations_copasi.__version__
        image, _ = docker_client.images.build(
            path='.',
            dockerfile='Dockerfile',
            pull=True,
            rm=True,
        )
        image.tag(image_repo, tag='latest')
        image.tag(image_repo, tag=image_tag)

    @unittest.skipIf(os.getenv('CI', '0') in ['1', 'true'], 'Docker not setup in CI')
    def test_sim_with_docker_image(self):
        docker_client = docker.from_env()

        # image config
        image_repo = 'crbm/biosimulations_copasi'
        image_tag = Biosimulations_copasi.__version__

        # setup input and output directories
        in_dir = os.path.join(self.dirname, 'in')
        out_dir = os.path.join(self.dirname, 'out')
        os.makedirs(in_dir)
        os.makedirs(out_dir)

        # create intermediate directories so that the test runner will have permissions to cleanup the results
        # generated by the docker image (running as root)
        os.makedirs(os.path.join(out_dir, 'ex1'))
        os.makedirs(os.path.join(out_dir, 'ex2'))
        os.makedirs(os.path.join(out_dir, 'ex1', 'BIOMD0035-1task-cvode'))
        os.makedirs(os.path.join(out_dir, 'ex2', 'BIOMD0035-1task-cvode'))

        # copy model and simulation to temporary directory which will be mounted into container
        shutil.copyfile('tests/fixtures/BIOMD0035-1task-cvode.omex',
                        os.path.join(in_dir, 'BIOMD0035-1task-cvode.omex'))

        # run image
        docker_client.containers.run(
            image_repo + ':' + image_tag,
            volumes={
                in_dir: {
                    'bind': '/root/in',
                    'mode': 'ro',
                },
                out_dir: {
                    'bind': '/root/out',
                    'mode': 'rw',
                }
            },
            command=['-i', '/root/in/BIOMD0035-1task-cvode.omex', '-o', '/root/out'],
            tty=True,
            remove=True)

        self.assert_outputs_created(out_dir)

    def assert_outputs_created(self, dirname):
        self.assertEqual(set(os.listdir(dirname)), {'ex1', 'ex2'})
        self.assertEqual(set(os.listdir(os.path.join(dirname, 'ex1'))), {'BIOMD0035-1task-cvode'})
        self.assertEqual(set(os.listdir(os.path.join(dirname, 'ex2'))), {'BIOMD0035-1task-cvode'})
        self.assertEqual(set(os.listdir(os.path.join(dirname, 'ex1', 'BIOMD0035-1task-cvode'))),
                         {'plot_1_task1.pdf', 'plot_3_task1.pdf'})
        self.assertEqual(set(os.listdir(os.path.join(dirname, 'ex2', 'BIOMD0035-1task-cvode'))),
                         {'plot_1_task1.pdf', 'plot_3_task1.pdf'})

        files = [
            os.path.join(dirname, 'ex1', 'BIOMD0035-1task-cvode', 'plot_1_task1.pdf'),
            os.path.join(dirname, 'ex1', 'BIOMD0035-1task-cvode', 'plot_3_task1.pdf'),
            os.path.join(dirname, 'ex2', 'BIOMD0035-1task-cvode', 'plot_1_task1.pdf'),
            os.path.join(dirname, 'ex2', 'BIOMD0035-1task-cvode', 'plot_3_task1.pdf'),
        ]
        for file in files:
            with open(file, 'rb') as f:
                PyPDF2.PdfFileReader(f)

    @unittest.skipIf(os.getenv('CI', '0') in ['1', 'true'], 'Docker not setup in CI')
    def test_validator(self):
        importlib.reload(libsbml)
        importlib.reload(libsedml)

        validator = SimulatorValidator()
        valid_cases, case_exceptions = validator.run('crbm/biosimulations_copasi', 'properties.json')
        self.assertGreater(len(valid_cases), 0)
        self.assertEqual(case_exceptions, [])
