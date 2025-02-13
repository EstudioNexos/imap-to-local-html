import os, sys
import time
import datetime
from jinja2 import Environment
from .utils import normalize, removeDir, copyDir, humansize, simplify_emailheaders, slugify_safe, strftime
import email
import mailbox
from email.utils import parsedate
import hashlib

def to_local(settings, mailfolders, struct, folder_id):
    """
    Creates HTML files and folder index from a mailbox folder
    """
    print(folder_id)
    print("Processing folder: %s" % normalize(folder_id, "utf7"), end="")

    maildir_raw = settings['maildir_raw']
    maildir_result= settings['maildir_result']
    mails = {}

    local_maildir_folder = folder_id.replace("/", ".")
    local_maildir = mailbox.Maildir(os.path.join(maildir_raw), factory=None, create=True)
    try:
        maildir_folder = local_maildir.get_folder(local_maildir_folder)
    except mailbox.NoSuchMailboxError as e:
        render_page(
            settings,
            mailfolders,
            "%s/%s" % (maildir_result, mailfolders[folder_id]["file"]),
            header_title="Folder %s" % mailfolders[folder_id]["title"],
            linkPrefix=".",
            selectedFolder=folder_id,
            content=render_template(
                settings,
                mailfolders,
                "page-mail-list.tpl",
                None,
                mails=mails,
                link_prefix=".",
                selectedFolder=folder_id,
            )
        )

        print("..Done!")
        return

    print("(%d)" % len(maildir_folder), end="")
    sofar = 0
    for mail in maildir_folder:
        mail_id = mail.get('Message-Id')
        if mail_id in mails:
            continue

        mail_subject = normalize(mail.get('Subject'), 'header')

        if not mail_subject:
            mail_subject = "(No Subject)"

        mail_from = normalize(mail.get('From'), 'header')
        mail_to = normalize(mail.get('To'), 'header')
        mail_date = email.utils.parsedate(normalize(mail.get('Date'), 'header'))
        if not mail_date:
            mail_date = (2000, 1, 1, 12, 0, 00, 0, 1, -1)

        if mail_id:
            mail_id_hash = hashlib.md5(mail_id.encode()).hexdigest()
        else:
            temp = "%s %s %s %s" % (mail_subject, mail_date, mail_from, mail_to)
            mail_id = hashlib.md5(temp.encode()).hexdigest()
            mail_id_hash = mail_id

        mail_folder = str(time.strftime("%Y/%m/%d", mail_date))
        mail_raw = ""
        error_decoding = ""

        try:
            mail_raw = normalize(mail.as_bytes())
        except Exception as e:
            error_decoding += "~> Error in mail.as_bytes(): %s" % str(e)

        try:
            os.makedirs("%s/%s" % (maildir_result, mail_folder))
        except:
            pass

        fileName = "%s/%s.html" % (mail_folder, mail_id_hash)
        content_of_mail_text, content_of_mail_html, attachments = "", "", []

        try:
            content_of_mail_text, content_of_mail_html, attachments = getMailContent(mail)
        except Exception as e:
            error_decoding += "~> Error in getMailContent: %s" % str(e)

        data_uri_to_download = ''
        try:
            data_uri_to_download = "data:text/plain;base64,%s" % base64.b64encode(mail_raw.encode())
        except Exception as e:
            error_decoding += "~> Error in data_uri_to_download: %s" % str(e)

        content_default = "raw"
        if content_of_mail_text:
            content_default = "text"
        if content_of_mail_html:
            content_default = "html"

        attachment_count = 0
        for attachment in attachments:
            attachment_count += 1
            attachment["path"] = "%s/%s-%02d-%s" % (mail_folder, mail_id_hash, attachment_count, attachment["slug"])
            attachment["link"] = "%s/%s-%02d-%s" % (mail_folder, mail_id_hash, attachment_count, attachment["slug"])
            try:
                with open("%s/%s" % (maildir_result, attachment["path"]), 'wb') as att_file:
                    att_file.write(attachment["content"])
            except Exception as e:
                error_decoding += "~> Error writing attachment: %s" % str(e)
                print("Error writing attachment: " + str(e) + ".\n")

        mailReplyTo = None
        mailReplyToRaw = normalize(mail.get('In-Reply-To'), 'header')
        if mailReplyToRaw and mailReplyToRaw in struct:
            mailReplyTo = struct[mailReplyToRaw]

        mails[mail_id] = {
            "id": mail_id,
            "from": mail_from,
            "to": mail_to,
            "subject": mail_subject,
            "date": str(time.strftime("%Y-%m-%d %H:%m", mail_date)),
            "size": len(mail_raw),
            "file": fileName,
            "link": "/%s" % fileName,
            "replyTo": mailReplyTo,
            "content": {
                "html": content_of_mail_html,
                "text": content_of_mail_text,
                "raw": mail_raw,
                "default": content_default,
            },
            "download": {
                "filename": "%s.eml" % mail_id_hash,
                "content": data_uri_to_download,
            },
            "attachments": attachments,
            "error_decoding": error_decoding,
            "folders": struct[mail_id]["folders"],
        }

        thread_parent = None
        if struct.get(mail_id, {}).get("parent") or len(struct.get(mail_id, {}).get("children", [])) > 0:
            thread_parent = mail_id
            while struct.get(thread_parent, {}).get("parent"):
                thread_parent = struct.get(thread_parent, {}).get("parent")

        render_page(
            settings,
            mailboxes,
            "%s/%s" % (maildir_result, mails[mail_id]["file"]),
            title="%s | %s" % (mail_subject, mailfolders[folder]["title"]),
            header_title=mails[mail_id]["subject"],
            linkPrefix="../../..",
            selectedFolder=struct[mail_id]["folders"],
            content=render_template(
                settings,
                mailboxes,
                "page-mail.tpl",
                None,
                mail=mails[mail_id],
                linkPrefix="../../..",
                selectedFolder=struct[mail_id]["folders"],
                thread=renderThread(
                    struct=struct,
                    thread_current_mail_id=thread_parent,
                    currently_selected_mail_id=mail_id,
                    linkPrefix="../../..",
                ),
            )
        )

        # No need to keep it in memory
        del mails[mail_id]["content"]
        del mails[mail_id]["download"]
        mails[mail_id]["attachments"] = len(mails[mail_id]["attachments"])

        sofar += 1
        if sofar % 10 == 0:
            print(sofar, end="")
        else:
            print('.', end="")
        sys.stdout.flush()
    print("Done!")

    print("    > Creating index file..", end="")
    sys.stdout.flush()
    renderPage(
        "%s/%s" % (maildir_result, mailfolders[folder]["file"]),
        title="Folder %s (%d)" % (mailfolders[folder]["title"], len(mails)),
        header_title="Folder %s (%d)" % (mailfolders[folder]["title"], len(mails)),
        linkPrefix=".",
        selectedFolder=folder,
        content=renderTemplate(
            "page-mail-list.tpl",
            None,
            mails=mails,
            linkPrefix=".",
            selectedFolder=folder,
        )
    )

    print("Done!")

