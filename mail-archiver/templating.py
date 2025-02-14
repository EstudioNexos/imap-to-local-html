import os, sys
import time
import datetime
from jinja2 import Environment
from .utils import normalize, remove_dir, copyDir, humansize, simplify_emailheaders, slugify_safe, strftime
import email
import mailbox
from email.utils import parsedate
import hashlib
import base64
import re

def render_thread(settings, mailfolders, struct = {}, thread_current_mail_id = '', currently_selected_mail_id = '', link_prefix = '.'):
    """
    Renders a thread of mails
    """

    if not thread_current_mail_id in struct:
        return ""

    mails = []

    parent_id = struct[thread_current_mail_id].get("parent")

    # if there is no parent, assume no other siblings
    if not parent_id or not parent_id in struct:
        current = {
            "id": thread_current_mail_id,
            "link": struct[thread_current_mail_id].get("link"),
            "date": struct[thread_current_mail_id].get("date"),
            "subject": struct[thread_current_mail_id].get("subject", "(mail not found)"),
            "selected": thread_current_mail_id == currently_selected_mail_id,
        }

        mails.append(current)
    else:
        for sibling_id in struct[parent_id].get("children", []):
            if not sibling_id in struct:
                current = {
                    "id": thread_current_mail_id,
                    "link": None,
                    "date": None,
                    "subject": "(mail not found)",
                    "selected": sibling_id == currently_selected_mail_id,
                }
                mails.append(current)
                continue

            current = {
                "id": sibling_id,
                "link": struct[sibling_id]["link"],
                "date": struct[sibling_id]["date"],
                "subject": struct[sibling_id]["subject"],
                "selected": sibling_id == currently_selected_mail_id,
            }

            mails.append(current)

    # For each sibling, go to first child and try to recurse
    for pos in range(len(mails)):
        # For some
        if not mails[pos]["id"] in struct:
            continue

        if not struct[ mails[pos]["id"] ][ "children" ]:
            continue

        mails[pos]["children"] = render_thread(
            settings,
            mailfolders,
            struct=struct,
            thread_current_mail_id=struct[ mails[pos]["id"] ][ "children" ][0],
            currently_selected_mail_id=currently_selected_mail_id,
            link_prefix=link_prefix,
        )

    mails.sort(key=lambda val: val["date"])

    return render_template(settings, mailfolders, "thread-ul.tpl", None, mails=mails, link_prefix=link_prefix)

