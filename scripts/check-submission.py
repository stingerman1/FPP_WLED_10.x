#!/usr/bin/env python3
"""Run FPP's unmodified linter against tracked source, reporting all findings.

Requires jsonschema and a checkout of FalconChristmas/fpp-data. No issue, PR or
comment is created. Exit 1 means FPP reports blockers or best-practice findings.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('checker', type=Path, help='fpp-data checkout directory')
    args = parser.parse_args()
    import jsonschema  # Fail rather than silently skipping the official schema check.
    checker = args.checker.resolve()
    scripts = checker / '.github/scripts'
    sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location('lint_plugin', scripts / 'lint_plugin.py')
    linter = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = linter
    spec.loader.exec_module(linter)
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix='fpp-submission-') as directory:
        archive = Path(directory) / 'source.tar'
        source = Path(directory) / 'source'; source.mkdir()
        subprocess.run(['git', 'archive', '--format=tar', '-o', str(archive), 'HEAD'], cwd=root, check=True)
        with tarfile.open(archive) as files:
            files.extractall(source, filter='data')
        info = json.loads((source / 'pluginInfo.json').read_text())
        schema = json.loads((checker / '.github/schema/pluginInfo.schema.json').read_text())
        jsonschema.Draft7Validator.check_schema(schema)
        findings = linter.lint_plugin_dir(str(source), info['repoName'], info, schema)
    linter.print_report(findings)
    report = {
        'plugin_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
        'checker_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=checker, text=True).strip(),
        'findings': [vars(finding) for finding in findings],
    }
    output = root / 'build/submission-report.json'; output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n')
    return int(any(f.severity in ('blocker', 'best-practice') for f in findings))


if __name__ == '__main__':
    raise SystemExit(main())
