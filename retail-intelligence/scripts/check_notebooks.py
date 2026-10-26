from pathlib import Path
from html import escape
import base64
import nbformat
from nbclient import NotebookClient
import argparse
from IPython.core.interactiveshell import InteractiveShell
from IPython.utils.capture import capture_output

parser = argparse.ArgumentParser()
parser.add_argument("--in-process", action="store_true")
args = parser.parse_args()

root = Path(__file__).resolve().parents[1]
for path in sorted((root/'notebooks').glob('*.ipynb')):
    notebook = nbformat.read(path, as_version=4)
    if args.in_process:
        shell = InteractiveShell.instance()
        import io
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from IPython.display import display, Image
        def show_figures():
            for figure_id in plt.get_fignums():
                buffer = io.BytesIO()
                plt.figure(figure_id).savefig(buffer, format='png', bbox_inches='tight')
                display(Image(data=buffer.getvalue()))
            plt.close('all')
        plt.show = show_figures
        shell.reset(new_session=False)
        shell.user_ns['__name__'] = '__main__'
        shell.user_ns['display'] = display
        for count, cell in enumerate([c for c in notebook.cells if c.cell_type == 'code'], 1):
            with capture_output() as captured:
                result = shell.run_cell(cell.source)
            if result.error_before_exec or result.error_in_exec:
                raise RuntimeError(str(result.error_before_exec or result.error_in_exec))
            cell.execution_count = count
            cell.outputs = []
            if captured.stdout:
                cell.outputs.append(nbformat.v4.new_output('stream', name='stdout', text=captured.stdout))
            if captured.stderr:
                cell.outputs.append(nbformat.v4.new_output('stream', name='stderr', text=captured.stderr))
            for output in captured.outputs:
                cell.outputs.append(nbformat.v4.new_output('display_data', data=output.data, metadata=output.metadata))
        notebook.metadata['execution_note'] = 'Executed top-to-bottom with in-process IPython; kernel sockets unavailable in build environment.'
    else:
        NotebookClient(notebook, timeout=180, kernel_name='python3',
                       resources={'metadata': {'path':str(root)}}).execute()
    nbformat.validate(notebook)
    nbformat.write(notebook, path)
    parts = ['<!doctype html><meta charset="utf-8"><style>body{max-width:1050px;margin:40px auto;font:16px/1.6 system-ui}pre{white-space:pre-wrap;background:#f5f6f8;padding:20px}img{max-width:100%}table{border-collapse:collapse}td,th{padding:8px;border:1px solid #ddd}</style>']
    for cell in notebook.cells:
        parts.append('<pre>'+escape(cell.source)+'</pre>')
        for out in cell.get('outputs',[]):
            data = out.get('data',{})
            if 'image/png' in data:
                parts.append('<img src="data:image/png;base64,'+data['image/png']+'">')
            elif 'text/html' in data:
                parts.append(data['text/html'])
            elif 'text/plain' in data:
                parts.append('<pre>'+escape(data['text/plain'])+'</pre>')
            elif out.get('output_type') == 'stream':
                parts.append('<pre>'+escape(out.get('text',''))+'</pre>')
    (root/'artifacts'/path.with_suffix('.html').name).write_text('\n'.join(parts))
    print(path.name, 'executed')
