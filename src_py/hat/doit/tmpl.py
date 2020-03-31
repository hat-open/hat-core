import mako.lookup
import mako.template


def mako_build(tmpl_dir, src_path, dst_path, params):
    tmpl_lookup = mako.lookup.TemplateLookup(directories=[str(tmpl_dir)],
                                             input_encoding='utf-8')
    tmpl_uri = tmpl_lookup.filename_to_uri(str(src_path))
    tmpl = tmpl_lookup.get_template(tmpl_uri)
    output = tmpl.render(**params)

    dst_path.parent.mkdir(parents=True, exist_ok=True)
    with open(dst_path, 'w', encoding='utf-8') as f:
        f.write(output)
