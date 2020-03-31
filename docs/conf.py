

extensions = ['sphinx.ext.imgmath',
              'sphinx.ext.graphviz',
              'sphinx.ext.todo',
              'sphinx.ext.autodoc',
              'sphinx.ext.autosummary',
              'sphinx.ext.napoleon',
              'sphinx.ext.imgmath',
              'hat.sphinx.patch']

with open('../VERSION', encoding='utf-8') as f:
    version = f.read().strip()
project = 'Hat Core Documentation'
copyright = '2020, Hat Open AUTHORS'
master_doc = 'index'

html_theme = 'nature'
html_static_path = ['static']
html_css_files = ['custom.css']
html_use_index = False
html_show_sourcelink = False
html_show_sphinx = False
html_sidebars = {'**': ['globaltoc.html', 'relations.html']}

latex_documents = [
    ('index', 'hat_developer.tex', project,
     "Hat Open AUTHORS",
     'manual', True)]
latex_engine = 'xelatex'
latex_elements = {'papersize': 'a4paper'}

imgmath_image_format = 'svg'

pngmath_latex_preamble = '\n'.join([
    r'\usepackage{amsmath}',
    r'\usepackage{wasysym}',
    r'\usepackage{dsfont}',
    r'\usepackage[utf8]{inputenc}'])

todo_include_todos = True

autoclass_content = 'both'

autodoc_default_options = {'members': True,
                           'member-order': 'bysource',
                           'undoc-members': True,
                           'show-inheritance': True}

plot_include_source = False
plot_html_show_source_link = False
plot_html_show_formats = False
plot_formats = ['png']