def get_mail_content(mail):
    """
    Walks mail and returns mail content
    """
    content_of_mail_text = ""
    content_of_mail_html = ""
    attachments = []

    for part in mail.walk():
        part_content_maintype = part.get_content_maintype()
        part_content_type = part.get_content_type()
        part_charset = part.get_charsets()

        part_transfer_encoding = part.get_all("Content-Transfer-Encoding")
        if part_transfer_encoding:
            part_transfer_encoding = part_transfer_encoding[0]

        if part_content_type in ('text/plain', 'text/html'):
            part_decoded_contents = part.get_payload(decode=True)
            if part_transfer_encoding is None or part_transfer_encoding == "binary":
                part_transfer_encoding = part_charset[0]

            part_decoded_contents = normalize(part_decoded_contents, part_transfer_encoding)

            if part_content_type == 'text/plain':
                content_of_mail_text += part_decoded_contents
                continue

            if part_content_type == 'text/html':
                content_of_mail_html += part_decoded_contents
                continue

        # Attachment
        if not part.get('Content-Disposition') is None:
            if part.get_content_maintype() == 'multipart':
                continue

            attachment_content = part.get_payload(decode=True)
            # Empty file?
            if not attachment_content:
                continue

            attachment_filename_default = 'no-name-%d' % (len(attachments) + 1)

            if part.get_filename():
                attachment_filename = normalize(part.get_filename(), 'header')
            else:
                attachment_filename = attachment_filename_default

            filename_parts = attachment_filename.split(".")

            filename_ext = filename_parts[-1]
            filename_rest = filename_parts[:-1]
            filename_slug = "%s.%s" % (slugify_safe('.'.join(filename_rest), defaultVal=attachment_filename_default), filename_ext.lower())

            attachments.append({
                "title": attachment_filename,
                "slug": filename_slug,
                "filename": attachment_filename,
                "mimetype": part_content_type,
                "maintype": part_content_maintype,
                "content": attachment_content,
                "size": len(attachment_content),
            })

    if content_of_mail_text:
        content_of_mail_text = re.sub(r"(?i)<html>.*?<head>.*?</head>.*?<body>", "", content_of_mail_text, flags=re.DOTALL)
        content_of_mail_text = re.sub(r"(?i)</body>.*?</html>", "", content_of_mail_text, flags=re.DOTALL)
        content_of_mail_text = re.sub(r"(?i)<!DOCTYPE.*?>", "", content_of_mail_text, flags=re.DOTALL)
        content_of_mail_text = re.sub(r"(?i)POSITION: absolute;", "", content_of_mail_text, flags=re.DOTALL)
        content_of_mail_text = re.sub(r"(?i)TOP: .*?;", "", content_of_mail_text, flags=re.DOTALL)


    if content_of_mail_html:
        content_of_mail_html = re.sub(r"(?i)<html>.*?<head>.*?</head>.*?<body>", "", content_of_mail_html, flags=re.DOTALL)
        content_of_mail_html = re.sub(r"(?i)<base .*?>", "", content_of_mail_html, flags=re.DOTALL)
        content_of_mail_html = re.sub(r"(?i)</body>.*?</html>", "", content_of_mail_html, flags=re.DOTALL)
        content_of_mail_html = re.sub(r"(?i)<!DOCTYPE.*?>", "", content_of_mail_html, flags=re.DOTALL)
        content_of_mail_html = re.sub(r"(?i)POSITION: absolute;", "", content_of_mail_html, flags=re.DOTALL)
        content_of_mail_html = re.sub(r"(?i)TOP: .*?;", "", content_of_mail_html, flags=re.DOTALL)

    return content_of_mail_text, content_of_mail_html, attachments


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
            link_prefix=".",
            selected_folder=folder_id,
            content=render_template(
                settings,
                mailfolders,
                "page-mail-list.tpl",
                None,
                mails=mails,
                link_prefix=".",
                selected_folder=folder_id
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
            content_of_mail_text, content_of_mail_html, attachments = get_mail_content(mail)
        except Exception as e:
            error_decoding += "~> Error in get_mail_content: %s" % str(e)

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
            mailfolders,
            "%s/%s" % (maildir_result, mails[mail_id]["file"]),
            title="%s | %s" % (mail_subject, mailfolders[folder_id]["title"]),
            header_title=mails[mail_id]["subject"],
            link_prefix="../../..",
            selected_folder=struct[mail_id]["folders"],
            content=render_template(
                settings,
                mailfolders,
                "page-mail.tpl",
                None,
                mail=mails[mail_id],
                link_prefix="../../..",
                selected_folder=struct[mail_id]["folders"],
                thread=render_thread(
                    settings,
                    mailfolders,
                    struct=struct,
                    thread_current_mail_id=thread_parent,
                    currently_selected_mail_id=mail_id,
                    link_prefix="../../..",
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
    render_page(
        settings,
        mailfolders,
        "%s/%s" % (maildir_result, mailfolders[folder_id]["file"]),
        title="Folder %s (%d)" % (mailfolders[folder_id]["title"], len(mails)),
        header_title="Folder %s (%d)" % (mailfolders[folder_id]["title"], len(mails)),
        link_prefix=".",
        selected_folder=folder_id,
        content=render_template(
            settings,
            mailfolders,
            "page-mail-list.tpl",
            None,
            mails=mails,
            link_prefix=".",
            selected_folder=folder_id,
        )
    )

    print("Done!")

def render_breadcrumbs(folder_id, settings, mailfolders, link_prefix):
    """
    Renders folder breadcrumbs
    """

    # mailfolders = getMailFolders()
    if not folder_id or not folder_id in mailfolders:
        return ''

    folders = []
    currentfolder_id = folder_id
    while currentfolder_id and currentfolder_id in mailfolders:
        if mailfolders[currentfolder_id]["selected"]:
            folders.append((mailfolders[currentfolder_id]["title"], mailfolders[currentfolder_id]["link"]))
        else:
            folders.append((mailfolders[currentfolder_id]["title"], None))

        currentfolder_id = mailfolders[currentfolder_id]["parent"]

    folders = folders[::-1]
    return render_template(
        settings,
        mailfolders,
        "folder-breadcrumbs.tpl",
        None,
        folders=folders,
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
    kwargs['settings'] = settings
    kwargs['mailfolders'] = mailfolders
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

    Expects: title, content
    """
    kwargs['title'] = get_title(settings, kwargs.get('title'))
    kwargs['username'] = settings.get('username')
    kwargs['link_prefix'] = kwargs.get('link_prefix', '.')
    kwargs['assets_location'] = settings.get('assets_location')
    kwargs['sidemenu'] = render_sidemenu(
        settings,
        mailfolders,
        folder=kwargs.get('selected_folder', ''),
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
    remove_dir("{}/{}".format(settings['maildir_result'], settings['assets_location']) )
    copyDir(settings['assets_location'], "{}/{}".format(settings['maildir_result'],settings['assets_location']) )
    struct = build_struct(settings, mailfolders)
    # print(struct)
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
    # print(info)
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