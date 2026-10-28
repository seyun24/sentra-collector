import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('installer_config', Path(__file__).resolve().parents[1] / 'validate_config.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='sentra-install-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.env = self.root / 'collector.env'
        self.output = self.root / 'compose.json'
        self.base = ('SENTRA_INGEST_BASE_URL=https://ingest.test.invalid\n'
                     'SENTRA_WORKSPACE_ID=ws-test\nSENTRA_COLLECTOR_ID=c-test\n'
                     'SENTRA_COLLECTOR_TOKEN=secret$not-executed\n'
                     'SENTRA_HOST_ID=host-test\nSENTRA_SERVICE_NAME=test\n')

    def generate(self, extra=''):
        self.env.write_text(self.base + extra)
        module.generate(self.env, self.output)
        return json.loads(self.output.read_text())['services']['collector']

    def test_paths_spaces_dollars_deduplicated_and_no_secret_in_output(self):
        folder = self.root / 'app $logs'
        folder.mkdir()
        service = self.generate(f'SENTRA_COLLECTOR_LOG_SOURCES={folder}/app.log:checkout:application\n'
                                f'SENTRA_COLLECTOR_TRACE_JSONL_PATH={folder}/trace.jsonl\n'
                                f'SENTRA_COLLECTOR_DB_SQLITE_PATH={folder}/db.sqlite\n')
        binds = [v for v in service['volumes'] if v['type']=='bind']
        self.assertEqual(len(binds), 1)
        self.assertEqual(binds[0]['source'], str(folder).replace('$','$$'))
        self.assertTrue(binds[0]['read_only'])
        self.assertFalse(binds[0]['bind']['create_host_path'])
        self.assertEqual(service['environment']['SENTRA_COLLECTOR_LOG_SOURCES'], '/inputs/0/app.log:checkout:application')
        self.assertNotIn('secret', self.output.read_text())
        self.assertEqual(self.output.stat().st_mode & 0o777, 0o600)

    def test_no_inputs_no_bind_and_optional_isolation(self):
        service = self.generate('SENTRA_INSTALL_HOST_METRICS=false\n')
        self.assertFalse(any(v['type']=='bind' for v in service['volumes']))
        self.assertNotIn('pid', service)
        self.assertNotIn('network_mode', service)

    def test_root_relative_and_nonexistent_parent_rejected(self):
        for path in ('/app.log','relative/app.log',str(self.root/'missing'/'app.log'),'/proc/stat'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.generate('SENTRA_COLLECTOR_LOG_SOURCES='+path+'\n')

    def test_symlink_resolves_and_same_directory_is_not_mounted_twice(self):
        directory=self.root/'logs';directory.mkdir()
        file=directory/'app.log';file.touch()
        alias=self.root/'alias.log';alias.symlink_to(file)
        service=self.generate(f'SENTRA_COLLECTOR_LOG_SOURCES={alias},{file}\n')
        self.assertEqual(len([v for v in service['volumes'] if v['type']=='bind']),1)

if __name__ == '__main__':
    unittest.main()
