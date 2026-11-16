"""Compatibility and integrity regressions for the author's HW8–10 contracts."""
import json
import shutil
import tempfile
import time
import unittest
import urllib.request
from pathlib import Path
from test_local import server, get
from app.release_contracts import canonical, digest, verify_files

class ContinuityTests(unittest.TestCase):
    def test_previous_generate_contract(self):
        with server() as url:
            time.sleep(.35)
            req=urllib.request.Request(url+'/generate',data=json.dumps(dict(prompt='compatibility',max_new_tokens=3)).encode(),headers={'Content-Type':'application/json','X-Request-ID':'hw8910-compatible'})
            with urllib.request.urlopen(req) as response:
                data=json.load(response)
            self.assertEqual(data['output_chunks'],3)
            self.assertTrue(data['complete'])
            self.assertEqual(data['request_id'],'hw8910-compatible')
            self.assertEqual(data['backend_mode'],'simulated')

    def test_original_contract_rejects_modified_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copytree('artifacts',tmp,dirs_exist_ok=True)
            manifest=json.loads(Path(tmp,'A.manifest.json').read_text())
            verify_files(manifest,tmp)
            Path(tmp,'A.json').write_text('{"changed":true}')
            with self.assertRaisesRegex(ValueError,'Artifact changed'):
                verify_files(manifest,tmp)
            with server(ARTIFACT_DIR=tmp) as url:
                time.sleep(.3)
                self.assertEqual(get(url+'/ready')[0],503)

    def test_modified_runtime_blocks_readiness(self):
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copytree('artifacts',tmp,dirs_exist_ok=True)
            path=Path(tmp,'A.manifest.json')
            manifest=json.loads(path.read_text())
            manifest['runtime']['backend_mode']='tampered'
            path.write_text(json.dumps(manifest))
            with server(ARTIFACT_DIR=tmp) as url:
                time.sleep(.3)
                self.assertEqual(get(url+'/ready')[0],503)
