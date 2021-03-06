# -*- coding: utf-8 -*-
"""
    util
    ~~~~

    Utility functions.

    :copyright: Copyright (C) 2015 by the respective authors; see AUTHORS.
    :license: GPLv3, see LICENSE for details.
"""

from yaml import safe_dump
import json
import string
from os import path
from io import BytesIO
from datetime import timedelta, datetime
from dateutil.tz import tzutc

from flask import Response, render_template, current_app, request, url_for

from pygments import highlight as _highlight, format as _format
from pygments.token import Token
from pygments.lexers import get_lexer_by_name
from pygments.formatters import HtmlFormatter, get_formatter_by_name
from pygments.util import ClassNotFound

from werkzeug import http

from docutils import core
from markdown import markdown as _markdown

b66c = string.ascii_uppercase + string.ascii_lowercase + string.digits + '-_~.'

def redirect(location, rv, code=302, **kwargs):
    response = current_app.response_class(rv, code, **kwargs)
    response.headers['Location'] = location
    return response

def json_datetime(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()

def dict_response(data, url=None):
    accept = http.parse_list_header(request.headers.get('Accept',''))

    mime = 'text/plain'
    if accept and 'application/json' in accept:
        body = json.dumps(data, default=json_datetime)
        mime = 'application/json'
    else:
        body = safe_dump(data, default_flow_style=False)

    if url and request.args.get('r'):
        return redirect(url, body, mimetype=mime)
    return current_app.response_class(body, mimetype=mime)

def any_url(paste, **kwargs):
    idu = lambda k,v: id_url(**{k: (paste[v], kwargs.get('filename'))})
    if paste.get('private'):
        return idu('sha1', 'digest')
    if paste.get('label'):
        return idu('label', 'label')
    return idu('sid', 'digest')

def complex_response(paste, **kwargs):
    gs = lambda l: current_app.url_map.converters['sid'].to_url(None, paste['digest'], l)

    d = {k:v for k,v in {
        'url': any_url(paste, **kwargs),
        'long': gs(42),
        'short': gs(6),
        'sha1': paste['digest'],
        'uuid': kwargs.get('uuid'),
        'status': kwargs.get('status'),
        'label': paste.get('label')
    }.items() if v}

    if paste.get('private'):
        del d['short']
    if paste.get('sunset'):
        d['sunset'] = paste['date'].replace(tzinfo=tzutc()) + timedelta(seconds=paste['sunset'])

    return dict_response(d, d['url'])

def style_args():
    return {k:request.args.get(k) for k in ['style','css']}

def highlight(content, lexer_name, formatter):
    try:
        lexer = get_lexer_by_name(lexer_name)
    except ClassNotFound:
        if lexer_name != '':
            return "No such lexer.", 400

    if formatter:
        formatter = get_formatter_by_name(formatter)
    else:
        formatter = HtmlFormatter(linenos='table', anchorlinenos=True, lineanchors='L', linespans='L')

    if lexer_name == '':
        tokens = ((Token.Text, '{}\n'.format(c.decode('utf-8'))) for c in content.splitlines())
        content = _format(tokens, formatter)
    else:
        content = _highlight(content, lexer, formatter)

    if not isinstance(formatter, HtmlFormatter):
        return content

    template = render_template("generic.html", cc='container-fluid', content=content, **style_args())

    return Response(template, mimetype='text/html')

def request_content():
    content_type = http.parse_options_header(request.headers.get('Content-Type', ''))
    if content_type:
        content_type, _ = content_type

    if content_type == 'application/json':
        content = request.json.get('c')
        if content:
            content = BytesIO(content.encode('utf-8'))
        return content, request.json.get('filename')

    c = request.form.get('c')
    if c:
        return BytesIO(c.encode('utf-8')), None
    fs = request.files.get('c')
    if fs:
        return fs.stream, fs.filename

    return None, None

def absolute_url(endpoint, **kwargs):
    proto = request.environ.get('HTTP_X_FORWARDED_PROTO')
    scheme = proto if proto else request.scheme
    return url_for(endpoint, _external=True, _scheme=scheme, **kwargs)

def id_url(**kwargs):
    return absolute_url('.get', **kwargs)

def rst(source):
    overrides = {'syntax_highlight': 'short'}
    parts = core.publish_parts(source, writer_name='html', settings_overrides=overrides)
    return parts['html_body']

def markdown(source):
    md = _markdown(source.decode('utf-8'), extensions=[
        'markdown.extensions.extra',
        'markdown.extensions.admonition',
        'markdown.extensions.codehilite',
        'markdown.extensions.meta',
        'markdown.extensions.toc',
        'markdown.extensions.wikilinks'
    ], extension_configs = {
        'markdown.extensions.codehilite': {
            'css_class': 'code'
        }
    })
    return md
