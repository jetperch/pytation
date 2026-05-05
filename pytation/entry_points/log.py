# Copyright 2026 Jetperch LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from pytation import log_analysis
import glob
import os
import webbrowser


NAME = 'log'


def parser_config(p):
    """Generate an HTML timing report from a pytation log."""
    p.add_argument('--output', '-o',
                   help='HTML output path (default: <input>.report.html '
                        'next to the input).')
    p.add_argument('--no-open', action='store_true',
                   help='Do not auto-open the report in the default browser.')
    p.add_argument('path',
                   help='Path to a station .log file, a run .zip file, or a '
                        'station name (latest log is used).')
    return on_cmd


def _resolve_path(arg):
    """Return the path to analyze, or None after printing diagnostics."""
    if os.path.isfile(arg):
        return arg

    candidates = []
    if os.path.isdir(arg):
        candidates = (glob.glob(os.path.join(arg, '*.log'))
                      + glob.glob(os.path.join(arg, 'log', '*.log'))
                      + glob.glob(os.path.join(arg, '*.zip'))
                      + glob.glob(os.path.join(arg, 'data', '*.zip')))
    else:
        root = os.path.join(os.path.expanduser('~'), 'pytation', arg)
        if os.path.isdir(root):
            candidates = (glob.glob(os.path.join(root, 'log', '*.log'))
                          + glob.glob(os.path.join(root, 'data', '*.zip')))
        if not candidates:
            pat = os.path.join(os.path.expanduser('~'), 'pytation', '**',
                               arg + '*')
            candidates = [c for c in glob.glob(pat, recursive=True)
                          if os.path.isfile(c)
                          and c.lower().endswith(('.log', '.zip'))]

    candidates = [c for c in candidates if os.path.isfile(c)]
    if not candidates:
        print(f'No log or zip files found for: {arg}')
        return None
    # Prefer .log files; fall back to .zip.
    logs = [c for c in candidates if c.lower().endswith('.log')]
    pool = logs if logs else candidates
    return max(pool, key=os.path.getmtime)


def on_cmd(args):
    resolved = _resolve_path(args.path)
    if resolved is None:
        return 1
    print(f'Analyzing {resolved}')
    display_name, runs = log_analysis.load_input(resolved)
    if not runs:
        print(f'No test runs found in {resolved}')
        return 1
    html = log_analysis.render_html(display_name, runs)
    if args.output:
        output = args.output
    else:
        base = resolved
        if base.lower().endswith('.zip'):
            base = base[:-4]
        elif base.lower().endswith('.log'):
            base = base[:-4]
        output = base + '.report.html'
    output = os.path.abspath(output)
    parent = os.path.dirname(output)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)
    with open(output, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'Wrote {output}')
    if not args.no_open:
        url = 'file:///' + output.replace(os.sep, '/').lstrip('/')
        webbrowser.open(url)
    return 0
