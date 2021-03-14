

def task_homepage_articles():
    """Homepage - copy articles"""

    def copy_article(name):
        common.rm_rf(articles_dst_dir / name)
        common.cp_r(articles_src_dir / name, articles_dst_dir / name)

    return {'actions': [(copy_article, [name])
                        for name in get_article_names()],
            'task_dep': ['articles']}


def _get_articles():
    ns = {'xhtml': 'http://www.w3.org/1999/xhtml'}
    for name in sorted(get_article_names()):
        rst_path = articles_src_dir / f'{name}/index.html'
        root = xml.etree.ElementTree.parse(str(rst_path)).getroot()
        title_tag = root.find("./xhtml:head/xhtml:title", ns)
        author_tag = root.find("./xhtml:head/xhtml:meta[@name='author']",
                               ns)
        date_tag = root.find("./xhtml:head/xhtml:meta[@name='date']", ns)
        title = title_tag.text
        author = (author_tag.get('content')
                  if author_tag is not None else None)
        date = date_tag.get('content') if date_tag is not None else None
        yield {'link': f'articles/{name}/index.html',
               'title': title,
               'author': author,
               'date': date}