def render_breadcrumbs(folder_id, mailfolders, link_prefix):
    """
    Renders folder breadcrumbs
    """

    # mailfolders = getMailFolders()
    if not folder_id or not folder_id in mailolders:
        return ''

    folderList = []
    currentfolder_id = folder_id
    while currentfolder_id and currentfolder_id in mailfolders:
        if mailfolders[currentfolder_id]["selected"]:
            folderList.append((mailfolders[currentfolder_id]["title"], mailfolders[currentfolder_id]["link"]))
        else:
            folderList.append((mailfolders[currentfolder_id]["title"], None))

        currentfolder_id = mailfolders[currentfolder_id]["parent"]

    folderList = folderList[::-1]
    return render_template(
        "folder-breadcrumbs.tpl",
        None,
        folderList=folderList,
        link_prefix=link_prefix,
    )

def render_header(settings, mailfolders, title):
    """
    Renders a simple header

    Expects: title
    """

    return render_template(settings, mailfolders, "header-main.tpl", None, title=title)

def render_sidemenu(settings, mailfolders, folder = '', current_parent = '', link_prefix = '.'):
    """
    Renders the menu on the left

    Expects: selected folder (id), current_parent (for recursion)
    """

    menu = []
    # folders = getMailFolders()
    for folder_id in mailfolders:
        folder = mailfolders[folder_id]
        if folder["parent"] != current_parent:
            continue

        add_to_menu = folder
        add_to_menu["children"] = render_sidemenu(
            settings,
            mailfolders,
            folder=folder,
            current_parent=folder_id,
            link_prefix=link_prefix
        )
        menu.append(add_to_menu)

    if len(menu) <= 0:
        return ""

    menu.sort(key=lambda val: val["title"])

    return render_template(
        settings,
        mailfolders,
        "nav-ul.tpl",
        None,
        menu=menu,
        link_prefix=link_prefix,
        folder=folder,
    )

def get_title(settings, title = None):
    """
    Returns title for all pages
    """

    result = []
    if title:
        result.append(title)

    result.append('%s@%s' % (settings.get('username'), settings.get('domain')))
    result.append('Mail Archiver')

    return ' | '.join(result)

