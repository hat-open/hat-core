from pathlib import Path


root_path = Path(__file__).parent.parent.resolve()

extensions = ['sphinx.ext.graphviz',
              'sphinx.ext.todo',
              'sphinx.ext.imgmath',
              'sphinxcontrib.plantuml',
              'sphinxcontrib.programoutput',
              'hat.sphinx.include_dir',
              'hat.sphinx.exec']

with open(root_path / 'VERSION', encoding='utf-8') as f:
    version = f.read().strip()
project = 'Hat Core Documentation'
copyright = '2020, Hat Open AUTHORS'
master_doc = 'index'

html_theme = 'alabaster'
html_static_path = ['static']
html_css_files = ['custom.css']
html_use_index = False
html_show_sourcelink = False
html_show_sphinx = False
html_sidebars = {'**': ['globaltoc.html', 'relations.html']}

todo_include_todos = True

plantuml = f"java -jar {root_path / 'cache/tools/plantuml.jar'}"
