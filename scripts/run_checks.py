"""Run the isolated Linux engineering suite and retain its actual stdout/stderr."""

from datetime import datetime, timezone
from pathlib import Path
import uuid

from run_replay import COMMON, IMAGE, ROOT, command, docker, source_manifest, write_json


def main():
    tag = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:6]
    out = ROOT / 'results' / ('checks-' + tag)
    out.mkdir(parents=True, exist_ok=False)
    cmd = ['docker','run','--rm', *COMMON, IMAGE, 'python','-m','pytest','-q','-p','no:cacheprovider']
    result = command(cmd, check=False)
    (out/'stdout.txt').write_text(result.stdout, encoding='utf-8')
    (out/'stderr.txt').write_text(result.stderr, encoding='utf-8')
    write_json(out/'metadata.json', {'kind':'engineering_checks_not_llm', 'command':cmd,
               'exit_code':result.returncode, 'image_id':docker('image','inspect',IMAGE,'--format','{{.Id}}'),
               'source_sha256':source_manifest()})
    print(result.stdout, end='')
    if result.stderr:
        print(result.stderr)
    print('Evidence:', out)
    raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