def render_template(settings, mailfolders, template_name, save_to, **kwargs):
    """
    Helper function to render a templete with variables
    """
    contents = ''
    template_path = settings['templates_location'] + template_name
    with open(template_path, "r") as f:
        contents = f.read()

    env = Environment()
    env.filters["humansize"] = humansize
    env.filters["simplify_emailheaders"] = simplify_emailheaders
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

def render_page(settings, mailfolders, save_to, **kwargs):
    """
    HTML page wrapper

    Expects: title, contentZ
    """
    kwargs['title'] = get_title(settings, kwargs.get('title'))
    kwargs['username'] = settings.get('username')
    kwargs['link_prefix'] = kwargs.get('link_prefix', '.')
    kwargs['sidemenu'] = render_sidemenu(
        settings,
        mailfolders,
        folder=kwargs.get('selectedFolder', ''),
        link_prefix=kwargs['link_prefix'],
    )

    if (kwargs.get("header_title")):
        kwargs['header'] = render_header(settings, mailfolders, kwargs.get("header_title"))

    return render_template(settings, mailfolders, "html.tpl", save_to, **kwargs)

def build_struct(settings, mailfolders):
    mailfiles = {}
    for folder_id in mailfolders:
        if not mailfolders[folder_id]["selected"]:
            continue

        local_maildir_folder = folder_id.replace("/", ".")
        local_maildir = mailbox.Maildir(os.path.join(settings['maildir_raw']), factory=None, create=True)
        try:
            maildir_folder = local_maildir.get_folder(local_maildir_folder)
        except mailbox.NoSuchMailboxError as e:
            continue

        for mail in maildir_folder:
            mail_id = mail.get('Message-Id')
            mail_subject = normalize(mail.get('Subject'), 'header')
            mail_from = normalize(mail.get('From'), 'header')
            mail_to = normalize(mail.get('To'), 'header')

            if not mail_subject:
                mail_subject = "(No Subject)"

            mail_date = email.utils.parsedate(normalize(mail.get('Date'), 'header'))
            if not mail_date:
                mail_date = (2000, 1, 1, 12, 0, 00, 0, 1, -1)

            if mail_id:
                mail_id_hash = hashlib.md5(mail_id.encode()).hexdigest()
            else:
                temp = "%s %s %s %s" % (mail_subject, mail_date, mail_from, mail_to)
                mail_id = hashlib.md5(temp.encode()).hexdigest()
                mail_id_hash = mail_id

            mail_folder = str(time.strftime("%Y/%m/%d", mail_date))
            fileName = "%s/%s.html" % (mail_folder, mail_id_hash)

            if not mail_id in mailfiles:
                mailfiles[mail_id] = {}

            mailfiles[mail_id]["id"] = mail_id
            mailfiles[mail_id]["date"] = mail_date
            mailfiles[mail_id]["subject"] = mail_subject
            mailfiles[mail_id]["file"] = fileName
            mailfiles[mail_id]["link"] = "/%s" % fileName

            if not mailfiles[mail_id].get("children"):
                mailfiles[mail_id]["children"] = []

            if not mailfiles[mail_id].get("folders"):
                mailfiles[mail_id]["folders"] = []

            if not folder_id in mailfiles[mail_id]["folders"]:
                mailfiles[mail_id]["folders"].append(folder_id)

            if not mailfiles[mail_id].get("parent"):
                mailfiles[mail_id]["parent"] = normalize(mail.get('In-Reply-To'), 'header')

                if mailfiles[mail_id]["parent"]:
                    if not mailfiles[mail_id]["parent"] in mailfiles:
                        mailfiles[ mailfiles[mail_id]["parent"] ] = {
                            "parent": "",
                            "children": [],
                        }

                    if not mail_id in mailfiles[ mailfiles[mail_id]["parent"] ][ "children" ]:
                        mailfiles[ mailfiles[mail_id]["parent"] ][ "children" ].append(mail_id)

        print(".", end="")
        sys.stdout.flush()
    print("Done (%d) mails" % len(mailfiles))
    return (mailfiles)

def build_templates(settings, mailfolders):
    render_index(settings, mailfolders)
    removeDir("%s/assets" % settings['maildir_result'])
    copyDir(settings['assets_location'], "%s/assets" % settings['maildir_result'])
    struct = build_struct(settings, mailfolders)
    print(struct)
    for folder_id in mailfolders:
        if not mailfolders[folder_id]["selected"]:
            continue
        to_local(settings, mailfolders, struct, folder_id)


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
        mailfolders,
        "%s/%s" % (settings['maildir_result'], "index.html"),
        header_title="Email Backup index page",
        link_prefix=".",
        content=render_template(
            settings,
            mailfolders,
            "page-index.html.tpl",
            None,
            info=info,
            link_prefix=".",
        )
    )