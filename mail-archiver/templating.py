import os
import datetime
from jinja2 import Environment
from .utils import normalize, removeDir, copyDir, humansize, simplifyEmailHeader, slugify_safe, strftime

def render_breadcrumbs(folder_id, mailfolders, link_prefix):
    """
    Renders folder breadcrumbs
    """

    # allFolders = getMailFolders()
    if not folder_id or not folder_id in mailolders:
        return ''

    folderList = []
    currentfolder_id = folder_id
    while currentfolder_id and currentfolder_id in allFolders:
        if allFolders[currentfolder_id]["selected"]:
            folderList.append((allFolders[currentfolder_id]["title"], allFolders[currentfolder_id]["link"]))
        else:
            folderList.append((allFolders[currentfolder_id]["title"], None))

        currentfolder_id = allFolders[currentfolder_id]["parent"]

    folderList = folderList[::-1]
    return render_template(
        "folder-breadcrumbs.tpl",
        None,
        folderList=folderList,
        link_prefix=link_prefix,
    )

def render_template(settings, template_name, save_to, **kwargs):
    """
    Helper function to render a templete with variables
    """
    global server

    contents = ''
    template_path = settings['templates_location'] + template_name
    with open(template_path, "r") as f:
        contents = f.read()

    env = Environment()
    env.filters["humansize"] = humansize
    env.filters["simplifyEmailHeader"] = simplifyEmailHeader
    env.filters["strftime"] = strftime
    env.filters["render_breadcrumbs"] = render_breadcrumbs

    template = env.from_string(contents)
    result = template.render(**kwargs)
    if save_to:
        with open(save_to, "w", encoding="utf-8") as f:
            if settings.get('prettify', True):
                try:
                    soup = BeautifulSoup(result, "html.parser")
                    f.write(soup.prettify())
                # RecursionError: maximum recursion depth exceeded while calling a Python object
                # or any other case
                except Exception as e:
                    f.write(result)
            else:
                f.write(result)

    return result

def render_page(settings, save_to, **kwargs):
    """
    HTML page wrapper

    Expects: title, contentZ
    """
    kwargs['title'] = getTitle(kwargs.get('title'))
    kwargs['username'] = server.get('username')
    kwargs['link_prefix'] = kwargs.get('link_prefix', '.')
    kwargs['sideMenu'] = renderMenu(
        selectedFolder=kwargs.get('selectedFolder', ''),
        link_prefix=kwargs['link_prefix'],
    )

    if (kwargs.get("headerTitle")):
        kwargs['header'] = renderHeader(kwargs.get("headerTitle"))

    return render_template("html.tpl", save_to, **kwargs)

def build_templates(settings, mailfolders):
    render_index(settings, mailfolders)

def render_index(settings, mailfolders):
    now = datetime.datetime.now()

    info = []
    info.append({
        "title": "IMAP Server",
        "value": settings.get('domain'),
    })

    info.append({
        "title": "Username",
        "value": settings.get('username'),
    })

    info.append({
        "title": "Date of backup",
        "value": str(now),
    })

    render_page(
        settings,
        "%s/%s" % (settings['maildir_result'], "index.html"),
        headerTitle="Email Backup index page",
        link_prefix=".",
        content=render_template(
            settings,
            "page-index.html.tpl",
            None,
            info=info,
            link_prefix=".",
        )
    )