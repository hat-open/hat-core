from pathlib import Path


root_path = Path(__file__).parent.parent.resolve()

extensions = ['sphinx.ext.graphviz',
              'sphinx.ext.todo',
              'sphinx.ext.imgmath',
              'sphinxcontrib.plantuml',
              'sphinxcontrib.programoutput',
              'hat.sphinx.include_dir',
              'hat.sphinx.exec',
              'hat.sphinx.scxml']

with open(root_path / 'VERSION', encoding='utf-8') as f:
    version = f.read().strip()
project = 'Hat Core'
copyright = '2020 - 2021, Hat Open AUTHORS'
master_doc = 'index'

html_theme = 'furo'
html_static_path = ['static']
html_css_files = ['custom.css']
html_use_index = False
html_show_sourcelink = False
html_show_sphinx = False
html_sidebars = {'**': ["sidebar/brand.html",
                        "sidebar/scroll-start.html",
                        "sidebar/navigation.html",
                        "sidebar/scroll-end.html"]}

todo_include_todos = True

plantuml = f"java -jar {root_path / 'cache/tools/plantuml.jar'}"
